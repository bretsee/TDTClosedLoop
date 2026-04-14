function set_mpc_test_target(varargin)
% SET_MPC_TEST_TARGET  Store a simple positive MPC target for mpc_test.
%
% Usage:
%   set_mpc_test_target
%   set_mpc_test_target(10)
%   set_mpc_test_target([10; 10; 10])
%
% This helper is meant for bench validation of the MATLAB -> C++ -> UDP path.
% It updates:
%   1) base-workspace MPC_TARGET
%   2) local AllModels.mat (if present)
%
% After changing the target, it resets mpc_test's persistent state so the next
% call reinitializes cleanly.

    if nargin < 1
        target = 10;
    else
        target = varargin{1};
    end

    target = double(target(:));

    matPath = fullfile(pwd, 'AllModels.mat');
    if isfile(matPath)
        loaded = load(matPath);
        if isfield(loaded, 'AllModels') && numel(loaded.AllModels) >= 10 ...
                && isfield(loaded.AllModels, 'sys') && ~isempty(loaded.AllModels(10).sys)
            p = infer_output_count(loaded.AllModels(10).sys);
            target = fit_length_local(target, p);
            MPC_TARGET = target; %#ok<NASGU>
            AllModels = loaded.AllModels; %#ok<NASGU>
            save(matPath, 'AllModels', 'MPC_TARGET');
            fprintf('Updated %s with MPC_TARGET = %s\n', matPath, mat2str(target.'));
        else
            warning('set_mpc_test_target:BadAllModels', ...
                    'AllModels.mat exists but does not contain a usable AllModels(10).sys entry.');
        end
    else
        fprintf('AllModels.mat not found in %s; only base-workspace MPC_TARGET was updated.\n', pwd);
    end

    assignin('base', 'MPC_TARGET', target);
    mpc_test([]);
    fprintf('Base-workspace MPC_TARGET set to %s and mpc_test state reset.\n', mat2str(target.'));
end

function p = infer_output_count(sys)
    if isa(sys, 'ss')
        p = size(sys.C, 1);
        return;
    end

    if isstruct(sys) && isfield(sys, 'C') && ~isempty(sys.C)
        p = size(sys.C, 1);
        return;
    end

    p = 1;
end

function x = fit_length_local(x, n)
    if numel(x) < n
        x = [x; repmat(x(end), n - numel(x), 1)];
    elseif numel(x) > n
        x = x(1:n);
    end
end
