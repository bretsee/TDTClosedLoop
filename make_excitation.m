function U = make_excitation(kind, nTicks, m, opts)
%MAKE_EXCITATION  Open-loop stim excitation sequences for system identification.
%
%   U = make_excitation(kind, nTicks, m, opts)
%
%   Returns U, an [nTicks x m] matrix of stim commands in engineering units,
%   clamped to [opts.uMin, opts.uMax]. Row k is the command for control tick k
%   at the 100 Hz control rate.
%
%   kind:
%     'prbs'       maximum-length binary sequence, two levels. Best default for
%                  a first linear model: flat spectrum up to ~1/(2*clockTicks).
%     'multilevel' random level held for clockTicks. Better than binary if you
%                  suspect amplitude nonlinearity, since it visits interior levels.
%     'steps'      staircase up then down. Easy to read by eye; gives DC gain and
%                  settling time directly. Poor spectral coverage on its own.
%     'chirp'      linear frequency sweep. Good for seeing bandwidth directly.
%     'impulse'    isolated single-tick pulses separated by long quiet gaps,
%                  cycling through opts.pulseAmps. The direct probe for the
%                  impulse response: average the feature aligned on each pulse
%                  and you have the kernel, gain, and delay with no model in
%                  between (rig/fit_impulse_model.py does exactly that). Also
%                  fits fine with fit_sysid_from_capture (ARX does not care).
%                  The acute-array analysis says the tissue settles in ~23 ms,
%                  so the default 50-tick (500 ms) gap makes each pulse an
%                  independent trial with generous baseline on both sides.
%
%   opts fields (all optional):
%     uMin        lower command bound                        (default 0)
%     uMax        upper command bound                        (default 40)
%     clockTicks  ticks each PRBS/multilevel value is held   (default 5)
%     nLevels     number of levels for 'multilevel'          (default 4)
%     holdTicks   ticks per step for 'steps'                 (default 50)
%     f0, f1      chirp start/end frequency in Hz            (default 0.2, 20)
%     pulseAmps   amplitudes cycled through for 'impulse'    (default [10 20 30 40])
%     gapTicks    quiet ticks between pulses for 'impulse'   (default 50)
%     gapJitterMeanTicks  extra RANDOM gap added after every impulse pulse,
%                 drawn per pulse from a geometric distribution on {1,2,...}
%                 with this mean (0 = off, the legacy strictly periodic train).
%                 Geometric = the discrete memoryless distribution: flat hazard,
%                 so the train has no rhythm to entrain to and no spectral comb,
%                 while staying strictly positive and integer-tick by
%                 construction. Generation is one uniform + one log per pulse
%                 (inversion), the cheapest strictly-positive draw available
%                 without a toolbox. Mean pulse period becomes
%                 (gapTicks + 1 + gapJitterMeanTicks) ticks.        (default 0)
%     schedule    'interleaved' (default): all active channels share the whole
%                 record, staggered + jittered, with a crossGuardTicks exclusion
%                 between any two pulses on ANY channels. Time-efficient (8 pairs
%                 in one record) but cross-pair spacing averages only ~7 ticks.
%                 'sequential': the record is split into contiguous per-channel
%                 BLOCKS, in active-channel order -- each channel's whole train
%                 lives in its own block, so channels are fully independent (no
%                 cross-pair proximity at all, no guard shifting, jitter mean
%                 exact). Costs numel(active)x the ticks for the same per-channel
%                 trial count.
%     crossGuardTicks  interleaved only: no two pulses on any channels within
%                 this many ticks of each other (conflicts shift forward)
%                                                                    (default 2)
%     seed        RNG seed for reproducibility               (default 12345)
%     decorrelate shift channels apart so inputs are not collinear (default true)
%     activeChannels  channel indices allowed to move; every other channel is
%                 held at uMin for the whole record          (default all)
%
%   activeChannels exists because the default is to excite ALL m channels at
%   once. That is right for identifying the full MIMO map, but it is the wrong
%   first run at the rig: it delivers m simultaneous stim trains, and it asks a
%   single-output fit to resolve m inputs at once. Set activeChannels to one
%   pair for the first capture, so "does stim move this feature at all" is
%   answered by an unambiguous single-input record. Held channels sit at uMin,
%   so with the usual uMin = 0 they deliver nothing. The fitter's default
%   useInputs keeps only channels that actually moved, so a single-pair capture
%   needs no extra configuration downstream.
%
%   Deliberately dependency-free: no System Identification Toolbox, no Signal
%   Processing Toolbox, no Statistics Toolbox. This runs on the rig machine
%   during acquisition, where a missing-toolbox error would cost a session.
%
%   Design notes for choosing clockTicks:
%     The control rate is 100 Hz, so a PRBS held for clockTicks samples has
%     usable energy roughly from 1/(nBits*clockTicks*0.01) Hz up to
%     1/(2*clockTicks*0.01) Hz. clockTicks=5 gives ~0.04-10 Hz, which brackets
%     the evoked-response dynamics we expect. Do not use clockTicks=1: it puts
%     nearly all the energy above the plant bandwidth and identifies noise.

    if nargin < 4 || isempty(opts)
        opts = struct();
    end
    opts = set_default(opts, 'uMin', 0);
    opts = set_default(opts, 'uMax', 40);
    opts = set_default(opts, 'clockTicks', 5);
    opts = set_default(opts, 'nLevels', 4);
    opts = set_default(opts, 'holdTicks', 50);
    opts = set_default(opts, 'f0', 0.2);
    opts = set_default(opts, 'f1', 20);
    opts = set_default(opts, 'pulseAmps', [10 20 30 40]);
    opts = set_default(opts, 'gapTicks', 50);
    opts = set_default(opts, 'gapJitterMeanTicks', 0);
    opts = set_default(opts, 'schedule', 'interleaved');
    opts = set_default(opts, 'crossGuardTicks', 2);
    opts = set_default(opts, 'seed', 12345);
    opts = set_default(opts, 'decorrelate', true);
    opts = set_default(opts, 'activeChannels', []);

    kind = lower(string(kind));
    nTicks = max(1, round(nTicks));
    m = max(1, round(m));

    switch kind
        case "prbs"
            U = build_prbs(nTicks, m, opts);
        case "multilevel"
            U = build_multilevel(nTicks, m, opts);
        case "steps"
            U = build_steps(nTicks, m, opts);
        case "chirp"
            U = build_chirp(nTicks, m, opts);
        case "impulse"
            U = build_impulse(nTicks, m, opts);
        otherwise
            error('make_excitation:UnknownKind', ...
                  'Unknown excitation kind "%s". Use prbs, multilevel, steps, chirp, or impulse.', kind);
    end

    U = min(max(U, opts.uMin), opts.uMax);

    % Hold every non-active channel at uMin. Applied after clamping so the held
    % value is exactly uMin and cannot be reintroduced by the clamp. Validated
    % loudly: a typo here would silently stim a channel the operator believes is
    % off, which is a safety matter and not merely a modelling one.
    if ~isempty(opts.activeChannels)
        active = unique(round(opts.activeChannels(:)));
        if any(active < 1) || any(active > m)
            error('make_excitation:BadActiveChannels', ...
                  'activeChannels must be within 1..%d; got [%s].', ...
                  m, strtrim(sprintf('%d ', active)));
        end
        held = setdiff(1:m, active);
        U(:, held) = opts.uMin;
        fprintf(['make_excitation: %d of %d channels active [%s]; ' ...
                 'the other %d held at uMin=%g.\n'], ...
                numel(active), m, strtrim(sprintf('%d ', active)), ...
                numel(held), opts.uMin);
    end
end

% =========================================================================

function U = build_prbs(nTicks, m, opts)
    % Two-level maximum-length sequence from an LFSR, held clockTicks per bit.
    nBits = 9;                        % 2^9-1 = 511 bits before repeating
    seqLen = 2^nBits - 1;
    bits = lfsr_sequence(nBits, seqLen);

    lo = opts.uMin;
    hi = opts.uMax;

    U = zeros(nTicks, m);
    for ch = 1:m
        shift = channel_shift(ch, m, seqLen, opts.decorrelate);
        for k = 1:nTicks
            bitIdx = mod(floor((k - 1) / opts.clockTicks) + shift, seqLen) + 1;
            if bits(bitIdx)
                U(k, ch) = hi;
            else
                U(k, ch) = lo;
            end
        end
    end
end

function U = build_multilevel(nTicks, m, opts)
    levels = linspace(opts.uMin, opts.uMax, max(2, opts.nLevels));
    rs = local_rng(opts.seed);

    U = zeros(nTicks, m);
    nHolds = ceil(nTicks / opts.clockTicks);
    for ch = 1:m
        vals = zeros(nHolds, 1);
        prev = NaN;
        for h = 1:nHolds
            % Avoid repeating the previous level: a repeat wastes a hold period
            % without adding an excitation edge.
            pick = prev;
            guard = 0;
            while (isnan(prev) || pick == prev) && guard < 20
                [rs, r] = local_rand(rs);
                pick = levels(min(numel(levels), 1 + floor(r * numel(levels))));
                guard = guard + 1;
                if isnan(prev)
                    break;
                end
            end
            vals(h) = pick;
            prev = pick;
        end
        for k = 1:nTicks
            U(k, ch) = vals(floor((k - 1) / opts.clockTicks) + 1);
        end
    end
end

function U = build_steps(nTicks, m, opts)
    levels = linspace(opts.uMin, opts.uMax, max(2, opts.nLevels));
    ladder = [levels, fliplr(levels(1:end-1))];

    U = zeros(nTicks, m);
    for ch = 1:m
        offset = 0;
        if opts.decorrelate && m > 1
            offset = round((ch - 1) * opts.holdTicks / m);
        end
        for k = 1:nTicks
            idx = mod(floor((k - 1 + offset) / opts.holdTicks), numel(ladder)) + 1;
            U(k, ch) = ladder(idx);
        end
    end
end

function U = build_chirp(nTicks, m, opts)
    Ts = 0.01;                                  % 100 Hz control rate
    t = (0:nTicks-1)' * Ts;
    T = max(Ts, t(end));
    mid = (opts.uMin + opts.uMax) / 2;
    amp = (opts.uMax - opts.uMin) / 2;

    U = zeros(nTicks, m);
    for ch = 1:m
        phase = 0;
        if opts.decorrelate && m > 1
            phase = 2 * pi * (ch - 1) / m;
        end
        % Linear sweep: instantaneous freq goes f0 -> f1 across the record.
        inst = opts.f0 * t + (opts.f1 - opts.f0) * (t.^2) / (2 * T);
        U(:, ch) = mid + amp * sin(2 * pi * inst + phase);
    end
end

function U = build_impulse(nTicks, m, opts)
    % Single-tick pulses at cycling amplitudes, gapTicks of uMin between them.
    % Amplitude of pulse k is pulseAmps(mod(k-1, numel(pulseAmps))+1), so every
    % amplitude is visited equally and drift affects all amplitudes the same on
    % average. With gapJitterMeanTicks = 0 the train is strictly periodic
    % (period gapTicks+1, the pre-2026-08-17 behaviour, byte-identical). With
    % gapJitterMeanTicks > 0 each inter-pulse gap is gapTicks plus an
    % independent geometric draw on {1,2,...} with that mean, per channel from
    % its own seeded substream -- memoryless, so the train carries no rhythm.
    %
    % Cross-channel guard: when several channels are active, no two pulses on
    % ANY pair of channels may land within crossGuard ticks of each other; a
    % conflicting pulse is shifted forward tick by tick until clear. This keeps
    % every pulse attributable to exactly one pair in the recording (the +1-tick
    % transport delay stays inside the guard). Channels are built in order, so
    % the whole record is reproducible from opts.seed alone.
    amps = opts.pulseAmps(:)';
    if isempty(amps)
        amps = opts.uMax;
    end
    gap = max(1, round(opts.gapTicks));
    period = gap + 1;
    jitterMean = max(0, round(opts.gapJitterMeanTicks));
    crossGuard = max(0, round(opts.crossGuardTicks));

    if isempty(opts.activeChannels)
        activeSet = 1:m;
    else
        activeSet = unique(round(opts.activeChannels(:)'));
        activeSet = activeSet(activeSet >= 1 & activeSet <= m);
    end

    U = opts.uMin * ones(nTicks, m);
    counts = zeros(1, m);
    schedule = lower(string(opts.schedule));

    if schedule == "sequential"
        % Fully independent channels: contiguous per-channel blocks in
        % active-channel order. No cross-pair proximity exists at all, so no
        % guard logic runs and the jitter distribution is exactly as designed.
        % Each block starts with its own leading gap (clean pre-pulse baseline)
        % and the block boundary itself provides >= gapTicks of quiet between
        % the last pulse of one channel and the first of the next.
        nAct = numel(activeSet);
        edges = round(linspace(0, nTicks, nAct + 1));
        for a = 1:nAct
            ch = activeSet(a);
            [U, counts(ch)] = place_train(U, ch, edges(a) + 1, edges(a + 1), ...
                                          amps, gap, period, jitterMean, opts.seed);
        end
        schedDesc = sprintf(', sequential blocks of %d ticks', ...
                            round(nTicks / max(1, nAct)));
    elseif schedule == "interleaved"
        claimed = false(nTicks, 1);
        for ch = activeSet
            % decorrelate staggers channel start times; the claimed-tick guard
            % is what actually forbids collisions once jitter makes trains drift.
            offset = 0;
            if opts.decorrelate && m > 1
                offset = round((ch - 1) * period / m);
            end
            if jitterMean > 0
                % Independent per-channel substream; 7919 (a prime) spreads the
                % seeds so channels do not share LCG trajectories.
                rs = local_rng(opts.seed + 7919 * ch);
                p = 1 / jitterMean;
            end
            pulseIdx = 0;
            tick = 1 + gap + offset;       % leading gap = clean pre-pulse baseline
            while tick <= nTicks
                t = tick;
                while t <= nTicks && any(claimed(max(1, t - crossGuard):min(nTicks, t + crossGuard)))
                    t = t + 1;
                end
                if t > nTicks
                    break;
                end
                pulseIdx = pulseIdx + 1;
                U(t, ch) = amps(mod(pulseIdx - 1, numel(amps)) + 1);
                claimed(t) = true;
                if jitterMean > 0
                    if p >= 1
                        jit = 1;
                    else
                        [rs, r] = local_rand(rs);
                        r = min(max(r, 1e-12), 1 - 1e-12);
                        jit = ceil(log(1 - r) / log(1 - p));   % geometric on {1,2,...}
                    end
                else
                    jit = 0;
                end
                tick = t + period + jit;
            end
            counts(ch) = pulseIdx;
        end
        schedDesc = sprintf(', interleaved (cross-guard %d ticks)', crossGuard);
    else
        error('make_excitation:UnknownSchedule', ...
              'Unknown impulse schedule "%s". Use interleaved or sequential.', schedule);
    end

    if jitterMean > 0
        jitterDesc = sprintf(' + geometric jitter mean %d ticks (%.0f ms)', ...
                             jitterMean, jitterMean * 10);
    else
        jitterDesc = '';
    end
    nPulses = mean(counts(activeSet));
    fprintf(['impulse: %.0f pulses/channel on %d channel(s) (~%.0f per amplitude ' ...
             'of [%s]), gap %d ticks (%.0f ms)%s%s.\n'], ...
            nPulses, numel(activeSet), nPulses / max(1, numel(amps)), ...
            strtrim(sprintf('%g ', amps)), gap, gap * 10, jitterDesc, schedDesc);
end

function [U, nPulses] = place_train(U, ch, blockStart, blockEnd, amps, gap, period, jitterMean, seed)
    % One channel's jittered impulse train confined to [blockStart, blockEnd].
    % Same per-channel substream seeding as the interleaved path, so a channel's
    % train is reproducible from the seed regardless of schedule.
    if jitterMean > 0
        rs = local_rng(seed + 7919 * ch);
        p = 1 / jitterMean;
    end
    nPulses = 0;
    tick = blockStart + gap;               % leading gap inside the block
    while tick <= blockEnd
        nPulses = nPulses + 1;
        U(tick, ch) = amps(mod(nPulses - 1, numel(amps)) + 1);
        if jitterMean > 0
            if p >= 1
                jit = 1;
            else
                [rs, r] = local_rand(rs);
                r = min(max(r, 1e-12), 1 - 1e-12);
                jit = ceil(log(1 - r) / log(1 - p));
            end
        else
            jit = 0;
        end
        tick = tick + period + jit;
    end
end

% =========================================================================
% Helpers (self-contained so no toolbox is required at acquisition time)
% =========================================================================

function bits = lfsr_sequence(nBits, seqLen)
    % Fibonacci LFSR with a known-maximal tap set for nBits = 9: x^9 + x^5 + 1.
    taps = [9, 5];
    reg = ones(1, nBits);
    bits = false(seqLen, 1);
    for i = 1:seqLen
        bits(i) = reg(end) == 1;
        fb = 0;
        for t = taps
            fb = xor(fb, reg(t) == 1);
        end
        reg = [double(fb), reg(1:end-1)];
    end
end

function shift = channel_shift(ch, m, seqLen, decorrelate)
    % Offsetting each channel into a different part of the m-sequence keeps the
    % input columns close to uncorrelated, which is what makes a MIMO fit
    % identifiable. Without this, all channels move together and only their sum
    % is observable.
    if ~decorrelate || m <= 1
        shift = 0;
    else
        shift = round((ch - 1) * seqLen / m);
    end
end

function opts = set_default(opts, field, value)
    if ~isfield(opts, field) || isempty(opts.(field))
        opts.(field) = value;
    end
end

function rs = local_rng(seed)
    % Small deterministic LCG so results reproduce without touching the global
    % RNG state (which the caller may be relying on elsewhere).
    rs = mod(abs(floor(seed)), 2147483647);
    if rs == 0
        rs = 12345;
    end
end

function [rs, r] = local_rand(rs)
    rs = mod(16807 * rs, 2147483647);
    r = (rs - 1) / 2147483646;
end
