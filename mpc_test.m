function u = mpc_test(y_feat, r_now)
% MPC_TEST  100 Hz MPC step for the current C++ control loop contract.
%
% This version is adapted for the refactored C++ loop:
%   - C++ already acquires PO8e continuously
%   - C++ already preprocesses the last 10 ms window into one scalar per input
%     channel
%   - C++ already calls MATLAB at the 100 Hz control interval
%
% So each call to mpc_test(...) is one control tick. There is no internal
% raw-sample accumulation or decimation in this file.
%
% Reference (optional second argument, added for trajectory tracking):
%   mpc_test(y)          constant reference from MPC_TARGET, as before
%   mpc_test(y, r)       r = [p x 1]: this tick's reference, held over the horizon
%   mpc_test(y, Rprev)   Rprev = [p x K]: reference PREVIEW, column j = the
%                        reference at tick k+j. K != N is fine: cropped, or
%                        padded by holding the last column. Preview is what lets
%                        the MPC lead into a fast transient (a ~200 ms touch
%                        template) instead of chasing it a horizon late.
%
% Tuning (optional): a struct MPC_OPTS in the base workspace or saved inside
% AllModels.mat, read once at init (call mpc_test([]) after changing it):
%   .N .Nu .qWeight .rWeight .umin .umax   (defaults 20, 2, 1, 1, 0, 40)
%   .featureChannel (default 0 = first-p mapping; k>0 = model output is
%                    feature channel k -- replaces hand-editing feature_map)
%   .useObserver    (default 1; 0 = pure feedforward on the model, LOUD warning)
% rWeight matters: the cost penalises ABSOLUTE u with no integral action, so
% with rWeight=1 the loop deliberately settles SHORT of the target at
% u* = r*g/(g^2 + rWeight/qWeight). Use rWeight ~1e-3..1e-4 for tracking.
%
% Model slot (optional): MPC_MODEL_INDEX (base workspace or in AllModels.mat)
% selects which AllModels(k).sys to control from; default 10.
%
% Operating point: if the model struct carries uOffset/yOffset (stored by
% fit_sysid_from_capture, which fits on mean-removed data), the controller
% runs its observer/QP in centered coordinates and converts at the measurement
% and command boundaries. Models without offsets behave exactly as before.
%
% Reset:
%   mpc_test([])

persistent P

if nargin >= 1 && (ischar(y_feat) || isstring(y_feat))
    % Soft reset: zero the controller STATE but keep the initialized problem
    % (model, prediction matrices, OSQP). Used after warm-up so the run starts
    % clean without re-paying the ~60 ms init on the first real tick.
    if strcmpi(string(y_feat), "state")
        if ~isempty(P)
            P.xhat   = zeros(P.n, 1);
            P.u_last = zeros(P.m, 1);
            P.tick   = 0;
        end
        u = [];
        return;
    end
    error('mpc_test:BadCommand', 'Unknown command "%s" (only ''state'').', y_feat);
end

if nargin == 0 || isempty(y_feat)
    P = [];
    u = [];
    return;
end

y_feat = double(y_feat(:));
y_feat = sanitize_vector(y_feat, 1e4);

if isempty(P)
    P = init_controller(numel(y_feat));
end

% Keep input length fixed after first call.
y_feat = fit_length(y_feat, P.ny_feat);

% Map preprocessed acquisition vector -> controller measurement y_k
yk = feature_map(y_feat, P);   % size = [p x 1]
yk = sanitize_vector(yk, 1e4);

% The model was fitted on mean-removed data (fit_sysid_from_capture), so the
% observer, prediction and QP all work in CENTERED coordinates. yk stays raw
% for the debug log; P.u_last stays raw (so zeros always mean "stim off") and
% is re-centered here at the point of use.
yk_c = yk - P.yOff;

% State estimate update using last applied input
x_pred = P.A * P.xhat + P.B * (P.u_last - P.uOff);
x_pred = sanitize_vector(x_pred, 1e6);

if P.useObserver
    y_pred = P.C * x_pred + P.D * (P.u_last - P.uOff);
    y_pred = sanitize_vector(y_pred, 1e6);
    P.xhat = x_pred + P.L * (yk_c - y_pred);
else
    P.xhat = x_pred;
end
P.xhat = sanitize_vector(P.xhat, 1e6);

% Reference over horizon
if nargin >= 2 && ~isempty(r_now)
    r = build_reference_stack(r_now, P);   % [pN x 1] from p x 1 or p x K preview
else
    r0 = get_reference(P);    % size = [p x 1]
    r  = repmat(r0, P.N, 1);  % size = [pN x 1]
end
r = sanitize_vector(r, 1e6);
% References arrive in RAW feature units from all three sources (MPC_TARGET is
% re-read live every tick; preview rows come from raw-unit CSVs), so center
% here, per tick -- centering targetDefault at init would make them disagree.
r = r - P.rOffStack;

% Linear term for condensed QP
fx = P.F * P.xhat;
fx = sanitize_vector(fx, 1e6);
q  = P.GS.' * (P.Qbar * (fx - r));
q  = sanitize_vector(q, 1e6);

P.tick = P.tick + 1;
write_debug_log(P, y_feat, yk, q);

% Solve QP
P.prob.update('q', full(q));
res = P.prob.solve();

if isempty(res.x) || any(~isfinite(res.x))
    % Fail-safe: hold previous command (P.u_last is RAW -- no offset math)
    u = P.u_last;
else
    z = res.x;
    u = z(1:P.m);          % centered first move
    if P.hasOffsets
        u = u + P.uOff;    % -> raw command units (guarded: x+0 can flip -0)
    end
end

% Clamp (OSQP tolerance net -- the QP box already maps onto [umin,umax] after
% un-centering, so this cannot double-clip an exact solution) and kill solver
% dust: sub-1e-8 magnitudes are ADMM residue, not commands.
u = min(max(u, P.umin), P.umax);
u(abs(u) < 1e-8) = 0;
P.u_last = u;              % RAW applied command; re-centered at next tick's use
end


% =========================================================================
% Initialization
% =========================================================================
function P = init_controller(ny_feat)

    % -----------------------------
    % EDIT THESE FIRST
    % -----------------------------
    P.controlFs = 100;          % nominal control rate; the MODEL's Ts wins below

    % Load the controller assets from the base workspace or local .mat file.
    assets = load_controller_assets();
    sys = get_model_entry(assets.AllModels, get_model_index(assets));

    % The model's sample time is the source of truth: fit_sysid_from_capture
    % stamps the MEASURED tick period of the capture it was fit from (10 ms
    % wall-clock, or 9.8304 ms frame-locked / --tick-frames 6). The controller
    % steps once per tick either way; Ts only labels physical time, so it must
    % never be "resampled" between the two rates.
    Ts = 1 / P.controlFs;
    modelTs = get_model_ts(sys);
    if ~isnan(modelTs) && modelTs > 0
        if abs(modelTs - Ts) / Ts > 0.05
            warning('mpc_test:UnusualTs', ...
                    'Model Ts = %g s is >5%% from the nominal %g s -- check the model.', ...
                    modelTs, Ts);
        end
        Ts = modelTs;
    end
    [A, B, C, D] = unpack_model(sys, Ts);

    P.A = full(A);
    P.B = full(B);
    P.C = full(C);
    P.D = full(D);

    P.n = size(P.A,1);
    P.m = size(P.B,2);
    P.p = size(P.C,1);

    % Operating point: fit_sysid_from_capture stores the capture means WITH the
    % model (sys.uOffset / sys.yOffset). Zeros when absent -> every centering
    % below is a bit-exact no-op and legacy models behave identically.
    [P.uOff, P.yOff] = get_model_offsets(sys, P.m, P.p);
    P.hasOffsets = any(P.uOff ~= 0) || any(P.yOff ~= 0);

    % MPC horizons / weights / bounds, overridable via MPC_OPTS (see header).
    mpcOpts = get_mpc_opts(assets);
    P.N  = mpcOpts.N;
    P.Nu = mpcOpts.Nu;
    P.featureChannel = mpcOpts.featureChannel;   % 0 = legacy first-p mapping
    P.rOffStack = [];   % filled after P.N is final (below)

    % qWeight/rWeight may be per-output/per-input VECTORS (MIMO: feature scales
    % differ across control channels). A scalar behaves exactly as before.
    Q = diag(expand_weight(mpcOpts.qWeight, P.p, 'qWeight'));
    R = diag(expand_weight(mpcOpts.rWeight, P.m, 'rWeight'));

    % Input constraints
    P.umin = mpcOpts.umin * ones(P.m,1);
    P.umax = mpcOpts.umax * ones(P.m,1);

    % Feature vector size expected from the C++ preprocessing stage
    P.ny_feat = ny_feat;

    % Build prediction matrices
    [P.F, P.G] = predmat_y(P.A, P.B, P.C, P.D, P.N);
    S          = hold_last_map(P.N, P.Nu, P.m);

    P.Qbar = kron(speye(P.N), Q);
    Rbar   = kron(speye(P.N), R);
    P.GS   = P.G * S;

    H = (P.GS.' * P.Qbar * P.GS) + (S.' * Rbar * S);
    P.H = sparse((H + H.') / 2);

    % Bound constraints on z = [u0; u1; ...; u_{Nu-1}]. z is CENTERED, so the
    % box shifts by -uOff; adding uOff back after the solve maps it exactly
    % onto [umin, umax] (the raw clamp downstream is only a tolerance net).
    lb = repmat(P.umin - P.uOff, P.Nu, 1);
    ub = repmat(P.umax - P.uOff, P.Nu, 1);

    if exist('osqp', 'class') ~= 8 && exist('osqp', 'file') == 0
        error('mpc_test:MissingOsqp', ...
              ['OSQP was not found on the MATLAB path. ' ...
               'Install OSQP and run addpath(...) before using mpc_test.']);
    end

    P.prob = osqp;
    % Tight tolerances + polishing: at the defaults (eps 1e-3, no polish) OSQP
    % returns ~1e-3-scale residue on components that are exactly zero at the
    % optimum -- which looks like real sub-threshold stim commands downstream.
    % OSQP renamed 'polish' to 'polishing' at v1.0; support both.
    osqpSettings = {'verbose', false, 'eps_abs', 1e-6, 'eps_rel', 1e-6};
    try
        P.prob.setup(P.H, zeros(P.m * P.Nu, 1), speye(P.m * P.Nu), lb, ub, ...
                     osqpSettings{:}, 'polish', true);
    catch
        P.prob = osqp;
        P.prob.setup(P.H, zeros(P.m * P.Nu, 1), speye(P.m * P.Nu), lb, ub, ...
                     osqpSettings{:}, 'polishing', true);
    end

    % Reference centering stack (per-tick subtract; see step path)
    P.rOffStack = repmat(P.yOff, P.N, 1);

    % Controller state (RAW u frame: zeros = stim off)
    P.xhat      = zeros(P.n,1);
    P.u_last    = zeros(P.m,1);

    % Observer. MPC_OPTS.useObserver = 0 gives pure model rollout (feedforward)
    % -- the historical silent-open-loop defect, so make it LOUD when chosen.
    P.useObserver = mpcOpts.useObserver ~= 0;
    if ~P.useObserver
        warning('mpc_test:ObserverDisabled', ...
                ['MPC_OPTS.useObserver = 0: the controller will IGNORE its ' ...
                 'measurement and run PURE FEEDFORWARD on the model. This is ' ...
                 'only valid for a deliberate open-loop experiment arm.']);
    end
    P.L = design_observer_gain(P.A, P.C);
    P.targetDefault = zeros(P.p, 1);
    P.tick = 0;
    P.debugLogPath = fullfile(pwd, 'mpc_test_debug.csv');
    P.debugLogInitialized = false;
    if isfield(assets, 'MPC_TARGET') && ~isempty(assets.MPC_TARGET)
        tmp = double(assets.MPC_TARGET(:));
        n = min(P.p, numel(tmp));
        P.targetDefault(1:n) = tmp(1:n);
    end
end


function opts = get_mpc_opts(assets)
% Tuning overrides. Priority: base-workspace MPC_OPTS > MPC_OPTS inside
% AllModels.mat > defaults. Defaults reproduce the pre-2026-08-15 behaviour
% exactly, so existing bench validations are unchanged.
    opts = struct('N', 20, 'Nu', 2, 'qWeight', 1, 'rWeight', 1, ...
                  'umin', 0, 'umax', 40, ...
                  'featureChannel', 0, ...   % 0 = legacy first-p mapping
                  'useObserver', 1);         % 0 = pure feedforward (loud warning)

    src = struct();
    if isfield(assets, 'MPC_OPTS') && isstruct(assets.MPC_OPTS)
        src = assets.MPC_OPTS;
    end
    try
        if evalin('base', 'exist(''MPC_OPTS'', ''var'')')
            baseOpts = evalin('base', 'MPC_OPTS');
            if isstruct(baseOpts)
                src = merge_struct(src, baseOpts);
            end
        end
    catch
    end

    fields = fieldnames(src);
    for i = 1:numel(fields)
        f = fields{i};
        % featureChannel and the weights may be VECTORS (MIMO, 2026-09-01):
        % one feature index per model output / per-output qWeight.
        vectorOk = any(strcmp(f, {'featureChannel', 'qWeight', 'rWeight'}));
        if isfield(opts, f) && isnumeric(src.(f)) && all(isfinite(src.(f))) ...
                && (isscalar(src.(f)) || (vectorOk && isvector(src.(f))))
            opts.(f) = double(src.(f));
        end
    end
    opts.N  = max(1, round(opts.N));
    opts.Nu = max(1, min(round(opts.Nu), opts.N));
    opts.featureChannel = max(0, round(opts.featureChannel));
    fprintf('mpc_test: N=%d Nu=%d qWeight=[%s] rWeight=[%s] u in [%g %g] featureChannel=[%s] observer=%d\n', ...
            opts.N, opts.Nu, strtrim(sprintf('%g ', opts.qWeight)), ...
            strtrim(sprintf('%g ', opts.rWeight)), opts.umin, opts.umax, ...
            strtrim(sprintf('%d ', opts.featureChannel)), opts.useObserver ~= 0);
end

function w = expand_weight(w, n, name)
% Scalar -> n-vector; n-vector passes through; anything else is a config error.
    w = double(w(:));
    if isscalar(w)
        w = repmat(w, n, 1);
    elseif numel(w) ~= n
        error('mpc_test:BadWeight', ...
              'MPC_OPTS.%s has %d entries; expected 1 or %d.', name, numel(w), n);
    end
end

function s = merge_struct(s, over)
    f = fieldnames(over);
    for i = 1:numel(f)
        s.(f{i}) = over.(f{i});
    end
end

function r = build_reference_stack(r_now, P)
% Turn a per-tick reference (p x 1) or preview matrix (p x K) into the stacked
% [pN x 1] vector the condensed QP expects. K < N pads by holding the last
% column (the trajectory continues at its final value); K > N crops.
%
% Disambiguation for the single-output plant (the production case): a 1 x K
% vector with K > 1 is a PREVIEW ROW, not a p-vector -- treating it as one
% would truncate it to its first element and silently disable preview exactly
% when it matters (the server sends refTraj(idx:stop,:)' = 1 x K when the
% reference CSV has one column).
    r_now = double(r_now);
    if isvector(r_now) && ~(P.p == 1 && numel(r_now) > 1)
        r_now = r_now(:);
        r_now = fit_length(r_now, P.p);
        r = repmat(r_now, P.N, 1);
        return;
    end
    if isvector(r_now)
        r_now = reshape(r_now, 1, []);   % 1 x K preview for the p = 1 plant
    end

    % p x K preview matrix. Row-fit to p, column-fit to N.
    if size(r_now, 1) ~= P.p
        tmp = zeros(P.p, size(r_now, 2));
        n = min(P.p, size(r_now, 1));
        tmp(1:n, :) = r_now(1:n, :);
        r_now = tmp;
    end
    K = size(r_now, 2);
    if K >= P.N
        r_now = r_now(:, 1:P.N);
    else
        r_now = [r_now, repmat(r_now(:, end), 1, P.N - K)];
    end
    r = r_now(:);
end


% =========================================================================
% Measurement mapping
% =========================================================================
function yk = feature_map(y_feat, P)
% Measurement mapping, configurable via MPC_OPTS.featureChannel:
%   featureChannel = 0 (default): legacy -- first p entries of the feature
%     vector are the measured outputs.
%   featureChannel = k > 0 (scalar): the model's single output is feature k.
%   featureChannel = [k1 .. kp] (vector, MIMO 2026-09-01): model output i is
%     feature channel k_i. Must have exactly p entries.

    yk = zeros(P.p,1);
    fc = P.featureChannel;
    if any(fc > 0)
        if numel(fc) == 1
            fc = [fc; zeros(P.p - 1, 1)];   % legacy scalar on a p=1 model
        end
        if numel(fc) ~= P.p
            error('mpc_test:BadFeatureChannel', ...
                  'MPC_OPTS.featureChannel has %d entries but the model has p=%d outputs.', ...
                  numel(fc), P.p);
        end
        if any(fc < 1)
            error('mpc_test:BadFeatureChannel', ...
                  'MPC_OPTS.featureChannel must be all-positive when mapping (got a 0/negative).');
        end
        if any(fc > numel(y_feat))
            error('mpc_test:BadFeatureChannel', ...
                  'MPC_OPTS.featureChannel = %d but only %d features arrive.', ...
                  max(fc), numel(y_feat));
        end
        yk = y_feat(fc(:));
        yk = yk(:);
        return;
    end
    n = min(P.p, numel(y_feat));
    yk(1:n) = y_feat(1:n);
end


% =========================================================================
% Reference source
% =========================================================================
function r0 = get_reference(P)
% Default:
%   uses a base-workspace variable named MPC_TARGET if it exists.
%   Otherwise defaults to zeros(p,1).
%
% Example in MATLAB:
%   MPC_TARGET = zeros(size(AllModels(10).sys.C,1),1);

    r0 = P.targetDefault;

    try
        if evalin('base', 'exist(''MPC_TARGET'', ''var'')')
            tmp = evalin('base', 'MPC_TARGET');
            tmp = double(tmp(:));
            n = min(P.p, numel(tmp));
            r0(1:n) = tmp(1:n);
        end
    catch
        % leave zero target on any workspace/eval issue
    end
end


% =========================================================================
% Debug logging / safety helpers
% =========================================================================
function write_debug_log(P, y_feat, yk, q)
    if P.tick > 25
        return;
    end

    try
        mode = 'a';
        if ~P.debugLogInitialized || P.tick == 1
            mode = 'w';
        end

        fid = fopen(P.debugLogPath, mode);
        if fid < 0
            return;
        end
        cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>

        if strcmp(mode, 'w')
            fprintf(fid, 'tick,y_feat0,yk0,q0,q_norm_inf\n');
        end

        y0 = first_or_zero(y_feat);
        yk0 = first_or_zero(yk);
        q0 = first_or_zero(q);
        qInf = max(abs(q));
        fprintf(fid, '%d,%.9g,%.9g,%.9g,%.9g\n', P.tick, y0, yk0, q0, qInf);
    catch
        % Debug logging is best-effort only.
    end
end

function x = sanitize_vector(x, limit)
    x = double(x(:));
    bad = ~isfinite(x);
    if any(bad)
        x(bad) = 0;
    end
    x = min(max(x, -limit), limit);
end

function v = first_or_zero(x)
    if isempty(x)
        v = 0;
    else
        v = x(1);
    end
end


% =========================================================================
% Controller assets / model loading
% =========================================================================
function assets = load_controller_assets()
    assets = struct();

    if evalin('base', 'exist(''AllModels'', ''var'')')
        assets.AllModels = evalin('base', 'AllModels');
    else
        matPath = fullfile(pwd, 'AllModels.mat');
        if ~isfile(matPath)
            error('mpc_test:MissingAllModels', ...
                  ['AllModels was not found in the MATLAB base workspace, ' ...
                   'and AllModels.mat was not found in the working folder: %s'], ...
                  matPath);
        end

        % Load only the variables that exist: load() warns on missing names,
        % and MPC_TARGET / MPC_OPTS / MPC_MODEL_INDEX are all optional.
        inFile = who('-file', matPath);
        wanted = intersect({'AllModels', 'MPC_TARGET', 'MPC_OPTS', 'MPC_MODEL_INDEX'}, inFile);
        loaded = load(matPath, wanted{:});
        if ~isfield(loaded, 'AllModels')
            error('mpc_test:MissingAllModelsVar', ...
                  'AllModels.mat exists but does not contain a variable named AllModels.');
        end
        assets = loaded;
    end

    if evalin('base', 'exist(''MPC_TARGET'', ''var'')')
        assets.MPC_TARGET = evalin('base', 'MPC_TARGET');
    end
    if evalin('base', 'exist(''MPC_MODEL_INDEX'', ''var'')')
        assets.MPC_MODEL_INDEX = evalin('base', 'MPC_MODEL_INDEX');
    end
end

function idx = get_model_index(assets)
% Which AllModels slot to control from. Optional MPC_MODEL_INDEX (base
% workspace, or saved inside AllModels.mat) selects it; default 10 preserves
% the historical behaviour. NOTE: MPC_TARGET is the reference VALUE, not a
% model selector -- do not overload it.
    idx = 10;
    if isfield(assets, 'MPC_MODEL_INDEX') && ~isempty(assets.MPC_MODEL_INDEX)
        v = double(assets.MPC_MODEL_INDEX(1));
        if isfinite(v) && v >= 1 && v == round(v)
            idx = v;
        else
            error('mpc_test:BadModelIndex', ...
                  'MPC_MODEL_INDEX must be a positive integer (got %g).', v);
        end
    end
end

function sys = get_model_entry(AllModels, idx)
    if numel(AllModels) < idx || ~isfield(AllModels, 'sys')
        error('mpc_test:BadAllModels', ...
              'AllModels must contain at least %d entries with a .sys field.', idx);
    end

    sys = AllModels(idx).sys;
    if isempty(sys)
        error('mpc_test:EmptyModel', ...
              'AllModels(%d).sys is empty.', idx);
    end
    fprintf('mpc_test: controlling from AllModels(%d).sys\n', idx);
end

function [uOff, yOff] = get_model_offsets(sys, m, p)
% Operating point stored with the model by fit_sysid_from_capture (capture
% means, raw units). Zeros when absent (toy/legacy/ss models).
    uOff = zeros(m,1);
    yOff = zeros(p,1);
    if ~isstruct(sys)
        return;
    end
    if isfield(sys, 'uOffset') && ~isempty(sys.uOffset)
        v = double(sys.uOffset(:));
        if numel(v) ~= m || any(~isfinite(v))
            error('mpc_test:BadUOffset', ...
                  'sys.uOffset has %d entries; model has m=%d inputs.', numel(v), m);
        end
        uOff = v;
    end
    if isfield(sys, 'yOffset') && ~isempty(sys.yOffset)
        v = double(sys.yOffset(:));
        if numel(v) ~= p || any(~isfinite(v))
            error('mpc_test:BadYOffset', ...
                  'sys.yOffset has %d entries; model has p=%d outputs.', numel(v), p);
        end
        yOff = v;
    end
    if any(uOff ~= 0) || any(yOff ~= 0)
        fprintf('mpc_test: operating point uOffset=%s yOffset=%s\n', ...
                mat2str(uOff.', 4), mat2str(yOff.', 4));
    end
end

function ts = get_model_ts(sys)
    % Sample time carried by the model itself, NaN if it has none.
    ts = NaN;
    if isa(sys, 'ss')
        if sys.Ts > 0
            ts = double(sys.Ts);
        end
    elseif isstruct(sys) && isfield(sys, 'Ts') && ~isempty(sys.Ts)
        ts = double(sys.Ts);
    end
end

function [A, B, C, D] = unpack_model(sys, Ts)
    if isa(sys, 'ss')
        if sys.Ts == 0
            sys = c2d(sys, Ts);
        elseif abs(sys.Ts - Ts) > 1e-12
            sys = d2d(sys, Ts);
        end
        [A, B, C, D] = ssdata(sys);
        return;
    end

    if isstruct(sys) && all(isfield(sys, {'A', 'B', 'C', 'D'}))
        A = double(sys.A);
        B = double(sys.B);
        C = double(sys.C);
        D = double(sys.D);

        sysTs = NaN;
        if isfield(sys, 'Ts') && ~isempty(sys.Ts)
            sysTs = double(sys.Ts);
        end

        if ~isnan(sysTs) && sysTs ~= 0 && abs(sysTs - Ts) > 1e-12
            error('mpc_test:StructModelRateMismatch', ...
                  ['AllModels(10).sys is a numeric struct with Ts=%g s, ' ...
                   'but mpc_test expects %g s. Save the struct already ' ...
                   'discretized at the controller rate or provide an ss object.'], ...
                  sysTs, Ts);
        end
        return;
    end

    error('mpc_test:UnsupportedModelType', ...
          ['AllModels(10).sys must be either an ss object or a struct ' ...
           'containing A, B, C, and D fields.']);
end


% =========================================================================
% Observer gain
% =========================================================================
function L = design_observer_gain(A, C)
% Returns the correction gain L used as
%     xhat = x_pred + L * (yk - y_pred)
% i.e. the current-estimator (filtering) form, whose error dynamics are
%     e_{k+1} = (I - L*C) * A * e.
%
% 2026-07-23: this function previously fell back to L = zeros(n,p) whenever
% place() threw. place() lives in the Control System Toolbox, which is NOT
% installed on this machine, so the fallback was always taken and the observer
% was silently inert -- the MPC ignored its measurement entirely and ran fully
% open-loop. The symptom was a control output that converged to a constant and
% stopped tracking the feature vector. A toolbox-free steady-state Kalman gain
% is now computed instead, and a zero gain is only ever returned as a last
% resort, loudly.

    n = size(A,1);
    p = size(C,1);

    % Preferred: explicit pole placement, when the toolbox is present.
    try
        obsPoles = linspace(0.35, 0.75, n);
        L = place(A.', C.', obsPoles).';
        return;
    catch
        % Fall through to the dependency-free path below.
    end

    % Dependency-free steady-state Kalman gain via Riccati iteration.
    % Q/R set the observer's trust in the model versus the measurement. R = I
    % with Q = qScale*I gives a moderately fast observer; raise qScale to trust
    % the measurement more (faster, noisier), lower it to trust the model more.
    qScale = 1e-2;
    L = kalman_gain_iterative(A, C, qScale * eye(n), eye(p));

    if isempty(L)
        warning('mpc_test:ObserverGainFailed', ...
                ['Could not compute an observer gain; falling back to L = 0. ' ...
                 'The controller will run OPEN LOOP and ignore its measurement.']);
        L = zeros(n, p);
        return;
    end

    % Verify the estimator is actually stable before handing it back.
    errPoles = abs(eig((eye(n) - L * C) * A));
    if any(errPoles >= 1)
        warning('mpc_test:ObserverUnstable', ...
                ['Computed observer has |pole| = %.4f >= 1; falling back to L = 0. ' ...
                 'The controller will run OPEN LOOP.'], max(errPoles));
        L = zeros(n, p);
    end
end

function L = kalman_gain_iterative(A, C, Q, R)
% Steady-state Kalman filter gain without the Control System Toolbox.
%
% Iterates the discrete Riccati recursion on the one-step prediction covariance
%     Pp <- A*(Pp - Pp*C'*(C*Pp*C' + R)^-1*C*Pp)*A' + Q
% to convergence, then forms the filtering gain
%     L = Pp*C'*(C*Pp*C' + R)^-1.
% Iterating is used rather than a direct DARE solve because it needs nothing but
% matrix arithmetic and degrades gracefully: if it fails to converge we return
% empty and the caller decides.

    n = size(A,1);
    Pp = eye(n);
    L = [];

    for iter = 1:5000
        S = C * Pp * C.' + R;
        if rcond(S) < 1e-12
            return;     % ill-conditioned innovation covariance
        end
        K = (Pp * C.') / S;                       % filtering gain this iteration
        Pf = Pp - K * C * Pp;                     % filtered covariance
        Pnext = A * Pf * A.' + Q;
        Pnext = (Pnext + Pnext.') / 2;            % keep it symmetric

        if ~all(isfinite(Pnext(:)))
            return;
        end

        delta = norm(Pnext - Pp, 'fro') / max(1, norm(Pp, 'fro'));
        Pp = Pnext;
        L = K;
        if delta < 1e-12
            break;
        end
    end
end


% =========================================================================
% Prediction matrices
% Predict y(k+1) ... y(k+N) from x(k) and U = [u(k); ...; u(k+N-1)]
% =========================================================================
function [F, G] = predmat_y(A, B, C, D, N)
    n = size(A,1);
    m = size(B,2);
    p = size(C,1);

    F = zeros(p*N, n);
    G = zeros(p*N, m*N);

    Apow = eye(n);

    for i = 1:N
        Apow = A * Apow;  % A^i
        rowi = (i-1)*p + (1:p);

        % x -> y(k+i)
        F(rowi, :) = C * Apow;

        % U -> y(k+i)
        for j = 1:i
            colj = (j-1)*m + (1:m);

            if i == j
                G(rowi, colj) = C * (A^(i-j)) * B + D;
            else
                G(rowi, colj) = C * (A^(i-j)) * B;
            end
        end
    end
end


% =========================================================================
% Hold-last mapping
% z = [u0; u1; ...; u_{Nu-1}]
% U_full = [u0; u1; ...; u_{Nu-1}; u_{Nu-1}; ...]
% =========================================================================
function S = hold_last_map(N, Nu, m)
    S = zeros(m*N, m*Nu);

    for i = 1:N
        j = min(i, Nu);
        rows = (i-1)*m + (1:m);
        cols = (j-1)*m + (1:m);
        S(rows, cols) = eye(m);
    end
end


% =========================================================================
% Utility
% =========================================================================
function x = fit_length(x, n)
    if numel(x) < n
        x = [x; zeros(n - numel(x), 1)];
    elseif numel(x) > n
        x = x(1:n);
    end
end
