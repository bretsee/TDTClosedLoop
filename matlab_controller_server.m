function matlab_controller_server(mode, requestPort, replyPort, outputCount, constantValue, maxPackets, logFile)
% MATLAB_CONTROLLER_SERVER  Localhost UDP controller responder for C++ testing.
%
% Two calling styles:
%   Positional (original):
%     matlab_controller_server('mpc', 31000, 31001, 16, 0, 600, 'server_lat.csv')
%   Options struct (needed for openloop; ignores the other arguments):
%     cfg.mode = 'openloop'; cfg.outputCount = 16; cfg.maxPackets = 6000;
%     cfg.excitation.kind = 'prbs'; cfg.captureFile = 'capture.csv';
%     matlab_controller_server(cfg)
%
% Fields / arguments:
%   mode          'constant' | 'ramp' | 'mpc' | 'openloop'   (default 'constant')
%   requestPort   UDP port this server listens on            (default 31000)
%   replyPort     UDP port replies are sent to on 127.0.0.1  (default 31001)
%   outputCount   number of float32 outputs in a reply       (default 8)
%   constantValue value used by 'constant' mode              (default 5)
%   maxPackets    stop after N serviced packets, 0 = forever (default 0)
%   logFile       CSV of per-packet server timing            (default none)
%   excitation    struct passed to make_excitation, plus .kind ('openloop' only)
%   captureFile   CSV of aligned (u, y) per tick             ('openloop' only)
%
% Protocol:
%   Request  = [uint32 seq][uint32 feature_count][feature_count x float32]
%   Response = [uint32 seq][uint32 output_count][output_count x float32]
%   All integer/float words are sent in network byte order (big-endian).
%
% Latency note (2026-07-23). Two separate problems, both traced to the Windows
% ~15.6 ms default timer quantum, kept this server from replying inside the C++
% side's 10 ms tick:
%   1. Receive side: the loop polled NumDatagramsAvailable with pause(0.001).
%      pause() is quantum-bound, so wake-ups were ~15.6 ms apart. Fixed by a
%      blocking read(), which parks in the transport layer and wakes on arrival.
%   2. Send side: udpport write() is *also* quantum-bound -- measured avg
%      15.775 ms per call (min 0.316 ms) with default resolution. This alone
%      exceeded the whole tick budget. Fixed by holding the process in the 1 ms
%      quantum for the server's lifetime via a no-op timer object (see below).
% Measured effect: server turnaround went from ~15.8 ms to ~2.1 ms, and the C++
% loop went from 0/500 usable replies to 476/500.

    cfg = struct();
    if nargin >= 1 && isstruct(mode)
        cfg = mode;                 % options-struct style
    else
        if nargin >= 1, cfg.mode          = mode;          end
        if nargin >= 2, cfg.requestPort   = requestPort;   end
        if nargin >= 3, cfg.replyPort     = replyPort;     end
        if nargin >= 4, cfg.outputCount   = outputCount;   end
        if nargin >= 5, cfg.constantValue = constantValue; end
        if nargin >= 6, cfg.maxPackets    = maxPackets;    end
        if nargin >= 7, cfg.logFile       = logFile;       end
    end

    cfg = set_default(cfg, 'mode',          'constant');
    cfg = set_default(cfg, 'requestPort',   31000);
    cfg = set_default(cfg, 'replyPort',     31001);
    cfg = set_default(cfg, 'outputCount',   8);
    cfg = set_default(cfg, 'constantValue', 5);
    cfg = set_default(cfg, 'maxPackets',    0);
    cfg = set_default(cfg, 'logFile',       '');
    cfg = set_default(cfg, 'captureFile',   '');
    cfg = set_default(cfg, 'excitation',    struct());
    cfg = set_default(cfg, 'referenceFile', '');   % mpc only: per-tick reference CSV
    cfg = set_default(cfg, 'mpcOpts',       struct());  % mpc only: MPC_OPTS overrides
    cfg = set_default(cfg, 'stimPairs',     []);   % mpc only: reply-slot mapping

    mode          = lower(string(cfg.mode));
    requestPort   = double(cfg.requestPort);
    replyPort     = double(cfg.replyPort);
    outputCount   = max(1, double(cfg.outputCount));
    constantValue = double(cfg.constantValue);
    maxPackets    = max(0, double(cfg.maxPackets));
    logFile       = string(cfg.logFile);
    captureFile   = string(cfg.captureFile);
    referenceFile = string(cfg.referenceFile);

    % Raise the Windows timer resolution to ~1 ms for the lifetime of this server.
    % This timer is deliberately a no-op: we never care about its callback, only
    % about the side effect that a running MATLAB timer puts the process into the
    % 1 ms scheduling quantum. Without it, udpport write() costs ~15.8 ms per call
    % (measured avg 15.775 ms, min 0.316 ms -- i.e. the 15.6 ms quantum), which is
    % more than the C++ side's entire 10 ms tick budget and makes every reply land
    % a tick late. With it, write() costs ~1.4 ms avg / 2.3 ms p95.
    % BusyMode 'drop' keeps executions from backing up while the main thread is
    % parked in read(); the resolution change does not depend on the callback
    % actually running.
    resTimer = timer('ExecutionMode', 'fixedRate', 'Period', 0.001, ...
                     'BusyMode', 'drop', 'TimerFcn', @(~, ~) [], ...
                     'Name', 'ControllerServerTimerResolution');
    start(resTimer);
    cleanupTimer = onCleanup(@() stop_and_delete_timer(resTimer)); %#ok<NASGU>

    % ---- mode-specific setup -------------------------------------------------
    excitationU = [];
    refTraj = [];          % [T x p] per-tick reference trajectory, mpc mode only
    refPreviewTicks = 20;  % preview window handed to mpc_test (cropped to its N)
    stimPairs = round(double(cfg.stimPairs(:)'));
    if mode == "mpc"
        % Tuning overrides must land in the base workspace BEFORE the warm-up
        % call below, because mpc_test reads MPC_OPTS once, at init. When no
        % overrides are given, CLEAR any stale MPC_OPTS a previous session left
        % behind -- otherwise this run silently inherits last session's weights
        % and bounds.
        if ~isempty(fieldnames(cfg.mpcOpts))
            assignin('base', 'MPC_OPTS', cfg.mpcOpts);
            fprintf('mpc: MPC_OPTS overrides -> base workspace: %s\n', ...
                    strjoin(fieldnames(cfg.mpcOpts), ', '));
        else
            evalin('base', 'clear MPC_OPTS');
        end
        if strlength(referenceFile) > 0
            refTraj = load_reference_csv(referenceFile);
            fprintf('mpc: reference trajectory %s: %d ticks (%.1f s), %d output(s), range [%g %g]\n', ...
                    referenceFile, size(refTraj, 1), size(refTraj, 1) / 100, ...
                    size(refTraj, 2), min(refTraj(:)), max(refTraj(:)));
        end
        if ~isempty(stimPairs)
            if any(stimPairs < 1) || any(stimPairs > outputCount) || ...
               numel(unique(stimPairs)) ~= numel(stimPairs)
                error('matlab_controller_server:BadStimPairs', ...
                      'stimPairs must be unique indices within 1..%d.', outputCount);
            end
            fprintf('mpc: controller output(s) mapped to stim pair slot(s) [%s]; all other slots 0.\n', ...
                    strtrim(sprintf('%d ', stimPairs)));
        end

        % Warm the controller before announcing readiness. The first mpc_test call
        % pays MATLAB JIT plus OSQP problem setup: measured 62.8 ms, against a
        % 10 ms tick budget, which cost the C++ side its first several ticks.
        % ORDER MATTERS: full reset FIRST (pick up new AllModels/MPC_OPTS), then
        % warm calls, then a STATE-ONLY reset -- a full reset here would discard
        % the warmed problem and re-pay init on the first real packet, which is
        % exactly what the warm-up exists to avoid.
        mpc_test([]);
        try
            for k = 1:3
                mpc_test(zeros(outputCount, 1));
            end
        catch warmErr
            fprintf('Controller warm-up skipped (%s). First reply may be late.\n', ...
                    warmErr.identifier);
        end
        mpc_test('state');   % zero xhat/u_last/tick, keep the warmed problem

    elseif mode == "openloop"
        % Open-loop system-ID excitation. The whole sequence is generated up front
        % so that no allocation or RNG work happens inside the 10 ms tick, and so
        % the exact commanded sequence is known before a single pulse is delivered.
        exc = cfg.excitation;
        exc = set_default(exc, 'kind', 'prbs');
        if maxPackets <= 0
            maxPackets = 6000;   % 60 s at 100 Hz; open-loop runs are always bounded
            fprintf('openloop: maxPackets defaulted to %d ticks (%.0f s).\n', ...
                    maxPackets, maxPackets / 100);
        end
        excitationU = make_excitation(exc.kind, maxPackets, outputCount, exc);
        fprintf('openloop: %s excitation, %d ticks (%.1f s), u in [%g %g]\n', ...
                exc.kind, maxPackets, maxPackets / 100, ...
                min(excitationU(:)), max(excitationU(:)));
        if strlength(captureFile) == 0
            captureFile = "capture_openloop.csv";
            fprintf('openloop: captureFile defaulted to %s\n', captureFile);
        end
    end

    % A blocking read that expires emits a warning; at 100 Hz this only happens
    % when the C++ side is not running, so it is noise rather than information.
    warnState = warning('off', 'instrument:interface:udpport:ReadWarning');
    cleanupWarn = onCleanup(@() warning(warnState)); %#ok<NASGU>

    % Timeout is the blocking-read parking time, not a per-packet budget: read()
    % returns as soon as a datagram lands. Keep it long enough that idle periods
    % do not spin, short enough that Ctrl+C and shutdown stay responsive.
    u = udpport("datagram", "IPV4", "LocalPort", requestPort, "Timeout", 1.0);
    cleanupObj = onCleanup(@() clear_udp_port(u)); %#ok<NASGU>

    packetCount = 0;
    rampValue = 0;
    rampStep = 5;
    rampMin = 0;
    rampMax = 40;
    rampDirection = 1;

    % Per-packet timing, preallocated so logging never allocates inside the loop.
    logCapacity = 0;
    if strlength(logFile) > 0
        logCapacity = 20000;
        if maxPackets > 0
            logCapacity = maxPackets;
        end
    end
    logSeq        = zeros(logCapacity, 1);
    logGapMs      = zeros(logCapacity, 1);   % wake-to-wake interval (should be ~10 ms)
    logComputeMs  = zeros(logCapacity, 1);   % controller evaluation only
    logTurnMs     = zeros(logCapacity, 1);   % read() return -> write() complete
    logRows = 0;

    % Capture buffers, preallocated; sized on first packet once the feature
    % count is known. Unbounded runs (maxPackets = 0) get a fixed budget rather
    % than capacity 1 -- when it fills, a one-time warning prints instead of
    % silently dropping the rest of the session.
    capCapacity = 0;
    capFullWarned = false;
    if strlength(captureFile) > 0
        if maxPackets > 0
            capCapacity = maxPackets;
        else
            capCapacity = 20000;   % 200 s at 100 Hz
        end
    end
    capU = []; capY = []; capSeq = []; capTms = [];
    capRows = 0;

    % Turnaround stats: bounded storage (median/p95 from the first turnCapacity
    % packets) plus exact running count/sum/max, so an unbounded multi-hour rig
    % server cannot grow memory inside the reply path.
    turnCapacity = 20000;
    turnaroundMs = zeros(turnCapacity, 1);
    turnRows = 0;
    turnCount = 0;
    turnSum = 0;
    turnMax = 0;
    idleReads = 0;
    prevWakeTime = [];
    runStart = [];

    fprintf('MATLAB localhost controller server ready. mode=%s requestPort=%d replyPort=%d outputCount=%d constantValue=%g\n', ...
            mode, requestPort, replyPort, outputCount, constantValue);
    if maxPackets > 0
        fprintf('Will stop automatically after %d serviced packets.\n', maxPackets);
    end
    if strlength(logFile) > 0
        fprintf('Per-packet server timing -> %s\n', logFile);
    end
    if strlength(captureFile) > 0
        fprintf('Open-loop (u,y) capture -> %s\n', captureFile);
    end
    fprintf('Press Ctrl+C in MATLAB to stop.\n');

    while true
        % Blocking read: parks until one datagram arrives (or Timeout elapses).
        % This replaces the old pause(0.001) poll and is half of the latency fix.
        packet = read(u, 1, "uint8");
        if isempty(packet) || isempty(packet.Data)
            % Idle timeout. A bounded run (maxPackets > 0) is a benchmark or a
            % capture, so sustained silence after the C++ side exits means
            % "done" -- stop and flush the logs. Require several CONSECUTIVE
            % 1 s timeouts first: a single one can be a transient stall of the
            % sender (console QuickEdit freeze, paging), and stopping on it
            % killed the controller mid-run. An unbounded run waits forever.
            idleReads = idleReads + 1;
            if maxPackets > 0 && packetCount > 0 && idleReads >= 3
                fprintf('Idle for %d consecutive reads after %d packets; stopping bounded run.\n', ...
                        idleReads, packetCount);
                break;
            end
            continue;
        end
        idleReads = 0;

        wakeTime = tic;
        if isempty(prevWakeTime)
            gapMs = NaN;
            runStart = tic;
        else
            gapMs = toc(prevWakeTime) * 1000;
        end
        prevWakeTime = tic;

        bytes = uint8(packet.Data);
        packetCount = packetCount + 1;
        senderAddress = string(packet.SenderAddress);
        senderPort = double(packet.SenderPort);

        if numel(bytes) < 8
            fprintf('Ignoring short localhost request #%d from %s:%d (%d bytes)\n', ...
                    packetCount, senderAddress, senderPort, numel(bytes));
            continue;
        end

        seq = unpack_u32_be(bytes(1:4));
        featureCount = unpack_u32_be(bytes(5:8));
        neededBytes = 8 + double(featureCount) * 4;
        if numel(bytes) < neededBytes
            fprintf('Ignoring truncated localhost request #%d seq=%u featureCount=%u bytes=%d\n', ...
                    packetCount, seq, featureCount, numel(bytes));
            continue;
        end

        % Vectorized unpack of the float32 payload (was a per-element loop).
        features = unpack_f32_be_vec(bytes(9:neededBytes));

        computeStart = tic;
        switch mode
            case "constant"
                y = constantValue * ones(outputCount, 1);
            case "ramp"
                y = rampValue * ones(outputCount, 1);
                rampValue = rampValue + rampDirection * rampStep;
                if rampValue >= rampMax
                    rampValue = rampMax;
                    rampDirection = -1;
                elseif rampValue <= rampMin
                    rampValue = rampMin;
                    rampDirection = 1;
                end
            case "mpc"
                % Run the real model-based controller on the received feature
                % vector. mpc_test returns one command per model input; the
                % C++ side normalizes/pads to its UDP output count.
                if isempty(refTraj)
                    y = mpc_test(features);
                else
                    % Hand mpc_test a preview window starting at this tick.
                    % Indexed by packetCount (like openloop) so a dropped
                    % request cannot skip a slice of the trajectory. Past the
                    % end, the trajectory holds its final row.
                    idx = min(packetCount, size(refTraj, 1));
                    stop = min(idx + refPreviewTicks - 1, size(refTraj, 1));
                    y = mpc_test(features, refTraj(idx:stop, :)');
                end
            case "openloop"
                % Ignore the measurement entirely: this is the open-loop probe.
                % Index by packetCount, not by seq, so a dropped request does not
                % skip a slice of the designed sequence.
                idx = min(packetCount, size(excitationU, 1));
                y = excitationU(idx, :)';
            otherwise
                error('matlab_controller_server:UnsupportedMode', ...
                      'Unsupported mode: %s', mode);
        end
        % Map an m-output controller onto the physical reply slots. Word k of the
        % UDP packet drives bipolar pair k, so a model identified on pair 3 must
        % land in slot 3 -- NOT slot 1, and never broadcast (the C++ side also
        % refuses to broadcast scalars as of 2026-08-15). Unmapped slots stay 0.
        if mode == "mpc" && ~isempty(stimPairs)
            mapped = zeros(outputCount, 1);
            nMap = min(numel(stimPairs), numel(y));
            mapped(stimPairs(1:nMap)) = y(1:nMap);
            y = mapped;
        end
        computeMs = toc(computeStart) * 1000;

        reply = pack_response(seq, y);
        write(u, reply, "uint8", "127.0.0.1", replyPort);
        turnMs = toc(wakeTime) * 1000;
        turnCount = turnCount + 1;
        turnSum = turnSum + turnMs;
        turnMax = max(turnMax, turnMs);
        if turnRows < turnCapacity
            turnRows = turnRows + 1;
            turnaroundMs(turnRows) = turnMs;
        end

        if logRows < logCapacity
            logRows = logRows + 1;
            logSeq(logRows)       = seq;
            logGapMs(logRows)     = gapMs;
            logComputeMs(logRows) = computeMs;
            logTurnMs(logRows)    = turnMs;
        end

        if capCapacity > 0
            if isempty(capU)
                capU   = zeros(capCapacity, numel(y));
                capY   = zeros(capCapacity, numel(features));
                capSeq = zeros(capCapacity, 1);
                capTms = zeros(capCapacity, 1);
            end
            if capRows < capCapacity && numel(y) == size(capU, 2) ...
                                     && numel(features) == size(capY, 2)
                capRows = capRows + 1;
                capSeq(capRows)  = seq;
                capTms(capRows)  = toc(runStart) * 1000;
                capU(capRows, :) = y(:)';
                capY(capRows, :) = features(:)';
            elseif capRows >= capCapacity && ~capFullWarned
                capFullWarned = true;
                fprintf('WARNING: capture buffer full at %d rows; later packets are NOT captured.\n', ...
                        capRows);
            end
        end

        if packetCount <= 5 || mod(packetCount, 100) == 0
            feature0 = features(1);
            out0 = y(1);
            fprintf(['Reply #%d seq=%u sender=%s:%d feature0=%.6f out0=%.6f bytes=%d ' ...
                     'compute=%.3fms turnaround=%.3fms gap=%.3fms\n'], ...
                    packetCount, seq, senderAddress, senderPort, feature0, out0, numel(reply), ...
                    computeMs, turnMs, gapMs);
        end

        if maxPackets > 0 && packetCount >= maxPackets
            break;
        end
    end

    report_turnaround(turnaroundMs(1:turnRows), turnCount, turnSum, turnMax);
    if strlength(logFile) > 0 && logRows > 0
        write_timing_log(logFile, logSeq(1:logRows), logGapMs(1:logRows), ...
                         logComputeMs(1:logRows), logTurnMs(1:logRows));
        fprintf('Wrote %d timing rows to %s\n', logRows, logFile);
    end
    if strlength(captureFile) > 0 && capRows > 0
        write_capture_log(captureFile, capSeq(1:capRows), capTms(1:capRows), ...
                          capU(1:capRows, :), capY(1:capRows, :));
        fprintf('Wrote %d capture rows to %s\n', capRows, captureFile);
    end
end

function report_turnaround(sampleMs, totalCount, totalSum, totalMax)
    if totalCount == 0
        fprintf('No packets serviced; no timing summary.\n');
        return;
    end
    % avg/max are exact over ALL packets; median/p95 come from the bounded
    % sample (first 20k packets) so an unbounded server never grows memory.
    note = '';
    if totalCount > numel(sampleMs)
        note = sprintf(' (median/p95 from first %d)', numel(sampleMs));
    end
    fprintf(['Server turnaround over %d packets: avg %.3f ms, median %.3f ms, ' ...
             'p95 %.3f ms, max %.3f ms%s\n'], ...
            totalCount, totalSum / totalCount, median(sampleMs), ...
            prctile_simple(sampleMs, 95), totalMax, note);
end

function value = prctile_simple(x, p)
    % Avoids a Statistics Toolbox dependency for a single percentile.
    x = sort(x(:));
    if isscalar(x)
        value = x;
        return;
    end
    idx = max(1, min(numel(x), ceil(p / 100 * numel(x))));
    value = x(idx);
end

function write_timing_log(logFile, seq, gapMs, computeMs, turnMs)
    fid = fopen(logFile, 'w');
    if fid < 0
        warning('matlab_controller_server:LogOpenFailed', ...
                'Could not open %s for writing; timing log skipped.', logFile);
        return;
    end
    closer = onCleanup(@() fclose(fid)); %#ok<NASGU>
    fprintf(fid, 'seq,gap_ms,compute_ms,turnaround_ms\n');
    for i = 1:numel(seq)
        fprintf(fid, '%u,%.6f,%.6f,%.6f\n', seq(i), gapMs(i), computeMs(i), turnMs(i));
    end
end

function write_capture_log(captureFile, seq, tms, U, Y)
    % One row per control tick: the command this server issued and the feature
    % vector it was issued in response to. See fit_sysid_from_capture.m for the
    % causal alignment between the two (u is applied one tick after it is logged).
    fid = fopen(captureFile, 'w');
    if fid < 0
        warning('matlab_controller_server:CaptureOpenFailed', ...
                'Could not open %s for writing; capture log skipped.', captureFile);
        return;
    end
    closer = onCleanup(@() fclose(fid)); %#ok<NASGU>

    nu = size(U, 2);
    ny = size(Y, 2);
    header = "tick,seq,t_ms";
    for i = 1:nu
        header = header + sprintf(",u%d", i);
    end
    for i = 1:ny
        header = header + sprintf(",y%d", i);
    end
    fprintf(fid, '%s\n', header);

    fmt = ['%d,%u,%.3f', repmat(',%.6g', 1, nu + ny), '\n'];
    for i = 1:numel(seq)
        fprintf(fid, fmt, i, seq(i), tms(i), U(i, :), Y(i, :));
    end
end

function s = set_default(s, field, value)
    if ~isfield(s, field) || isempty(s.(field))
        s.(field) = value;
    end
end

function refTraj = load_reference_csv(referenceFile)
% Reads the per-tick reference CSV written by rig/build_touch_reference.py:
% header 'tick,r1[,r2,...]', one row per 100 Hz control tick. Returns [T x p].
    if ~isfile(referenceFile)
        error('matlab_controller_server:MissingReference', ...
              'Reference file not found: %s', referenceFile);
    end
    raw = readmatrix(referenceFile);
    if isempty(raw) || size(raw, 2) < 2
        error('matlab_controller_server:BadReference', ...
              'Reference file %s must have columns tick,r1[,r2,...].', referenceFile);
    end
    refTraj = raw(:, 2:end);
    if any(~isfinite(refTraj(:)))
        error('matlab_controller_server:BadReference', ...
              'Reference file %s contains non-finite values.', referenceFile);
    end
end

function stop_and_delete_timer(t)
    try
        if isvalid(t)
            stop(t);
            delete(t);
        end
    catch
    end
end

function clear_udp_port(u)
    try
        clear u
    catch
    end
end

function value = unpack_u32_be(bytes)
    tmp = typecast(uint8(bytes), 'uint32');
    value = double(swapbytes(tmp));
end

function values = unpack_f32_be_vec(bytes)
    % bytes is a big-endian float32 payload; returns a double column vector.
    words = swapbytes(typecast(uint8(bytes(:))', 'uint32'));
    values = double(typecast(words, 'single'))';
end

function bytes = pack_response(seq, values)
    values = single(values(:));
    header = typecast(swapbytes(uint32([seq, numel(values)])), 'uint8');
    payload = typecast(swapbytes(typecast(values', 'uint32')), 'uint8');
    bytes = [header, payload]';
end
