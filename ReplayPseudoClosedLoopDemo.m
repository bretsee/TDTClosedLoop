% ReplayPseudoClosedLoopDemo
% Pseudo-real-time closed-loop demo using prerecorded TDT data.
%
% What it does:
% - loads a recorded TDT block with TDTbin2mat
% - selects one stream store (default: Wav2)
% - computes 10 ms mean-absolute-value features
% - feeds those features into a simple pseudo controller at 100 Hz
% - animates input features and output control channels as if they were live
%
% This is designed for presentation/demo use when the full live hardware path
% is too risky or unnecessary.

clear;
clc;

%% User configuration
SDKPATH = 'C:\Users\brets\Desktop\TDTMatlabSDK\TDTSDK';
BLOCK_PATH = 'C:\Users\brets\Downloads\Acute_122023\ExperimentBL-231220-234444';
STORE_NAME = 'Wav2';          % Recommended first choice from this dataset
CONTROL_FS = 100;             % 100 Hz controller/update rate
WINDOW_MS = 10;               % 10 ms feature window
INPUT_CHANNEL_COUNT = 8;      % Number of replayed input channels to use
OUTPUT_CHANNEL_COUNT = 8;     % Number of pseudo control channels to display
MAX_SECONDS_TO_REPLAY = 30;   % Keep the demo concise by default
PLAYBACK_SPEED = 1.0;         % 1.0 = real-time, 2.0 = 2x speed, etc.

% Pseudo-controller tuning for a visually clear demo.
CONTROL_MIN = 0;
CONTROL_MAX = 40;
SMOOTHING_ALPHA = 0.2;        % Higher -> faster control response
CHANNEL_PHASE_GAIN = 0.15;    % Adds visible per-channel structure

%% Load SDK and block
addpath(genpath(SDKPATH));
fprintf('Loading block: %s\n', BLOCK_PATH);
data = TDTbin2mat(BLOCK_PATH);

if ~isfield(data, 'streams') || ~isfield(data.streams, STORE_NAME)
    error('ReplayPseudoClosedLoopDemo:MissingStore', ...
          'Store "%s" was not found in the block.', STORE_NAME);
end

stream = data.streams.(STORE_NAME);
raw = double(stream.data);
fs = double(stream.fs);

if isempty(raw)
    error('ReplayPseudoClosedLoopDemo:EmptyStream', ...
          'Store "%s" contains no samples.', STORE_NAME);
end

% TDT stream matrices are typically [channels x samples].
if size(raw, 1) > size(raw, 2)
    raw = raw.';
end

nChannelsAvailable = size(raw, 1);
nSamplesAvailable = size(raw, 2);
inputChannelCount = min(INPUT_CHANNEL_COUNT, nChannelsAvailable);
raw = raw(1:inputChannelCount, :);

fprintf('Using store %s at %.1f Hz with %d input channels.\n', ...
        STORE_NAME, fs, inputChannelCount);

%% Convert raw stream to 100 Hz feature frames
samplesPerWindow = max(1, round(fs * (WINDOW_MS / 1000)));
controlDt = 1 / CONTROL_FS;

maxSamplesToReplay = min(nSamplesAvailable, round(MAX_SECONDS_TO_REPLAY * fs));
raw = raw(:, 1:maxSamplesToReplay);

nFrames = floor(size(raw, 2) / samplesPerWindow);
if nFrames < 2
    error('ReplayPseudoClosedLoopDemo:TooShort', ...
          'Not enough data to build replay frames.');
end

features = zeros(inputChannelCount, nFrames);
for k = 1:nFrames
    idx0 = (k - 1) * samplesPerWindow + 1;
    idx1 = idx0 + samplesPerWindow - 1;
    window = raw(:, idx0:idx1);
    features(:, k) = mean(abs(window), 2);
end

timeAxis = (0:nFrames-1) * controlDt;

%% Pseudo controller
% The goal is not model fidelity; it is a believable, responsive control
% output that changes with the replayed input.
featureWeights = linspace(1.0, 0.4, inputChannelCount).';
featureWeights = featureWeights / sum(featureWeights);

uHistory = zeros(OUTPUT_CHANNEL_COUNT, nFrames);
uPrev = zeros(OUTPUT_CHANNEL_COUNT, 1);

for k = 1:nFrames
    feat = features(:, k);

    % Normalize to a stable scale for the demo.
    featNorm = feat / max(max(features(:)), eps);

    % Base control signal from weighted feature energy.
    baseDrive = featureWeights.' * featNorm;

    % Add a small deterministic phase offset per channel so outputs are
    % visibly distinct but still correlated with the input features.
    target = zeros(OUTPUT_CHANNEL_COUNT, 1);
    for ch = 1:OUTPUT_CHANNEL_COUNT
        phaseTerm = 0.5 + 0.5 * sin(2 * pi * (k / 40) + (ch - 1) * CHANNEL_PHASE_GAIN * 2 * pi);
        target(ch) = CONTROL_MAX * min(max(0.7 * baseDrive + 0.3 * phaseTerm, 0), 1);
    end

    % Smooth outputs so they look controller-like, not frame-to-frame noisy.
    uPrev = (1 - SMOOTHING_ALPHA) * uPrev + SMOOTHING_ALPHA * target;
    uHistory(:, k) = min(max(uPrev, CONTROL_MIN), CONTROL_MAX);
end

%% Plot setup
figure('Name', 'Pseudo Real-Time Closed Loop Demo', 'Color', 'w');
tiledlayout(3, 1, 'TileSpacing', 'compact', 'Padding', 'compact');

ax1 = nexttile;
plot(ax1, timeAxis, features(1, :), 'Color', [0.85 0.85 0.85]);
hold(ax1, 'on');
featureLine = plot(ax1, timeAxis(1), features(1, 1), 'LineWidth', 1.5, 'Color', [0.1 0.35 0.75]);
xline1 = xline(ax1, timeAxis(1), '--k');
title(ax1, sprintf('Input Feature Replay (%s, channel 1 MAV)', STORE_NAME));
ylabel(ax1, 'Feature');
xlim(ax1, [timeAxis(1) timeAxis(end)]);

ax2 = nexttile;
imagesc(ax2, timeAxis(1), 1:inputChannelCount, features(:, 1));
axis(ax2, 'xy');
colorbar(ax2);
title(ax2, 'Input Features Across Channels');
ylabel(ax2, 'Input Channel');
xlim(ax2, [timeAxis(1) timeAxis(end)]);

ax3 = nexttile;
colors = lines(OUTPUT_CHANNEL_COUNT);
controlLines = gobjects(OUTPUT_CHANNEL_COUNT, 1);
hold(ax3, 'on');
for ch = 1:OUTPUT_CHANNEL_COUNT
    controlLines(ch) = plot(ax3, timeAxis(1), uHistory(ch, 1), ...
        'LineWidth', 1.5, 'Color', colors(ch, :));
end
xline3 = xline(ax3, timeAxis(1), '--k');
title(ax3, 'Pseudo Control Outputs');
xlabel(ax3, 'Time (s)');
ylabel(ax3, 'Control Value');
xlim(ax3, [timeAxis(1) timeAxis(end)]);
ylim(ax3, [CONTROL_MIN CONTROL_MAX + 2]);

legend(ax3, arrayfun(@(ch) sprintf('Out %d', ch), 1:OUTPUT_CHANNEL_COUNT, 'UniformOutput', false), ...
    'Location', 'eastoutside');

%% Animate replay
fprintf('Starting pseudo-real-time replay for %.1f s at %.1fx speed.\n', ...
        timeAxis(end), PLAYBACK_SPEED);

tic;
for k = 1:nFrames
    set(featureLine, 'XData', timeAxis(1:k), 'YData', features(1, 1:k));
    set(xline1, 'Value', timeAxis(k));

    imagesc(ax2, timeAxis(1:k), 1:inputChannelCount, features(:, 1:k));
    axis(ax2, 'xy');
    xlim(ax2, [timeAxis(1) timeAxis(end)]);

    for ch = 1:OUTPUT_CHANNEL_COUNT
        set(controlLines(ch), 'XData', timeAxis(1:k), 'YData', uHistory(ch, 1:k));
    end
    set(xline3, 'Value', timeAxis(k));

    drawnow limitrate;

    targetElapsed = timeAxis(k) / PLAYBACK_SPEED;
    actualElapsed = toc;
    pauseTime = targetElapsed - actualElapsed;
    if pauseTime > 0
        pause(pauseTime);
    end
end

fprintf('Replay complete.\n');

