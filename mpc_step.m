function u = mpc_step(x)
% MPC_STEP  Conservative multi-channel saline-test pattern generator.
%
% Signature must match C++ MATLAB Engine call:
%   u = mpc_step(x)
%
% Behavior:
% - Returns one output amplitude per input element.
% - Generates a distinct ramp/triangle-wave phase for each output channel.
% - Clamps values to a conservative "safe" range for bench/saline testing.
%
% Tune these constants below before in vivo use.

    %#ok<INUSD>  % x is currently unused for this saline ramp profile.

    % -------- User-tunable conservative saline-test limits --------
    AMP_MIN = 0;       % Lower amplitude bound (matches C++ clamp lower bound).
    AMP_MAX = 50;      % Conservative upper bound for saline bench tests.
    STEP_UP = 5;       % Increment per update while ramping upward.
    STEP_DOWN = 5;     % Decrement per update while ramping downward.
    HOLD_UPDATES = 5;  % Number of calls between each amplitude step.
    CHANNEL_PHASE_STEPS = 2;  % Offset each channel by this many ramp steps.
    % -------------------------------------------------------------

    n = numel(x);
    if n == 0
        u = zeros(0, 1);
        return;
    end

    persistent tick initialized nPrev rampStepCount
    if isempty(initialized) || nPrev ~= n
        tick = 0;
        rampStepCount = floor((AMP_MAX - AMP_MIN) / STEP_UP);
        if rampStepCount < 1
            rampStepCount = 1;
        end
        initialized = true;
        nPrev = n;
    end

    tick = tick + 1;

    amp = zeros(n, 1);
    for ch = 1:n
        channelTick = floor((tick - 1) / HOLD_UPDATES) + (ch - 1) * CHANNEL_PHASE_STEPS;
        phase = mod(channelTick, 2 * rampStepCount);

        if phase < rampStepCount
            value = AMP_MIN + phase * STEP_UP;
        else
            downPhase = phase - rampStepCount;
            value = AMP_MAX - downPhase * STEP_DOWN;
        end

        amp(ch) = value;
    end

    % Ensure safe bounds regardless of numerical drift.
    amp = min(max(amp, AMP_MIN), AMP_MAX);

    % Return column vector of doubles (expected by MATLAB Engine bridge).
    u = double(amp);
end
