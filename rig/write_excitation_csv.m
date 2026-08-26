function write_excitation_csv(outFile, kind, nTicks, m, opts)
%WRITE_EXCITATION_CSV  Export a designed excitation to CSV for C++ replay.
%
%   write_excitation_csv('design_sal2.csv', 'impulse', 7000, 8, ...
%       struct('pulseAmps', {[5 10 18 25]}, 'gapJitterMeanTicks', 8, ...
%              'uMax', 25, 'seed', 777))
%
%   Writes tick,u1..uM -- the format cpp_controller.exe --play replays
%   verbatim and rig/validate_impulse_design.py audits. This is the design
%   half of the MATLAB-free probe path: MATLAB generates and is then OUT of
%   the real-time loop entirely (the 2026-08-17 saline run showed MATLAB
%   server stalls stretching probes to 70-90 ms and dropping 5.1% of them).

    if nargin < 5 || isempty(opts)
        opts = struct();
    end
    U = make_excitation(kind, nTicks, m, opts);

    fid = fopen(outFile, 'w');
    if fid < 0
        error('write_excitation_csv:OpenFailed', 'cannot open %s', outFile);
    end
    fprintf(fid, 'tick');
    fprintf(fid, ',u%d', 1:m);
    fprintf(fid, '\n');
    for k = 1:size(U, 1)
        fprintf(fid, '%d', k);
        fprintf(fid, ',%.9g', U(k, :));
        fprintf(fid, '\n');
    end
    fclose(fid);
    fprintf('write_excitation_csv: wrote %s (%d ticks x %d channels)\n', ...
            outFile, size(U, 1), m);

    % Metadata sidecar (NOT in-file comments: cpp_controller's load_csv_prefix
    % parses every non-header line with atof, so a comment line would replay as
    % a row of zeros). Records everything the validator and the lab notebook
    % need to reconstruct the design's intent.
    metaFile = regexprep(outFile, '\.csv$', '_meta.json');
    meta = struct('kind', char(kind), 'nTicks', nTicks, 'm', m, ...
                  'generated', datestr(now, 'yyyy-mm-dd HH:MM:SS'), ...
                  'generator', 'make_excitation.m');
    fn = fieldnames(opts);
    for i = 1:numel(fn)
        meta.(fn{i}) = opts.(fn{i});
    end
    fid = fopen(metaFile, 'w');
    if fid >= 0
        fprintf(fid, '%s\n', jsonencode(meta));
        fclose(fid);
        fprintf('write_excitation_csv: wrote %s\n', metaFile);
    end
end
