function u = mpc_step(x)
% MPC_STEP  Conservative saline-test ramp generator for closed-loop integration.
%
% Signature must match C++ MATLAB Engine call:
%   u = mpc_step(x)
%
% Behavior:
% - Returns one output amplitude per input element.
% - Uses persistent state so amplitudes ramp up/down smoothly over time.
% - Clamps values to a conservative "safe" range for bench/saline testing.
%
% Tune these constants below before in vivo use.

    %#ok<INUSD>  % x is currently unused for this saline ramp profile.

    % -------- User-tunable conservative saline-test limits --------
    AMP_MIN = 0;       % Lower amplitude bound (matches C++ clamp lower bound).
    AMP_MAX = 50;    % Conservative upper bound for saline bench tests.
    STEP_UP = 5;       % Increment per update while ramping upward.
    STEP_DOWN = 5;     % Decrement per update while ramping downward.
    HOLD_UPDATES = 5;  % Number of calls between each amplitude step.
    % -------------------------------------------------------------

    n = numel(x);
    if n == 0
        u = zeros(0, 1);
        return;
    end

    persistent amp direction holdCounter initialized nPrev
    if isempty(initialized) || nPrev ~= n
        amp = zeros(n, 1);
        direction = 1;   % +1 ramp up, -1 ramp down
        holdCounter = 0;
        initialized = true;
        nPrev = n;
    end

    holdCounter = holdCounter + 1;
    if holdCounter >= HOLD_UPDATES
        holdCounter = 0;

        if direction > 0
            amp = amp + STEP_UP;
            if any(amp >= AMP_MAX)
                amp = min(amp, AMP_MAX);
                direction = -1;
            end
        else
            amp = amp - STEP_DOWN;
            if any(amp <= AMP_MIN)
                amp = max(amp, AMP_MIN);
                direction = 1;
            end
        end
    end

    % Ensure safe bounds regardless of numerical drift.
    amp = min(max(amp, AMP_MIN), AMP_MAX);

    % Return column vector of doubles (expected by MATLAB Engine bridge).
    u = double(amp);
end

