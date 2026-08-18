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
