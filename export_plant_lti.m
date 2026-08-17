function outPath = export_plant_lti(outPath, modelIndex)
%EXPORT_PLANT_LTI  Write AllModels(idx).sys to the .lti file cpp_controller reads.
%
%   export_plant_lti                       % -> plant.lti from AllModels(10).sys
%   export_plant_lti('plant_run1.lti', 10)
%
%   Bridges the primary and backup control paths: the plant identified by
%   fit_sysid_from_capture and used by mpc_test is handed to the native
%   controller unchanged, so the two run the SAME model and any difference in
%   behaviour is attributable to the controller rather than to the plant.
%
%   The .lti format is plain text -- see cpp_controller/model_io.hpp. It carries
%   A, B, C, D and the sample time, which is all the native MPC needs.
%
%   Verify afterwards with:
%       cpp_controller.exe --mode mpc --model plant.lti --target <value>
%   which prints the observer pole it computed. That number should match what
%   mpc_test computes for the same model; if it does not, the two controllers
%   are not running the same plant and nothing downstream is comparable.

    if nargin < 1 || isempty(outPath),    outPath = 'plant.lti'; end
    if nargin < 2 || isempty(modelIndex), modelIndex = 10;       end

    Ts = 0.01;   % must match mpc_test's P.controlFs = 100 Hz

    if evalin('base', 'exist(''AllModels'', ''var'')')
        AllModels = evalin('base', 'AllModels');
    else
        matPath = fullfile(pwd, 'AllModels.mat');
        if ~isfile(matPath)
            error('export_plant_lti:MissingAllModels', ...
                  'AllModels not in the base workspace and %s not found.', matPath);
        end
        loaded = load(matPath, 'AllModels');
        AllModels = loaded.AllModels;
    end

    if numel(AllModels) < modelIndex || ~isfield(AllModels, 'sys')
        error('export_plant_lti:BadAllModels', ...
              'AllModels has no entry %d with a .sys field.', modelIndex);
    end
    sys = AllModels(modelIndex).sys;
    if isempty(sys)
        error('export_plant_lti:EmptyModel', 'AllModels(%d).sys is empty.', modelIndex);
    end

    if isa(sys, 'ss')
        % Only reachable if the Control System Toolbox is installed; on this
        % machine it is not, and models are stored as plain structs.
        [A, B, C, D] = ssdata(sys);
    elseif isstruct(sys) && all(isfield(sys, {'A', 'B', 'C', 'D'}))
        A = double(sys.A); B = double(sys.B);
        C = double(sys.C); D = double(sys.D);
        if isfield(sys, 'Ts') && ~isempty(sys.Ts) && sys.Ts ~= 0 && abs(sys.Ts - Ts) > 1e-12
            error('export_plant_lti:RateMismatch', ...
                  'Model Ts=%g s but the controller runs at %g s.', sys.Ts, Ts);
        end
    else
        error('export_plant_lti:UnsupportedModel', ...
              'AllModels(%d).sys must be an ss object or a struct with A,B,C,D.', modelIndex);
    end

    n = size(A, 1); m = size(B, 2); p = size(C, 1);
    if size(A,2) ~= n || size(B,1) ~= n || size(C,2) ~= n || ...
       size(D,1) ~= p || size(D,2) ~= m
        error('export_plant_lti:Inconsistent', 'A/B/C/D dimensions are inconsistent.');
    end
    if ~all(isfinite([A(:); B(:); C(:); D(:)]))
        error('export_plant_lti:NonFinite', 'Model contains non-finite entries.');
    end

    fid = fopen(outPath, 'w');
    if fid < 0
        error('export_plant_lti:CannotWrite', 'Could not open %s for writing.', outPath);
    end
    cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>

    fprintf(fid, 'LTI 1\n');
    fprintf(fid, '# exported from AllModels(%d).sys on %s\n', modelIndex, datestr(now, 31));
    fprintf(fid, 'Ts %.17g\n', Ts);
    fprintf(fid, 'n %d\nm %d\np %d\n', n, m, p);
    write_block(fid, 'A', A);
    write_block(fid, 'B', B);
    write_block(fid, 'C', C);
    write_block(fid, 'D', D);

    fprintf('Wrote %s  (n=%d m=%d p=%d Ts=%g)\n', outPath, n, m, p, Ts);
    fprintf('Check the native controller agrees on this model:\n');
    fprintf('  cpp_controller.exe --mode mpc --model %s --target 0\n', outPath);
end

function write_block(fid, name, M)
    fprintf(fid, '%s\n', name);
    for i = 1:size(M, 1)
        fprintf(fid, '%.17g ', M(i, :));
        fprintf(fid, '\n');
    end
end
