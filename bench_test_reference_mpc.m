function bench_test_reference_mpc
%BENCH_TEST_REFERENCE_MPC  No-hardware checks for the 2026-08-15 deployment additions.
%
% Verifies, against the toy AllModels(10) model:
%   1. make_excitation kind='impulse' (pulse count, isolation, amplitudes, gaps)
%   2. mpc_test backward compatibility (1-arg call unchanged)
%   3. mpc_test per-tick reference (2-arg, p x 1) actually steers the command
%   4. mpc_test preview reference (p x K, K != N) crops/pads without error
%   5. matlab_controller_server's reference CSV loader round-trips
%
% Run: matlab -batch "cd('<repo>'); bench_test_reference_mpc"

    fails = 0;

    % ---- 1. impulse excitation ------------------------------------------
    U = make_excitation('impulse', 600, 8, struct('activeChannels', 1));
    pulses = find(U(:, 1) > 0);
    assert(all(U(:, 2:end) == 0, 'all'), 'held channels moved');
    gapsOk = isempty(pulses) || all(diff(pulses) == 51);
    ampsSeen = unique(U(pulses, 1))';
    ok = numel(pulses) == numel(51:51:600) && gapsOk && ...
         isequal(ampsSeen, [10 20 30 40]);
    fails = fails + report('impulse excitation', ok, ...
        sprintf('%d pulses, amps [%s]', numel(pulses), num2str(ampsSeen)));

    % isolation: every pulse is single-tick
    iso = all(U(max(pulses - 1, 1), 1) == 0) && all(U(min(pulses + 1, 600), 1) == 0);
    fails = fails + report('impulse isolation', iso, 'all pulses single-tick');

    % ---- 1b. jittered all-channel impulse (2026-08-17 additions) ---------
    % The saline-validation configuration: all 8 pairs, amps [5 10 18 25],
    % geometric gap jitter mean 8 ticks (80 ms) on the 50-tick base gap.
    optsJ = struct('pulseAmps', {[5 10 18 25]}, 'gapJitterMeanTicks', 8, ...
                   'uMax', 25, 'seed', 424242);
    UJ  = make_excitation('impulse', 7000, 8, optsJ);
    UJ2 = make_excitation('impulse', 7000, 8, optsJ);
    allJit = [];
    perChOk = true;
    for ch = 1:8
        pj = find(UJ(:, ch) > 0);
        isoJ = all(UJ(max(pj - 1, 1), ch) == 0) && all(UJ(min(pj + 1, 7000), ch) == 0);
        ampsJ = unique(UJ(pj, ch))';
        jit = diff(pj) - 51;                       % jitter = interval - (gap+1)
        perChOk = perChOk && isoJ && isequal(ampsJ, [5 10 18 25]) && ...
                  numel(pj) >= 60 && all(jit >= 1);
        allJit = [allJit; jit]; %#ok<AGROW>
    end
    fails = fails + report('impulse jitter per-chan', perChOk, ...
        sprintf('8 channels isolated, amps [5 10 18 25], all jitter >= 1 tick (n=%d)', ...
                numel(allJit)));

    % pooled jitter mean must sit near the requested 8 ticks (geometric std is
    % ~7.5 ticks, n ~ 800, so +/-1 tick is a ~4-sigma band), and the same seed
    % must reproduce the record exactly.
    mj = mean(allJit);
    fails = fails + report('impulse jitter stats', ...
        mj > 7 && mj < 9 && isequal(UJ, UJ2), ...
        sprintf('mean jitter %.2f ticks (target 8), same-seed reproducible', mj));

    % cross-channel guard: no two pulses on ANY channels within 2 ticks
    rowPulses = sum(UJ > 0, 2);
    spacing = diff(find(rowPulses > 0));
    fails = fails + report('impulse cross-chan guard', ...
        all(rowPulses <= 1) && all(spacing >= 3), ...
        sprintf('no collisions, min cross-channel spacing %d ticks', min(spacing)));

    % ---- 1c. sequential schedule: fully independent per-channel blocks ---
    optsS = optsJ;
    optsS.schedule = 'sequential';
    US = make_excitation('impulse', 28000, 8, optsS);
    edges = round(linspace(0, 28000, 9));
    seqOk = true;
    seqCounts = zeros(1, 8);
    for ch = 1:8
        pj = find(US(:, ch) > 0);
        inBlock = ~isempty(pj) && all(pj > edges(ch)) && all(pj <= edges(ch + 1));
        isoS = all(US(max(pj - 1, 1), ch) == 0) && all(US(min(pj + 1, 28000), ch) == 0);
        jitS = diff(pj) - 51;
        seqOk = seqOk && inBlock && isoS && all(jitS >= 1) && ...
                isequal(unique(US(pj, ch))', [5 10 18 25]) && numel(pj) >= 40;
        seqCounts(ch) = numel(pj);
    end
    seqOk = seqOk && all(sum(US > 0, 2) <= 1);
    fails = fails + report('impulse sequential blocks', seqOk, ...
        sprintf('%d..%d pulses/block, confined + isolated, jitter >= 1', ...
                min(seqCounts), max(seqCounts)));

    % ---- 1d. random schedule: balanced (channel, amplitude) deck ---------
    % The tissue probing protocol (2026-08-25): ONE global train, every
    % probe's condition drawn from a block-shuffled deck.
    optsR = optsJ;
    optsR.schedule = 'random';
    UR  = make_excitation('impulse', 20000, 8, optsR);
    UR2 = make_excitation('impulse', 20000, 8, optsR);
    gTicks = find(sum(UR > 0, 2) > 0);
    fails = fails + report('impulse random reproducible+single', ...
        isequal(UR, UR2) && all(sum(UR > 0, 2) <= 1), ...
        sprintf('%d probes, same-seed identical, one pulse/tick', numel(gTicks)));

    givR = diff(gTicks);
    gjitR = givR - 51;
    fails = fails + report('impulse random global spacing', ...
        all(givR >= 52) && mean(gjitR) > 7 && mean(gjitR) < 9, ...
        sprintf('min interval %d ticks (>= 52), mean jitter %.2f (target 8)', ...
                min(givR), mean(gjitR)));

    cntR = zeros(8, 4);
    ampsR = [5 10 18 25];
    isoR = true;
    for ch = 1:8
        pj = find(UR(:, ch) > 0);
        isoR = isoR && all(UR(max(pj - 1, 1), ch) == 0) && ...
               all(UR(min(pj + 1, 20000), ch) == 0);
        for ai = 1:4
            cntR(ch, ai) = sum(abs(UR(pj, ch) - ampsR(ai)) < 1e-9);
        end
    end
    fails = fails + report('impulse random balance', ...
        max(cntR(:)) - min(cntR(:)) <= 1 && all(cntR(:) > 0), ...
        sprintf('per-condition counts %d..%d over 32 conditions (spread <= 1)', ...
                min(cntR(:)), max(cntR(:))));

    % legacy schedules untouched: regenerate 1b's interleaved design and
    % re-assert its invariants byte-for-byte against the copy from above.
    UJ3 = make_excitation('impulse', 7000, 8, optsJ);
    fails = fails + report('impulse random leaves legacy intact', ...
        isoR && isequal(UJ3, UJ), ...
        'random pulses single-tick; interleaved regenerates byte-identical');

    % ---- 2. one-arg call (legacy path) ----------------------------------
    evalin('base', 'clear MPC_OPTS MPC_TARGET');
    mpc_test([]);
    u_legacy = mpc_test(zeros(8, 1));
    fails = fails + report('legacy 1-arg call', ...
        ~isempty(u_legacy) && all(isfinite(u_legacy)), ...
        sprintf('u = %s', mat2str(round(u_legacy', 4))));

    % ---- 3. per-tick reference steers the command ------------------------
    mpc_test([]);
    uLo = run_settled(zeros(8, 1), 0);      % track 0
    mpc_test([]);
    uHi = run_settled(zeros(8, 1), 1.0);    % track a big positive reference
    fails = fails + report('reference steers u', uHi(1) > uLo(1) + 1e-6, ...
        sprintf('u(track 0) = %.4g, u(track 1) = %.4g', uLo(1), uHi(1)));

    % ---- 4. preview shapes ----------------------------------------------
    mpc_test([]);
    ok = true;
    try
        mpc_test(zeros(8, 1), 0.5);                 % scalar
        mpc_test(zeros(8, 1), 0.5 * ones(1, 5));    % K < N
        mpc_test(zeros(8, 1), 0.5 * ones(1, 40));   % K > N
    catch err
        ok = false;
        fprintf('  preview error: %s\n', err.message);
    end
    fails = fails + report('preview crop/pad', ok, 'K = scalar, 5, 40 all accepted');

    % ---- 4b. preview must actually ANTICIPATE (regression: a 1 x K row on a
    % p = 1 plant used to be truncated to its first element, silently disabling
    % preview in exactly the production configuration) ---------------------
    mpc_test([]);
    uNoPreview = mpc_test(zeros(8, 1), 0);                       % flat zero ref
    mpc_test([]);
    uPreview = mpc_test(zeros(8, 1), [0 0 1 1 1 1 1 1 1 1]);     % step arrives at k+2
    fails = fails + report('preview anticipates', uPreview(1) > uNoPreview(1) + 1e-9, ...
        sprintf('u(flat 0) = %.4g, u(step in preview) = %.4g', uNoPreview(1), uPreview(1)));

    % ---- 4c. soft state reset keeps the initialized problem --------------
    ok = true;
    try
        mpc_test('state');
        uAfter = mpc_test(zeros(8, 1), 0.5);
        ok = ~isempty(uAfter) && all(isfinite(uAfter));
    catch err
        ok = false;
        fprintf('  soft reset error: %s\n', err.message);
    end
    fails = fails + report('soft state reset', ok, 'mpc_test(''state'') then step OK');

    % ---- 5. reference CSV round-trip ------------------------------------
    tmp = fullfile(tempdir, 'bench_ref_test.csv');
    fid = fopen(tmp, 'w');
    fprintf(fid, 'tick,r1\n');
    vals = [0.001; 0.002; 0.0035; 0.001];
    for i = 1:numel(vals)
        fprintf(fid, '%d,%.9g\n', i, vals(i));
    end
    fclose(fid);
    loaded = load_reference_csv_copy(tmp);
    delete(tmp);
    fails = fails + report('reference CSV loader', ...
        isequal(size(loaded), [4 1]) && max(abs(loaded - vals)) < 1e-12, ...
        sprintf('4 ticks, max err %.2g', max(abs(loaded - vals))));

    % ---- 6. model Ts is the source of truth (frame-locked alignment) ------
    % A model stamped with the frame-locked tick period (9.8304 ms) must load
    % without resampling or error, and the controller must still step. Before
    % 2026-08-18 a struct model with Ts ~= 0.01 was a hard error.
    ok = true;
    detail = '';
    try
        M = struct('sys', struct('A', 0.9512, 'B', 0.00975, 'C', 1, 'D', 0, ...
                                 'Ts', 6 / 610.3515625));
        AM = repmat(struct('sys', []), 1, 10);
        AM(10) = M;
        assignin('base', 'AllModels', AM);
        mpc_test([]);
        uT = mpc_test(0, 0.5);
        ok = ~isempty(uT) && all(isfinite(uT));
        detail = sprintf('Ts=9.8304 ms model accepted, u = %.4g', uT(1));
    catch err
        ok = false;
        detail = err.message;
    end
    evalin('base', 'clear AllModels');
    mpc_test([]);   % restore the file model for anything running after us
    fails = fails + report('model-Ts source of truth', ok, detail);

    % ---- 7. solver hygiene: zero target from rest -> u is EXACTLY zero ----
    % (2026-08-20: OSQP polish + tight eps + dust clamp. At the old defaults,
    % ADMM residue ~1e-3 leaked out as phantom sub-threshold stim commands.)
    evalin('base', 'clear MPC_OPTS MPC_TARGET');
    mpc_test([]);
    uZ = run_settled(zeros(8, 1), 0);
    fails = fails + report('exact zero at zero target', all(uZ == 0), ...
        sprintf('u = %s (must be exactly 0)', mat2str(uZ')));

    % ---- 8. MPC_MODEL_INDEX selects the model slot ------------------------
    ok = true;
    detail = '';
    try
        AM = repmat(struct('sys', []), 1, 3);
        AM(3).sys = struct('A', 0.5, 'B', 0.1, 'C', 1, 'D', 0, 'Ts', 0.01);
        assignin('base', 'AllModels', AM);
        assignin('base', 'MPC_MODEL_INDEX', 3);
        mpc_test([]);
        u3 = mpc_test(zeros(8, 1), 0.5);
        ok = ~isempty(u3) && all(isfinite(u3));
        detail = sprintf('slot-3 model (no slot 10 present) accepted, u = %.4g', u3(1));
    catch err
        ok = false;
        detail = err.message;
    end
    evalin('base', 'clear AllModels MPC_MODEL_INDEX');
    mpc_test([]);
    fails = fails + report('MPC_MODEL_INDEX slot', ok, detail);

    % ---- 9. featureChannel maps the measurement ---------------------------
    % With featureChannel = 5, feature 5 must drive the observer and feature 1
    % must not.
    assignin('base', 'MPC_OPTS', struct('featureChannel', 5));
    mpc_test([]);
    yA = zeros(8, 1); yA(5) = 0.5;
    uCh5 = run_settled(yA, 0.5);
    mpc_test('state');
    yB = zeros(8, 1); yB(1) = 0.5;   % channel 1 loaded, channel 5 silent
    uCh1 = run_settled(yB, 0.5);
    evalin('base', 'clear MPC_OPTS');
    mpc_test([]);
    fails = fails + report('featureChannel mapping', ...
        abs(uCh5(1) - uCh1(1)) > 1e-9, ...
        sprintf('u(ch5 loaded) = %.4g, u(ch1 loaded) = %.4g (must differ)', ...
                uCh5(1), uCh1(1)));

    % ---- 10. offset model: closed-loop tracking at the true operating point
    % Toy dynamics + uOffset 5, yOffset 0.5. Plant simulated in RAW frame:
    % y = yOff + C x, x+ = A x + B (u - uOff). With rWeight 1e-4 the loop must
    % settle near u* = uOff + (r - yOff) * g / (g^2 + rWeight) and y near r.
    ok = true;
    detail = '';
    try
        sysO = struct('A', 0.9512, 'B', 0.00975, 'C', 1, 'D', 0, 'Ts', 0.01, ...
                      'uOffset', 5, 'yOffset', 0.5);
        AM = repmat(struct('sys', []), 1, 10);
        AM(10).sys = sysO;
        assignin('base', 'AllModels', AM);
        assignin('base', 'MPC_OPTS', struct('rWeight', 1e-4));
        mpc_test([]);
        g = 0.00975 / (1 - 0.9512);
        rTar = 1.0;
        uStar = 5 + (rTar - 0.5) * g / (g^2 + 1e-4);
        x = 0; y = 0.5; u = 0;
        for k = 1:400
            u = mpc_test([y; zeros(7, 1)], rTar);
            x = 0.9512 * x + 0.00975 * (u(1) - 5);
            y = 0.5 + x;
        end
        ok = abs(y - rTar) < 0.01 && abs(u(1) - uStar) < 0.1;
        detail = sprintf('settled y = %.4f (target %.2f), u = %.3f (u* = %.3f)', ...
                         y, rTar, u(1), uStar);
    catch err
        ok = false;
        detail = err.message;
    end
    evalin('base', 'clear AllModels MPC_OPTS');
    mpc_test([]);
    fails = fails + report('offset operating point', ok, detail);

    % ---- 11. useObserver = 0 ignores the measurement (pure feedforward) ---
    assignin('base', 'MPC_OPTS', struct('useObserver', 0));
    lastwarn('');
    mpc_test([]);
    uFF1 = mpc_test(zeros(8, 1), 0.5);
    [~, warnId] = lastwarn;
    mpc_test('state');
    uFF2 = mpc_test(100 * ones(8, 1), 0.5);   % wildly different measurement
    evalin('base', 'clear MPC_OPTS');
    mpc_test([]);
    fails = fails + report('useObserver=0 feedforward', ...
        isequal(uFF1, uFF2) && strcmp(warnId, 'mpc_test:ObserverDisabled'), ...
        sprintf('u identical under y=0 and y=100; warning %s', warnId));

    fprintf('\n%s\n', ternary(fails == 0, 'ALL BENCH TESTS PASS', ...
                              sprintf('%d BENCH TEST(S) FAILED', fails)));
    if fails > 0
        error('bench_test_reference_mpc:Failed', '%d failure(s)', fails);
    end
end

function u = run_settled(y, r)
    % A few ticks so the QP settles; measurement fixed at y.
    for k = 1:15
        u = mpc_test(y, r);
    end
end

function n = report(name, ok, detail)
    if ok
        fprintf('PASS  %-24s %s\n', name, detail);
        n = 0;
    else
        fprintf('FAIL  %-24s %s\n', name, detail);
        n = 1;
    end
end

function out = ternary(cond, a, b)
    if cond, out = a; else, out = b; end
end

function refTraj = load_reference_csv_copy(referenceFile)
    % Mirror of matlab_controller_server's private loader (not callable from
    % outside); keep the two in sync.
    raw = readmatrix(referenceFile);
    refTraj = raw(:, 2:end);
end
