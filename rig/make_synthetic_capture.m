function make_synthetic_capture(outFile, respChannel, snr, noiseSeed, stimSeed, nU, nY)
%MAKE_SYNTHETIC_CAPTURE  Build a capture with a KNOWN response, for testing.
%
%   make_synthetic_capture('capture_synth.csv', 7, 3)
%
%   Writes a file in exactly the format matlab_controller_server's openloop mode
%   produces, except that output channel `respChannel` is a known second-order
%   response to stim channel 3 buried in noise at the given SNR. Every other
%   output channel is pure noise.
%
%   Purpose: prove that sweep_channels and fit_sysid_from_capture actually
%   DETECT a response when one exists. A negative control (real capture, no
%   stim effect) only shows they do not hallucinate; it does not show they can
%   find anything. Both directions have to be checked before trusting a
%   go/no-go decision made at the rig under time pressure.
%
%   Ground truth: poles 0.90 and 0.70, one-tick input delay, so a correct
%   pipeline should recover |corr| well above 0.1 on respChannel and near zero
%   everywhere else.

    if nargin < 1 || isempty(outFile),     outFile = 'capture_synth.csv'; end
    if nargin < 2 || isempty(respChannel), respChannel = 7;               end
    if nargin < 3 || isempty(snr),         snr = 3;                       end
    % Separate seeds so a second record can be generated with independent noise.
    % Note that 'prbs' is a deterministic LFSR and ignores the seed -- stimSeed
    % only changes the excitation for the 'multilevel' kind. A second record
    % therefore differs in its noise realisation, which is enough to exercise
    % crossval_model, but is a weaker test than genuinely different excitation.
    if nargin < 4 || isempty(noiseSeed),   noiseSeed = 20260730;          end
    if nargin < 5 || isempty(stimSeed),    stimSeed = 12345;              end
    % Stim (u) and recording (y) widths are independent in production (8 pairs
    % vs 16/32 channels); the historical fixture conflated them at 16/16, which
    % stays the default so the committed fixtures regenerate byte-identical.
    % An 8u x 32y fixture exercises the 32-ch offline chain with a response
    % planted above channel 16 (2026-08-29).
    if nargin < 6 || isempty(nU),          nU = 16;                       end
    if nargin < 7 || isempty(nY),          nY = 16;                       end
    if respChannel > nY
        error('make_synthetic_capture:BadRespChannel', ...
              'respChannel %d > nY %d.', respChannel, nY);
    end

    nTicks = 3000;

    U = make_excitation('prbs', nTicks, nU, ...
                        struct('uMin', 0, 'uMax', 10, 'clockTicks', 5, ...
                               'seed', stimSeed, 'activeChannels', 3));

    % Second-order plant, poles 0.9 / 0.7, driven by stim channel 3.
    a1 = -(0.9 + 0.7);
    a2 =  0.9 * 0.7;
    b  = 0.5;
    u  = U(:, 3);
    y  = zeros(nTicks, 1);
    for k = 3:nTicks
        % u(k-2) not u(k-1): one tick of transport lag plus the model's own
        % one-sample input delay, matching the real path.
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

    fprintf(['make_synthetic_capture: wrote %s\n' ...
             '  %d ticks, stim on channel 3, response on OUTPUT CHANNEL %d\n' ...
             '  true poles 0.9000 / 0.7000, SNR %g\n'], ...
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
