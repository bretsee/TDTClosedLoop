function u = mpc_test(y_feat)
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
% Reset:
%   mpc_test([])

persistent P

if nargin == 0 || isempty(y_feat)
    P = [];
    u = [];
    return;
end

y_feat = double(y_feat(:));

if isempty(P)
    P = init_controller(numel(y_feat));
end

% Keep input length fixed after first call.
y_feat = fit_length(y_feat, P.ny_feat);

% Map preprocessed acquisition vector -> controller measurement y_k
yk = feature_map(y_feat, P);   % size = [p x 1]

% State estimate update using last applied input
x_pred = P.A * P.xhat + P.B * P.u_last;

if P.useObserver
    y_pred = P.C * x_pred + P.D * P.u_last;
    P.xhat = x_pred + P.L * (yk - y_pred);
else
    P.xhat = x_pred;
end

% Reference over horizon
r0 = get_reference(P);        % size = [p x 1]
r  = repmat(r0, P.N, 1);      % size = [pN x 1]

% Linear term for condensed QP
fx = P.F * P.xhat;
q  = P.GS.' * (P.Qbar * (fx - r));

% Solve QP
P.prob.update('q', full(q));
res = P.prob.solve();

if isempty(res.x) || any(~isfinite(res.x))
    % Fail-safe: hold previous command
    u = P.u_last;
else
    z = res.x;
    u = z(1:P.m);
end

% Clamp and store
u = min(max(u, P.umin), P.umax);
P.u_last = u;
end


% =========================================================================
% Initialization
% =========================================================================
function P = init_controller(ny_feat)

    % -----------------------------
    % EDIT THESE FIRST
    % -----------------------------
    P.controlFs = 100;          % desired control/update rate (Hz)

    % Load your model
    if ~evalin('base', 'exist(''AllModels'', ''var'')')
        error('mpc_test:MissingAllModels', ...
              'AllModels was not found in the MATLAB base workspace.');
    end
    sys = AllModels(10).sys;

    % Discretize / resample model to the controller rate
    Ts = 1 / P.controlFs;
    if sys.Ts == 0
        sys = c2d(sys, Ts);
    elseif abs(sys.Ts - Ts) > 1e-12
        sys = d2d(sys, Ts);
    end

    [A,B,C,D] = ssdata(sys);

    P.A = full(A);
    P.B = full(B);
    P.C = full(C);
    P.D = full(D);

    P.n = size(P.A,1);
    P.m = size(P.B,2);
    P.p = size(P.C,1);

    % MPC horizons
    P.N  = 20;
    P.Nu = 2;

    % Weights
    Q = eye(P.p);
    R = eye(P.m);

    % Input constraints
    P.umin = zeros(P.m,1);
    P.umax = 40 * ones(P.m,1);

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

    % Bound constraints on z = [u0; u1; ...; u_{Nu-1}]
    lb = repmat(P.umin, P.Nu, 1);
    ub = repmat(P.umax, P.Nu, 1);

    P.prob = osqp;
    P.prob.setup(P.H, zeros(P.m * P.Nu, 1), speye(P.m * P.Nu), lb, ub, ...
                 'verbose', false);

    % Controller state
    P.xhat      = zeros(P.n,1);
    P.u_last    = zeros(P.m,1);

    % Observer
    P.useObserver = true;
    P.L = design_observer_gain(P.A, P.C);
end


% =========================================================================
% Measurement mapping
% =========================================================================
function yk = feature_map(y_feat, P)
% Default mapping:
%   take the first p entries of the preprocessed feature vector and interpret them
%   as the measured outputs for the model.
%
% Change this function once you know your real preprocessing/features.

    yk = zeros(P.p,1);
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

    r0 = zeros(P.p,1);

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
% Observer gain
% =========================================================================
function L = design_observer_gain(A, C)
    n = size(A,1);
    p = size(C,1);

    try
        obsPoles = linspace(0.35, 0.75, n);
        L = place(A.', C.', obsPoles).';
    catch
        % Fallback: no correction if pole placement fails
        L = zeros(n, p);
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
