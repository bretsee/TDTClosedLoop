function out = crossval_model(fitFile, valFile, channel, opts)
%CROSSVAL_MODEL  Fit on one capture, score on a second independent capture.
%
%   out = crossval_model('capture_rig_run1.csv', 'capture_rig_run2.csv', 7)
%
%   fit_sysid_from_capture already holds out the last 30% of a record. That
%   guards against fitting order to training noise, but it cannot catch anything
%   that is stable WITHIN a record and not across records -- electrode drift, a
%   slow anaesthetic trend, a preparation that changed between runs. Those look
%   like plant dynamics to a single-record fit.
%
%   Two numbers are reported, and the difference between them is the useful part:
%
%     trainedOffsets  the model applied exactly as it would be in the loop, with
%                     the DC offsets learned during fitting. This is the honest
%                     deployment number.
%     recenteredFit   the same model scored after re-centring the validation
%                     record on its own means.
%
%   If recenteredFit is good but trainedOffsets is poor, the DYNAMICS transferred
%   and only the operating point moved -- a baseline shift between records, not a
%   bad model. That is a recoverable situation (re-reference, or re-fit including
%   both records) and is worth distinguishing at the rig from an actually wrong
%   model, where both numbers collapse together.
%
%   NO TOOLBOXES.

    if nargin < 3 || isempty(channel), channel = 1;      end
    if nargin < 4 || isempty(opts),    opts = struct();  end
    opts = set_default(opts, 'skipTicks',       50);
    opts = set_default(opts, 'inputDelayTicks',  1);

    fprintf('=== CROSS-RECORD VALIDATION ===\n');
    fprintf('  fit on:   %s\n', fitFile);
    fprintf('  score on: %s\n', valFile);
    fprintf('  output channel: %d\n\n', channel);

    evalc(sprintf('r = fit_sysid_from_capture(''%s'', struct(''useOutputs'',%d));', ...
                  fitFile, channel));   %#ok<EVLCS>

    T = readtable(valFile);
    names = T.Properties.VariableNames;
    U = table2array(T(:, startsWith(names, 'u')));
    Y = table2array(T(:, startsWith(names, 'y')));

    % Identical alignment and warm-up discard to the fitter, or the comparison
    % is not like for like.
    d = opts.inputDelayTicks;
    if d > 0
        U = U(1:end-d, :);
        Y = Y(1+d:end, :);
    end
    U = U(opts.skipTicks+1:end, r.useInputs);
    Y = Y(opts.skipTicks+1:end, channel);

    trainedFit   = score(r, U - r.uOffset(:).',        Y - r.yOffset);
    recenteredFit = score(r, U - mean(U, 1),           Y - mean(Y));

    fprintf('  in-record valFit (from the fit itself): %7.2f %%\n', r.valFit);
    fprintf('  cross-record, trained offsets:          %7.2f %%\n', trainedFit);
    fprintf('  cross-record, re-centred:               %7.2f %%\n', recenteredFit);
    fprintf('\n');

    % Degenerate case first. If the in-record fit was already ~nothing there was
    % never a model to transfer, and reporting "did not transfer" would send you
    % looking for drift between records when the real problem is upstream: this
    % channel has no identifiable response at all.
    if r.valFit < 1.0
        fprintf('  VERDICT: there was no model to begin with -- in-record valFit is\n');
        fprintf('           %.2f%%. This channel has no identifiable linear response.\n', r.valFit);
        fprintf('           Cross-record numbers are meaningless here. Go back to the\n');
        fprintf('           sweep and pick a channel with |corr| > 0.1 (branch C1).\n');
        out.verdict = 'no-model';
    elseif recenteredFit < 0.5 * r.valFit
        fprintf('  VERDICT: the model did NOT transfer. It describes record-specific\n');
        fprintf('           structure, not the plant. See branch D2 -- do not deploy it.\n');
        out.verdict = 'failed';
    elseif trainedFit < 0.5 * recenteredFit
        fprintf('  VERDICT: dynamics transferred, but the OPERATING POINT MOVED between\n');
        fprintf('           records (baseline drift). The model is usable; the DC offset\n');
        fprintf('           is not. See branch D3.\n');
        out.verdict = 'offset-drift';
    else
        fprintf('  VERDICT: model generalises across records. This is the number to trust.\n');
        out.verdict = 'ok';
    end

    out.valFit        = r.valFit;
    out.trainedFit    = trainedFit;
    out.recenteredFit = recenteredFit;
    out.sys           = r.sys;
    out.order         = r.order;
end

% =========================================================================

function f = score(r, Uc, Yc)
    % Free-run simulation: the model gets no measurement feedback, only the
    % input. This is deliberately the hardest test -- a one-step-ahead predictor
    % would look far better and would not tell us whether the dynamics are right.
    x  = zeros(size(r.sys.A, 1), 1);
    yh = zeros(numel(Yc), 1);
    for k = 1:numel(Yc)
        yh(k) = r.sys.C * x + r.sys.D * Uc(k, :).';
        x     = r.sys.A * x + r.sys.B * Uc(k, :).';
    end
    denom = norm(Yc - mean(Yc));
    if denom < eps
        f = NaN;
    else
        f = 100 * (1 - norm(Yc - yh) / denom);
    end
end

function s = set_default(s, field, value)
    if ~isfield(s, field) || isempty(s.(field))
        s.(field) = value;
    end
end
