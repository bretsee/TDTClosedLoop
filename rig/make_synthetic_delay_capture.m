function truth = make_synthetic_delay_capture(outFile, deadTicks, seed)
%MAKE_SYNTHETIC_DELAY_CAPTURE  Capture with a KNOWN row-frame dead time.
%
%   truth = make_synthetic_delay_capture('capture_synth_delay.csv', 3)
%
%   Writes a capture in the server format (tick,seq,t_ms,u1..u8,y1,y2) where
%   output y1 answers stim pairs 4 and 6 through a first-order plant with a
%   dead time of exactly `deadTicks` ticks IN THE CAPTURE'S ROW FRAME: the
%   command in row k first moves y in row k + deadTicks. That is the frame the
%   controllers live in (x(k+1) = A x(k) + B u(k), y(k) = C x(k) gives a dead
%   time of 1), so a correct fitter + export must reproduce it with
%   inputDelayTicks = deadTicks - 1.
%
%   Used by bench_test_reference_mpc ('delay-state realization') to prove the
%   2026-10-09 fitter change end to end: fit -> delay states -> row-frame
%   free-run best at shift 0. rig/check_dead_time.py scores the same thing on
%   rig captures.
%
%   Ground truth returned: pole 0.8, b = [1e-6 4e-7] V/uA, yOffset 5e-5 V,
%   held multilevel excitation (5-tick hold, levels 0/10/20/30 uA).

    if nargin < 1 || isempty(outFile),   outFile = 'capture_synth_delay.csv'; end
    if nargin < 2 || isempty(deadTicks), deadTicks = 3;                      end
    if nargin < 3 || isempty(seed),      seed = 20261009;                    end

    rng(seed);
    N = 12000;
    a = 0.8;
    b = [1e-6 4e-7];
    yOff = 5e-5;
    noise = 2e-6;

    U = zeros(N, 2);
    lvl = [0 0];
    for k = 1:N
        if mod(k - 1, 5) == 0
            lvl = 10 * (randi(4, 1, 2) - 1);   % 0/10/20/30 uA, 5-tick hold
        end
        U(k, :) = lvl;
    end

    % Row frame: x(k+1) = a x(k) + b u(k - deadTicks + 1), y(k) = yOff + x(k).
    % Then u(k) first appears in x(k+deadTicks) = y(k+deadTicks).
    x = 0;
    Y = zeros(N, 1);
    for k = 1:N
        Y(k) = yOff + x + noise * randn;
        j = k - deadTicks + 1;
        uk = [0 0];
        if j >= 1, uk = U(j, :); end
        x = a * x + b * uk.';
    end

    fid = fopen(outFile, 'w');
    if fid < 0
        error('make_synthetic_delay_capture:CannotWrite', 'Could not open %s.', outFile);
    end
    cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
    fprintf(fid, 'tick,seq,t_ms,u1,u2,u3,u4,u5,u6,u7,u8,y1,y2\n');
    for k = 1:N
        u8 = zeros(1, 8);
        u8(4) = U(k, 1); u8(6) = U(k, 2);
        fprintf(fid, '%d,%d,%.1f', k, k, 10 * (k - 1));
        fprintf(fid, ',%.9g', u8);
        fprintf(fid, ',%.9g,0\n', Y(k));
    end

    truth = struct('deadTicks', deadTicks, 'a', a, 'b', b, 'yOffset', yOff, ...
                   'useInputs', [4 6], 'useOutputs', 1, 'N', N, 'file', outFile);
end
