function result = fit_sysid_from_capture(captureFile, opts)
%FIT_SYSID_FROM_CAPTURE  Identify a plant model from an open-loop capture.
%
%   result = fit_sysid_from_capture('capture_openloop.csv')
%   result = fit_sysid_from_capture(file, opts)
%
%   Takes the (u, y) CSV written by matlab_controller_server in 'openloop' mode
%   and fits a discrete state-space model at the 100 Hz control rate, in the
%   struct form (.A .B .C .D .Ts) that mpc_test expects at AllModels(10).sys.
%
%   NO TOOLBOXES REQUIRED. This machine has only MATLAB, Signal Processing, DSP,
%   Communications and Instrument Control -- there is no System Identification
%   Toolbox (no n4sid/iddata/compare) and no Control System Toolbox (no ss/c2d/
%   place/dcgain). Everything here is plain matrix arithmetic:
%     * identification is ARX by linear least squares (backslash),
%     * the ARX polynomials are realized in observable canonical form,
%     * validation simulates the realization directly and scores NRMSE.
%   If the System Identification Toolbox is ever installed, n4sid on the same
%   aligned/detrended data is a strictly better estimator and worth switching to.
%
%   opts fields (all optional):
%     inputDelayTicks  ticks between a command being logged and applied (default 1)
%     skipTicks        leading ticks to discard as warm-up             (default 50)
%     useInputs        input channel indices to keep         (default all non-constant)
%     useOutputs       output channel index to keep (single output)    (default 1)
%     orders           candidate ARX orders na=nb to try               (default 1:8)
%     nk               extra input delay inside the ARX model          (default 1)
%     trainFraction    fraction of the record used for fitting         (default 0.7)
%     save             write the chosen model into AllModels.mat       (default false)
%     modelIndex       AllModels entry to overwrite when saving        (default 10)
%
%   WHY EACH STEP MATTERS (this is the part that decides whether the model is
%   real or an artifact):
%
%   1. Causal alignment. The server logs the command it computed from y_k, but
%      the C++ loop does not transmit that command until the following tick. So
%      the command that actually acted on the plant during tick k is the one
%      logged at tick k-1. Getting this wrong by one sample produces a model with
%      a spurious direct feedthrough term and an optimistic fit.
%
%   2. Detrending. MAV features are strictly positive and have a large DC offset
%      relative to their modulation. A linear model fitted to un-centred data
%      spends its dynamic range explaining the mean instead of the response, and
%      the MPC then sees a bias it cannot reject. Both u and y are mean-removed;
%      the offsets are returned so they can be reapplied.
%
%   3. Validation on a held-out tail. Training-set fit rises monotonically with
%      order and will happily justify an order-8 model of noise. Order is chosen
%      on data the fit never saw.
%
%   4. An input-movement check. If a stim channel never moved, or the output did
%      not respond to it, no amount of fitting produces a usable model -- it just
%      produces a confident-looking one. That case is reported loudly.

    if nargin < 2 || isempty(opts)
        opts = struct();
    end
    opts = set_default(opts, 'inputDelayTicks', 1);
    opts = set_default(opts, 'skipTicks',       50);
    opts = set_default(opts, 'useInputs',       []);
    opts = set_default(opts, 'useOutputs',      1);
    opts = set_default(opts, 'orders',          1:8);
    opts = set_default(opts, 'nk',              1);
    opts = set_default(opts, 'trainFraction',   0.7);
    opts = set_default(opts, 'save',            false);
    opts = set_default(opts, 'modelIndex',      10);
    % Parsimony: accept the SMALLEST order whose validation fit is within this
    % many percentage points of the best. ARX is an equation-error method, so on
    % noisy data it buys apparent fit with extra states that model the noise
    % colouring rather than the plant (on a synthetic order-2 plant it will pick
    % order 5 if left unchecked). Fewer states also means a smaller QP in
    % mpc_test. Set to 0 to always take the outright best fit.
    opts = set_default(opts, 'parsimonyTolerance', 1.0);

    % Ts is MEASURED from the capture below, not assumed: wall-clock runs tick
    % at ~10 ms, frame-locked runs (--tick-frames 6) at 9.8304 ms. The model
    % carries the rate its data was collected at, and mpc_test /
    % export_plant_lti follow the model's Ts. Never resample between the two
    % rates -- the controller steps once per tick regardless; Ts only labels
    % physical time (time constants, settle estimates).
    Ts = 0.01;   % fallback when the capture has no t_ms column

    % ---- load -------------------------------------------------------------
    T = readtable(captureFile);
    if any(strcmp(T.Properties.VariableNames, 't_ms')) && height(T) > 10
        TsMeas = median(diff(T.t_ms)) / 1000;
        % Snap to the two known rates when within 2% so labels stay exact.
        known = [0.01, 6 / 610.3515625];
        [dev, ki] = min(abs(TsMeas - known) ./ known);
        if dev < 0.02
            TsMeas = known(ki);
        end
        if TsMeas > 0 && isfinite(TsMeas)
            Ts = TsMeas;
        end
        fprintf('Control period measured from capture: Ts = %.7g s (%.4f Hz)\n', Ts, 1 / Ts);
    end
    uCols = find_cols(T.Properties.VariableNames, 'u');
    yCols = find_cols(T.Properties.VariableNames, 'y');
    if isempty(uCols) || isempty(yCols)
        error('fit_sysid_from_capture:BadCapture', ...
              'Capture file %s has no u*/y* columns.', captureFile);
    end
    U = table2array(T(:, uCols));
    Y = table2array(T(:, yCols));

    fprintf('Loaded %s: %d ticks (%.1f s), %d inputs, %d outputs\n', ...
            captureFile, size(U, 1), size(U, 1) * Ts, size(U, 2), size(Y, 2));

    % ---- causal alignment (step 1) ----------------------------------------
    d = round(opts.inputDelayTicks);
    if d > 0
        U = U(1:end-d, :);
        Y = Y(1+d:end, :);
        fprintf('Applied %d-tick input delay: u(k) now aligned with y(k+%d).\n', d, d);
    end

    % ---- trim warm-up -----------------------------------------------------
    s = min(max(0, round(opts.skipTicks)), size(U, 1) - 10);
    if s > 0
        U = U(s+1:end, :);
        Y = Y(s+1:end, :);
        fprintf('Discarded %d warm-up ticks.\n', s);
    end

    % ---- channel selection ------------------------------------------------
    if isempty(opts.useInputs)
        moved = find(std(U, 0, 1) > 1e-9);
        if isempty(moved)
            error('fit_sysid_from_capture:NoInputMovement', ...
                  'No input channel varies. There is nothing to identify.');
        end
        opts.useInputs = moved;
    end
    if numel(opts.useOutputs) ~= 1
        error('fit_sysid_from_capture:SingleOutputOnly', ...
              ['This ARX path identifies one output at a time. Pass a single ' ...
               'index in opts.useOutputs and run it once per output channel.']);
    end
    U = U(:, opts.useInputs);
    Y = Y(:, opts.useOutputs);
    fprintf('Using inputs [%s] and output %d.\n', ...
            num2str(opts.useInputs(:)'), opts.useOutputs);

    % ---- sanity check (step 4) --------------------------------------------
    report_excitation_quality(U, Y);

    % ---- detrend (step 2) -------------------------------------------------
    uOffset = mean(U, 1);
    yOffset = mean(Y, 1);
    Uc = U - uOffset;
    Yc = Y - yOffset;

    % ---- split ------------------------------------------------------------
    n = size(Uc, 1);
    nTrain = max(20, round(opts.trainFraction * n));
    nTrain = min(nTrain, n - 10);
    Utr = Uc(1:nTrain, :);       Ytr = Yc(1:nTrain);
    Uva = Uc(nTrain+1:end, :);   Yva = Yc(nTrain+1:end);
    fprintf('Split: %d ticks train (%.1f s), %d ticks validation (%.1f s).\n', ...
            nTrain, nTrain * Ts, n - nTrain, (n - nTrain) * Ts);

    % ---- order sweep (step 3) ---------------------------------------------
    fprintf('\n  order   trainFit%%   valFit%%   stable   slowestPole\n');
    fprintf(  '  -----   ---------   -------   ------   -----------\n');
    best = struct('valFit', -Inf, 'order', NaN, 'sys', []);
    valFits = nan(numel(opts.orders), 1);
    candidates = cell(numel(opts.orders), 1);

    for i = 1:numel(opts.orders)
        na = opts.orders(i);
        try
            [a, B] = arx_ls(Ytr, Utr, na, na, opts.nk);
            sysi = arx_to_ss(a, B, Ts);
        catch fitErr
            fprintf('  %5d   (fit failed: %s)\n', na, fitErr.identifier);
            continue;
        end

        trainFit = nrmse_fit(Ytr, simulate_ss(sysi, Utr));
        valFit   = nrmse_fit(Yva, simulate_ss(sysi, Uva));
        poles = abs(eig(sysi.A));
        isStable = all(poles < 1);
        valFits(i) = valFit;

        fprintf('  %5d   %9.2f   %7.2f   %6s   %11.4f\n', ...
                na, trainFit, valFit, bool_str(isStable), max(poles));

        % Only accept a stable model: mpc_test builds prediction matrices from
        % A^i out to N=20, so an unstable A makes the QP numerically hopeless.
        if isStable
            candidates{i} = struct('order', na, 'valFit', valFit, 'sys', sysi);
            if valFit > best.valFit
                best.valFit = valFit;
                best.order  = na;
                best.sys    = sysi;
            end
        end
    end

    if isempty(best.sys)
        error('fit_sysid_from_capture:NoUsableModel', ...
              'No stable model was found across orders [%s].', num2str(opts.orders));
    end

    % Parsimony: prefer the smallest order that is statistically as good.
    if opts.parsimonyTolerance > 0
        for i = 1:numel(candidates)
            c = candidates{i};
            if ~isempty(c) && c.valFit >= best.valFit - opts.parsimonyTolerance
                if c.order < best.order
                    fprintf(['\nParsimony: order %d (%.2f%%) is within %.2f pp of the ' ...
                             'best order %d (%.2f%%); taking the smaller model.\n'], ...
                            c.order, c.valFit, opts.parsimonyTolerance, ...
                            best.order, best.valFit);
                    best = c;
                end
                break;
            end
        end
    end

    fprintf('\nChosen: order %d, validation fit %.2f%%\n', best.order, best.valFit);
    describe_model(best.sys, Ts);

    result = struct();
    result.sys        = best.sys;
    result.order      = best.order;
    result.valFit     = best.valFit;
    result.uOffset    = uOffset;
    result.yOffset    = yOffset;
    result.Ts         = Ts;
    result.useInputs  = opts.useInputs;
    result.useOutputs = opts.useOutputs;
    result.orders     = opts.orders;
    result.valFits    = valFits;
    result.method     = 'ARX least squares -> observable canonical form';

    if opts.save
        save_into_allmodels(best.sys, opts.modelIndex, result);
    else
        fprintf(['\nNot saved. Re-run with opts.save = true to write this into ' ...
                 'AllModels(%d).sys.\n'], opts.modelIndex);
    end
end

% =========================================================================
% Identification
% =========================================================================

function [a, B] = arx_ls(y, U, na, nb, nk)
% Least-squares ARX fit:
%   y(k) = -a1*y(k-1) - ... - ana*y(k-na)
%          + sum_ch [ b_ch,1*u_ch(k-nk) + ... + b_ch,nb*u_ch(k-nk-nb+1) ]
%
% Returns a = [a1..ana] and B (nb x nu), one column per input channel.

    y = y(:);
    N = numel(y);
    nu = size(U, 2);
    maxLag = max(na, nk + nb - 1);
    rows = (maxLag + 1):N;
    if numel(rows) < (na + nb * nu + 5)
        error('fit_sysid_from_capture:TooFewSamples', ...
              'Not enough samples for order %d with %d inputs.', na, nu);
    end

    Phi = zeros(numel(rows), na + nb * nu);
    for i = 1:na
        Phi(:, i) = -y(rows - i);
    end
    col = na;
    for ch = 1:nu
        for j = 1:nb
            col = col + 1;
            Phi(:, col) = U(rows - nk - j + 1, ch);
        end
    end

    theta = Phi \ y(rows);

    a = theta(1:na).';
    B = reshape(theta(na+1:end), nb, nu);
end

function sys = arx_to_ss(a, B, Ts)
% Observable canonical realization of
%     y(k) = -a1 y(k-1) ... -an y(k-n) + sum_ch b_ch(z^-1) u_ch
% giving a strictly proper (D = 0) discrete state-space model.
%
%   A = [-a1  1  0 ... 0        B = [b_1,: ;      C = [1 0 ... 0]
%        -a2  0  1 ... 0             b_2,: ;      D = 0
%         ...                        ...   ]
%        -an  0  0 ... 0]

    n = numel(a);
    nb = size(B, 1);
    nu = size(B, 2);

    A = zeros(n, n);
    A(:, 1) = -a(:);
    if n > 1
        A(1:n-1, 2:n) = eye(n-1);
    end

    Bfull = zeros(n, nu);
    Bfull(1:min(n, nb), :) = B(1:min(n, nb), :);

    C = zeros(1, n);
    C(1) = 1;

    sys = struct('A', A, 'B', Bfull, 'C', C, 'D', zeros(1, nu), 'Ts', Ts);
end

function yhat = simulate_ss(sys, U)
% Free-run (infinite-horizon) simulation: no measured y is fed back, which is
% the honest test of a model intended for multi-step MPC prediction.
    N = size(U, 1);
    n = size(sys.A, 1);
    x = zeros(n, 1);
    yhat = zeros(N, 1);
    for k = 1:N
        yhat(k) = sys.C * x + sys.D * U(k, :).';
        x = sys.A * x + sys.B * U(k, :).';
    end
end

function f = nrmse_fit(y, yhat)
% Percentage fit, same definition the System Identification Toolbox uses:
%   100 * (1 - ||y - yhat|| / ||y - mean(y)||)
    y = y(:); yhat = yhat(:);
    den = norm(y - mean(y));
    if den < eps || ~all(isfinite(yhat))
        f = -Inf;
        return;
    end
    f = 100 * (1 - norm(y - yhat) / den);
end

% =========================================================================
% Diagnostics
% =========================================================================

function report_excitation_quality(U, Y)
    fprintf('\nExcitation check:\n');
    for i = 1:size(U, 2)
        ui = U(:, i);
        levels = numel(unique(round(ui, 6)));
        fprintf('  input %d: range [%.3g %.3g], std %.3g, %d distinct levels\n', ...
                i, min(ui), max(ui), std(ui), levels);
        if std(ui) < 1e-9
            fprintf('    WARNING: this input never moved; it cannot be identified.\n');
        elseif levels < 2
            fprintf('    WARNING: only one level present.\n');
        end
    end
    for j = 1:size(Y, 2)
        yj = Y(:, j);
        fprintf('  output %d: range [%.3g %.3g], std %.3g\n', ...
                j, min(yj), max(yj), std(yj));
        if std(yj) < 1e-9
            fprintf('    WARNING: this output is constant; nothing to explain.\n');
        end
    end

    % Peak absolute cross-correlation over a 0-500 ms lag window. This is a rough
    % "did the stim do anything at all" indicator, not a rigorous test.
    maxLag = 50;
    for i = 1:size(U, 2)
        for j = 1:size(Y, 2)
            r = max_abs_xcorr(U(:, i), Y(:, j), maxLag);
            fprintf('  |corr| u%d -> y%d within 0-500 ms: %.3f\n', i, j, r);
            if r < 0.1
                fprintf(['    WARNING: little apparent response. A model fitted here ' ...
                         'will mostly describe noise.\n']);
            end
        end
    end
    fprintf('\n');
end

function r = max_abs_xcorr(x, y, maxLag)
    x = x(:) - mean(x);
    y = y(:) - mean(y);
    sx = std(x); sy = std(y);
    if sx < eps || sy < eps
        r = 0;
        return;
    end
    r = 0;
    n = numel(x);
    for lag = 0:maxLag
        a = x(1:n-lag);
        b = y(1+lag:n);
        v = abs(sum(a .* b) / ((n - lag) * sx * sy));
        r = max(r, v);
    end
end

function describe_model(sys, Ts)
    poles = eig(sys.A);
    mag = abs(poles);
    n = size(sys.A, 1);
    fprintf('\nModel summary:\n');
    fprintf('  states %d, inputs %d, outputs %d, Ts %g s\n', ...
            n, size(sys.B, 2), size(sys.C, 1), Ts);

    % DC gain computed directly: C*(I-A)^-1*B + D (no Control System Toolbox).
    M = eye(n) - sys.A;
    if rcond(M) > 1e-12
        K = sys.C * (M \ sys.B) + sys.D;
        fprintf('  DC gain: %s\n', mat2str(K, 4));
    else
        fprintf('  DC gain unavailable (model has a pole at z = 1).\n');
    end

    slow = max(mag(mag < 1));
    if ~isempty(slow) && slow > 0
        tau = -Ts / log(slow);
        fprintf('  slowest pole |z| = %.4f -> time constant ~%.0f ms (settles ~%.0f ms)\n', ...
                slow, tau * 1000, 4 * tau * 1000);
    end
    fprintf('  all poles inside unit circle: %s\n', bool_str(all(mag < 1)));
end

% =========================================================================
% Saving
% =========================================================================

function save_into_allmodels(sys, idx, result)
    matPath = fullfile(pwd, 'AllModels.mat');
    if isfile(matPath)
        stamp = char(datetime('now', 'Format', 'yyyyMMdd_HHmmss'));
        backup = fullfile(pwd, sprintf('AllModels_backup_%s.mat', stamp));
        copyfile(matPath, backup);
        fprintf('Backed up existing AllModels.mat -> %s\n', backup);
        S = load(matPath);
    else
        S = struct();
    end

    if ~isfield(S, 'AllModels')
        S.AllModels = struct('sys', {});
    end
    AllModels = S.AllModels;
    if numel(AllModels) < idx
        AllModels(idx).sys = [];
    end

    % Saved as a plain struct, which is what mpc_test's unpack_model accepts
    % without the Control System Toolbox (an ss object would need it).
    AllModels(idx).sys = sys;
    S.AllModels = AllModels;
    S.SYSID_INFO = result;

    save(matPath, '-struct', 'S');
    fprintf('Wrote identified model into AllModels(%d).sys in %s\n', idx, matPath);
    fprintf('Run mpc_test([]) to force the controller to reload it.\n');
end

% =========================================================================
% Utility
% =========================================================================

function cols = find_cols(names, prefix)
    cols = {};
    for i = 1:numel(names)
        nm = names{i};
        if startsWith(nm, prefix) && numel(nm) > 1 && all(isstrprop(nm(2:end), 'digit'))
            cols{end+1} = nm; %#ok<AGROW>
        end
    end
end

function s = bool_str(b)
    if b
        s = 'yes';
    else
        s = 'NO';
    end
end

function s = set_default(s, field, value)
    if ~isfield(s, field) || isempty(s.(field))
        s.(field) = value;
    end
end
