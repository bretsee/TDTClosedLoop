function best = sweep_channels(captureFile, opts)
%SWEEP_CHANNELS  Triage every output channel in an open-loop capture.
%
%   best = sweep_channels('capture_rig_run1.csv')
%   best = sweep_channels(file, struct('skipTicks',50,'maxLagTicks',50))
%
%   Answers the first question of the rig day -- "did the stim move ANYTHING,
%   and if so which channel?" -- with one line per output channel, before you
%   commit to a full fit on any one of them.
%
%   This exists because fit_sysid_from_capture reports one channel at a time
%   (useOutputs is a single index) and prints a full page each call. Running it
%   16 times by hand and eyeballing 16 pages is exactly the kind of thing that
%   goes wrong under time pressure with an animal on the table.
%
%   THE COLUMN THAT DECIDES EVERYTHING IS |corr|.
%   It is the peak absolute cross-correlation between a moving stim channel and
%   the output, over lags 0-500 ms, computed on the SAME causal alignment and
%   warm-up discard the fitter uses. Below ~0.1 the stim did not measurably move
%   that feature, and the fit column for that row is meaningless however
%   confident it looks -- ARX will always return something.
%
%   valFit% is scored on held-out data by fit_sysid_from_capture. It is a
%   secondary check: a high |corr| with a near-zero valFit means there is a
%   relationship but not a linear dynamic one at this order.
%
%   opts fields (all optional):
%     skipTicks        leading ticks discarded as warm-up      (default 50)
%     inputDelayTicks  one-tick localhost command lag          (default 1)
%     maxLagTicks      lags searched for peak |corr|           (default 50 = 500 ms)
%     quiet            suppress the per-channel fit output     (default true)
%
%   Returns a struct with .channel, .corr, .valFit, .order and .table (all rows),
%   so a caller can act on the winner without re-parsing printed text.
%
%   NO TOOLBOXES. Plain matrix arithmetic only, same as the rest of this path.

    if nargin < 2 || isempty(opts)
        opts = struct();
    end
    opts = set_default(opts, 'skipTicks',       50);
    opts = set_default(opts, 'inputDelayTicks',  1);
    opts = set_default(opts, 'maxLagTicks',     50);
    opts = set_default(opts, 'quiet',         true);

    T = readtable(captureFile);
    names = T.Properties.VariableNames;
    uCols = find(startsWith(names, 'u'));
    yCols = find(startsWith(names, 'y'));
    if isempty(uCols) || isempty(yCols)
        error('sweep_channels:BadCapture', ...
              '%s has no u* / y* columns -- is it an openloop capture?', captureFile);
    end

    U = table2array(T(:, uCols));
    Y = table2array(T(:, yCols));

    % Same causal alignment the fitter applies: the command logged at tick k is
    % not transmitted until tick k+1, so u(k) acts on y(k+1). Getting this wrong
    % by one sample is the classic way to invent a response that is not there.
    d = opts.inputDelayTicks;
    if d > 0
        U = U(1:end-d, :);
        Y = Y(1+d:end, :);
    end
    s = min(opts.skipTicks, size(U, 1) - 10);
    if s > 0
        U = U(s+1:end, :);
        Y = Y(s+1:end, :);
    end

    moved = find(std(U, 0, 1) > eps);
    if isempty(moved)
        error('sweep_channels:NoInputMovement', ...
              'No stim channel moved in %s. Nothing to correlate against.', captureFile);
    end

    nY = size(Y, 2);
    fprintf('\n%s: %d ticks after alignment, stim channels that moved: [%s]\n', ...
            captureFile, size(U, 1), strtrim(sprintf('%d ', moved)));
    fprintf('\n   ch     |corr|   bestStim   valFit%%   order   slowestPole   verdict\n');
    fprintf('  ----    -------   --------   -------   -----   -----------   --------\n');

    rows = struct('channel', {}, 'corr', {}, 'stim', {}, 'valFit', {}, 'order', {}, 'pole', {});
    best = struct('channel', 0, 'corr', 0, 'valFit', -Inf, 'order', NaN);

    for ch = 1:nY
        % --- peak |corr| across every moving stim channel --------------------
        cmax = 0; cArg = moved(1);
        for ii = 1:numel(moved)
            c = max_abs_xcorr(U(:, moved(ii)), Y(:, ch), opts.maxLagTicks);
            if c > cmax
                cmax = c; cArg = moved(ii);
            end
        end

        % --- fit, quietly ----------------------------------------------------
        valFit = NaN; order = NaN; pole = NaN;
        try
            cmd = sprintf('r = fit_sysid_from_capture(''%s'', struct(''useOutputs'',%d));', ...
                          captureFile, ch);
            if opts.quiet
                evalc(cmd);          %#ok<EVLCS>  output deliberately discarded
            else
                eval(cmd);           %#ok<EVLEQ>
            end
            valFit = r.valFit;
            order  = r.order;
            if isstruct(r.sys) && isfield(r.sys, 'A') && ~isempty(r.sys.A)
                pole = max(abs(eig(r.sys.A)));
            end
        catch fitErr
            fprintf('  %4d    %7.3f   %8d   FIT FAILED (%s)\n', ch, cmax, cArg, fitErr.identifier);
            rows(end+1) = struct('channel', ch, 'corr', cmax, 'stim', cArg, ...
                                 'valFit', NaN, 'order', NaN, 'pole', NaN); %#ok<AGROW>
            continue;
        end

        if cmax >= 0.10
            verdict = 'RESPONDS';
        elseif cmax >= 0.05
            verdict = 'marginal';
        else
            verdict = '-';
        end

        fprintf('  %4d    %7.3f   %8d   %7.2f   %5d   %11.4f   %s\n', ...
                ch, cmax, cArg, valFit, order, pole, verdict);

        rows(end+1) = struct('channel', ch, 'corr', cmax, 'stim', cArg, ...
                             'valFit', valFit, 'order', order, 'pole', pole); %#ok<AGROW>

        if cmax > best.corr
            best.channel = ch; best.corr = cmax;
            best.valFit  = valFit; best.order = order;
        end
    end

    best.table = rows;

    fprintf('\n');
    if best.corr < 0.10
        fprintf('*** NO CHANNEL RESPONDED. Best |corr| = %.3f (want > 0.1). ***\n', best.corr);
        fprintf('*** Do NOT fit or save a model from this capture.          ***\n');
        fprintf('*** See RIG_DAY_2026-07-30.md branch C1 before re-running. ***\n');
    else
        fprintf('Strongest: output channel %d, |corr| %.3f (driven by stim ch %d), valFit %.2f%%\n', ...
                best.channel, best.corr, rows(best.channel).stim, best.valFit);
        fprintf('Next: .\\rig\\3_fit.ps1 -Channel %d   (full report before you save)\n', best.channel);
    end
end

% =========================================================================

function r = max_abs_xcorr(x, y, maxLag)
    % Peak absolute Pearson correlation of y against x over lags 0..maxLag,
    % where lag L means y is compared against x delayed by L ticks. Written out
    % rather than calling xcorr so this does not need the Signal Processing
    % Toolbox at acquisition time.
    x = x(:) - mean(x);
    y = y(:) - mean(y);
    n = numel(x);
    maxLag = max(0, min(maxLag, n - 10));
    r = 0;
    for L = 0:maxLag
        xa = x(1:n-L);
        ya = y(1+L:n);
        dx = norm(xa); dy = norm(ya);
        if dx > eps && dy > eps
            r = max(r, abs((xa.' * ya) / (dx * dy)));
        end
    end
end

function s = set_default(s, field, value)
    if ~isfield(s, field) || isempty(s.(field))
        s.(field) = value;
    end
end
