% create_example_allmodels.m
% Creates a minimal AllModels.mat containing a toy LTI model and MPC_TARGET
% for quick functional testing of mpc_test when launched from the C++ engine.

% Create a 10-entry AllModels struct and put a simple lowpass at index 10
AllModels = repmat(struct('sys', []), 10, 1);

% Create a discrete-time first-order toy model without requiring the
% Control System Toolbox. This avoids needing `tf`/`ss` in batch mode.
P.controlFs = 100; % controller rate used by mpc_test
Ts = 1 / P.controlFs;

% Continuous-time poles for a safe lowpass: G(s) = 1 / (s + 5)
% Discretize analytically for the single-state case:
ac = -5.0;
bc = 1.0;
cc = 1.0;
dc = 0.0;

Ad = exp(ac * Ts);
Bd = (1.0 - exp(ac * Ts)) * (1.0 / (-ac)) * bc; % integral of exp(ac*t)*bc dt

AllModels(10).sys = struct('A', Ad, 'B', Bd, 'C', cc, 'D', dc, 'Ts', Ts);

% MPC_TARGET sized to model output dimension
MPC_TARGET = zeros(1, 1);

save('AllModels.mat', 'AllModels', 'MPC_TARGET');
fprintf('Saved AllModels.mat and MPC_TARGET in current folder.\n');
