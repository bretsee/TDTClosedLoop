function make_synthetic_impulse_capture(outFile, respChannel, snr, noiseSeed, nU, nY)
%MAKE_SYNTHETIC_IMPULSE_CAPTURE  Impulse-probe capture with a KNOWN response.
%
%   make_synthetic_impulse_capture('capture_synth_impulse.csv', 7, 3)
%
%   The impulse-excitation twin of make_synthetic_capture: same file format,
%   same u(k-2) drive (one tick of transport lag plus the model's own input
%   delay), same per-channel LCG noise -- but the excitation is
%   make_excitation('impulse', ...) on stim channel 3, exactly the probe
%   DEPLOYMENT_PLAN_INVIVO.md step 1 runs.
%
%   Purpose: a committed positive-control fixture for rig/fit_impulse_model.py.
%   The 2026-08-15 validation ("gain/delay/linearity recovered exactly") ran on
%   an ad-hoc synthetic that was never checked in, so the success path could not
%   be re-verified. This regenerates it reproducibly. Expected verdict: output
%   channel `respChannel` RESPONDING (>=3x null floor), all others below floor;
%   plant is linear so linearity R^2 should be ~1.
%
%   The plant here uses TISSUE-SPEED poles 0.50/0.20 (peak ~2-3 ticks, settled
%   within ~5 ticks, matching the acute-array 23 ms settle), NOT the 0.90/0.70
%   of make_synthetic_capture. fit_impulse_model's null floor is built from
%   "pulse-free" ticks 31..48 after each pulse, and its +30-tick null windows
%   reach into the NEXT pulse's response -- a pole-0.9 plant (time constant
%   ~100 ms) therefore leaks real signal into the null and caps SNR near 1.4x
%   regardless of noise level. That is a designed-in assumption of the tool
%   (response dead well inside the 500 ms gap), which real tissue satisfies
%   and the slow PRBS fixture plant does not.
%
%   Ground truth: poles 0.5000/0.2000, kernel peak 0.5*amp at lag +2, single-
%   tick pulses cycling [10 20 30 40] every 51 ticks (6000 ticks -> ~117
%   pulses, ~29 per amplitude).

    if nargin < 1 || isempty(outFile),     outFile = 'capture_synth_impulse.csv'; end
    if nargin < 2 || isempty(respChannel), respChannel = 7;                       end
    if nargin < 3 || isempty(snr),         snr = 3;                               end
    if nargin < 4 || isempty(noiseSeed),   noiseSeed = 20260817;                  end
    % Independent stim/recording widths; 16/16 defaults keep the committed
    % fixture byte-identical (see make_synthetic_capture, 2026-08-29).
    if nargin < 5 || isempty(nU),          nU = 16;                              end
    if nargin < 6 || isempty(nY),          nY = 16;                              end
    if respChannel > nY
        error('make_synthetic_impulse_capture:BadRespChannel', ...
              'respChannel %d > nY %d.', respChannel, nY);
    end

    nTicks = 6000;

    U = make_excitation('impulse', nTicks, nU, ...
                        struct('uMin', 0, 'uMax', 40, 'activeChannels', 3));

    % Second-order plant, poles 0.5 / 0.2 (tissue-speed -- see header), driven
    % by stim channel 3.
    a1 = -(0.5 + 0.2);
    a2 =  0.5 * 0.2;
    b  = 0.5;
    u  = U(:, 3);
    y  = zeros(nTicks, 1);
    for k = 3:nTicks
        y(k) = -a1 * y(k-1) - a2 * y(k-2) + b * u(k-2);
    end

    sig = std(y);
    rs = noiseSeed;
    Y = zeros(nTicks, nY);
    for ch = 1:nY
        [rs, n] = local_randn(rs, nTicks);
        if ch == respChannel
            Y(:, ch) = 250 + y + (sig / snr) * n;   % MAV-like positive offset
        else
            Y(:, ch) = 250 + sig * n;
        end
    end

    tick = (1:nTicks).';
    seq  = tick;
    tms  = (tick - 1) * 10;

    names = [{'tick', 'seq', 't_ms'}, ...
             arrayfun(@(i) sprintf('u%d', i), 1:nU, 'UniformOutput', false), ...
             arrayfun(@(i) sprintf('y%d', i), 1:nY, 'UniformOutput', false)];
    T = array2table([tick, seq, tms, U, Y], 'VariableNames', names);
    writetable(T, outFile);

    fprintf(['make_synthetic_impulse_capture: wrote %s\n' ...
             '  %d ticks, impulse probe on channel 3, response on OUTPUT CHANNEL %d\n' ...
             '  true poles 0.5000 / 0.2000, SNR %g\n'], ...
            outFile, nTicks, respChannel, snr);
end

function [rs, n] = local_randn(rs, count)
    % Box-Muller on a small LCG, so the test is reproducible and does not touch
    % the global RNG state.
    n = zeros(count, 1);
    for i = 1:count
        [rs, u1] = local_rand(rs);
        [rs, u2] = local_rand(rs);
        u1 = max(u1, 1e-12);
        n(i) = sqrt(-2 * log(u1)) * cos(2 * pi * u2);
    end
end

function [rs, r] = local_rand(rs)
    rs = mod(16807 * rs, 2147483647);
    r = (rs - 1) / 2147483646;
end
