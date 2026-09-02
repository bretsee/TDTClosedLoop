// mpc_controller.hpp -- native C++ port of mpc_test.m.
//
// Condensed linear MPC with a hold-last input parameterisation, a steady-state
// Kalman observer, and box constraints on the commanded stimulation amplitude.
// The formulation is deliberately IDENTICAL to the MATLAB controller so the two
// can be compared tick-for-tick on the same plant model:
//
//   predict   y(k+1..k+N) = F*xhat + G*U
//   hold-last U = S*z,  z = [u_0; ...; u_{Nu-1}]
//   minimise  (F*xhat + GS*z - r)' Qbar (F*xhat + GS*z - r) + z' S' Rbar S z
//   subject to  umin <= z <= umax
//
// which condenses to  min 1/2 z'Hz + q'z  with
//   H = GS' Qbar GS + S' Rbar S      (built once)
//   q = GS' Qbar (F*xhat - r)        (rebuilt each tick)
//
// THE OBSERVER IS THE PART TO WATCH. In the MATLAB version this silently
// degraded to L = 0 whenever pole placement was unavailable, which left the
// controller running fully open-loop while still looking healthy. That defect is
// not reproduced here: the gain is computed by Riccati iteration with no optional
// dependency, the estimator's stability is verified before it is accepted, and a
// zero gain is only ever adopted with a loud warning and a flag visible in
// status(). See observer_active().
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <sstream>
#include <string>
#include <vector>

#include "controller.hpp"
#include "linalg.hpp"
#include "model_io.hpp"
#include "qp_solver.hpp"

namespace ctl {

struct MpcConfig {
    int    N  = 20;         // prediction horizon
    int    Nu = 2;          // control horizon (hold-last beyond this)
    double q_weight = 1.0;  // output tracking weight (Q = q_weight * I)
    double r_weight = 1.0;  // input effort weight   (R = r_weight * I)
    // Per-output / per-input weight vectors (MIMO: feature scales differ). When
    // non-empty they OVERRIDE the scalars; must be sized p / m respectively.
    std::vector<double> q_weights;
    std::vector<double> r_weights;
    double umin = 0.0;
    double umax = 40.0;     // physical stimulator amplitude ceiling
    double qScale = 1e-2;   // observer process/measurement noise ratio
    int    qp_iters = 200;
    double qp_tol = 1e-7;
    bool   use_observer = true;   // false = deliberate feedforward arm (loud)
};

class MpcController : public IController {
public:
    MpcController(const LtiModel& model, const MpcConfig& cfg, int output_count)
        : M_(model), cfg_(cfg), out_count_(output_count) {
        n_ = M_.n; m_ = M_.m; p_ = M_.p;

        // Hand-built models (selftest, tools) may carry no offset vectors;
        // size them to zeros so centered arithmetic is always well-defined.
        if ((int)M_.uOff.size() != m_) M_.uOff.assign((size_t)m_, 0.0);
        if ((int)M_.yOff.size() != p_) M_.yOff.assign((size_t)p_, 0.0);

        build_prediction_matrices();
        build_hessian();
        if (cfg_.use_observer) build_observer();

        xhat_.assign((size_t)n_, 0.0);
        u_last_.assign((size_t)m_, 0.0);          // RAW units; 0 = stim off
        target_stack_.assign((size_t)(p_ * cfg_.N), 0.0);   // CENTERED (r - yOff)
        z_.assign((size_t)(m_ * cfg_.Nu), 0.0);
    }

    // Constant target, repeated over the horizon. r is RAW (feature units); the
    // stack is stored CENTERED against the model's yOffset (mpc_test.m:111).
    void set_target(const std::vector<double>& r) {
        Vec col((size_t)p_, 0.0);
        for (int i = 0; i < p_; ++i) {
            const double raw = (i < (int)r.size()) ? r[(size_t)i]
                                                   : (r.empty() ? 0.0 : r.back());
            col[(size_t)i] = raw - M_.yOff[(size_t)i];
        }
        for (int k = 0; k < cfg_.N; ++k)
            for (int i = 0; i < p_; ++i)
                target_stack_[(size_t)(k * p_ + i)] = col[(size_t)i];
    }

    // Reference PREVIEW: cols[k] is the RAW p-vector target k ticks ahead.
    // Crops K>N; pads by holding the last column (mpc_test.m build_reference_stack).
    void set_target_preview(const std::vector<Vec>& cols) {
        if (cols.empty()) return;
        for (int k = 0; k < cfg_.N; ++k) {
            const Vec& col = cols[(size_t)std::min<size_t>((size_t)k, cols.size() - 1)];
            for (int i = 0; i < p_; ++i) {
                const double raw = (i < (int)col.size()) ? col[(size_t)i] : col.back();
                target_stack_[(size_t)(k * p_ + i)] = raw - M_.yOff[(size_t)i];
            }
        }
    }

    bool observer_active() const { return observer_active_; }
    double observer_pole() const { return observer_pole_; }
    int    last_qp_iters() const { return last_iters_; }

    std::string name() const override { return "mpc"; }

    void reset() override {
        std::fill(xhat_.begin(), xhat_.end(), 0.0);
        std::fill(u_last_.begin(), u_last_.end(), 0.0);
        std::fill(z_.begin(), z_.end(), 0.0);
        qp_.warm_start(z_);
    }

    std::vector<double> step(const std::vector<double>& features) override {
        // ---- feature-map bounds guard (once, loudly) ----------------------
        // A mapped index past the arriving feature width was previously a
        // SILENT out-of-bounds read. Now: loud fault, hold-last forever.
        if (!feature_fault_) {
            for (int i = 0; i < p_; ++i)
                if (feature_map_index(i) >= (int)features.size()) {
                    std::fprintf(stderr,
                        "FATAL: --feature-map index %d exceeds the arriving feature "
                        "count %zu; holding last command. Fix the map or the loop's "
                        "input width.\n", feature_map_index(i) + 1, features.size());
                    feature_fault_ = true;
                }
        }
        if (feature_fault_) {
            Vec out((size_t)out_count_, 0.0);
            for (int i = 0; i < out_count_ && i < m_; ++i) out[(size_t)i] = u_last_[(size_t)i];
            return out;
        }

        // ---- measurement (centered: yk_c = y - yOff, mpc_test.m:85) --------
        Vec yk((size_t)p_, 0.0);
        for (int i = 0; i < p_; ++i)
            yk[(size_t)i] = features[(size_t)feature_map_index(i)] - M_.yOff[(size_t)i];
        sanitize(yk, 1e4);

        // u_last_ is stored RAW (0 = stim off); the model runs centered.
        Vec u_last_c((size_t)m_);
        for (int i = 0; i < m_; ++i)
            u_last_c[(size_t)i] = u_last_[(size_t)i] - M_.uOff[(size_t)i];

        // ---- observer update ---------------------------------------------
        Vec x_pred = matvec(M_.A, xhat_);
        {
            const Vec bu = matvec(M_.B, u_last_c);
            for (int i = 0; i < n_; ++i) x_pred[(size_t)i] += bu[(size_t)i];
        }
        sanitize(x_pred, 1e6);

        if (observer_active_) {
            Vec y_pred = matvec(M_.C, x_pred);
            const Vec du = matvec(M_.D, u_last_c);
            for (int i = 0; i < p_; ++i) y_pred[(size_t)i] += du[(size_t)i];
            sanitize(y_pred, 1e6);

            Vec innov((size_t)p_);
            for (int i = 0; i < p_; ++i) innov[(size_t)i] = yk[(size_t)i] - y_pred[(size_t)i];

            const Vec corr = matvec(L_, innov);
            for (int i = 0; i < n_; ++i) xhat_[(size_t)i] = x_pred[(size_t)i] + corr[(size_t)i];
        } else {
            xhat_ = x_pred;
        }
        sanitize(xhat_, 1e6);

        // ---- linear term --------------------------------------------------
        // e = F*xhat - r_stack (stack already centered; per-step preview column)
        Vec fx = matvec(F_, xhat_);
        Vec e((size_t)(p_ * cfg_.N));
        for (size_t i = 0; i < e.size(); ++i) e[i] = fx[i] - target_stack_[i];
        sanitize(e, 1e6);

        Vec q = matvec(GStQbar_, e);
        sanitize(q, 1e9);

        // ---- solve (z is CENTERED command; box shifted by -uOff) ----------
        qp_.warm_start(z_);
        Vec z_new;
        const QpResult res = qp_.solve(q, z_new);
        last_iters_ = res.iters;
        last_converged_ = res.converged;

        Vec u((size_t)m_);          // RAW output
        bool usable = (int)z_new.size() == m_ * cfg_.Nu;
        if (usable)
            for (int i = 0; i < m_; ++i)
                if (!std::isfinite(z_new[(size_t)i])) { usable = false; break; }

        if (usable) {
            z_ = z_new;
            for (int i = 0; i < m_; ++i)
                u[(size_t)i] = z_new[(size_t)i] + M_.uOff[(size_t)i];   // un-center
        } else {
            // Fail-safe: hold the previous command rather than emit a fresh one
            // from a solver that did not return a usable answer.
            u = u_last_;
            ++qp_failures_;
        }

        for (int i = 0; i < m_; ++i)
            u[(size_t)i] = std::min(std::max(u[(size_t)i], cfg_.umin), cfg_.umax);
        u_last_ = u;

        // Pad or truncate to the wire's output width.
        Vec out((size_t)out_count_, 0.0);
        for (int i = 0; i < out_count_ && i < m_; ++i) out[(size_t)i] = u[(size_t)i];
        return out;
    }

    std::string status() const override {
        std::ostringstream os;
        os << "qpIters=" << last_iters_ << (last_converged_ ? "" : "(cap)")
           << " qpFail=" << qp_failures_
           << " observer=" << (observer_active_ ? "on"
                               : (cfg_.use_observer ? "OFF" : "off(DELIBERATE)"))
           << " obsPole=" << observer_pole_
           << " offsets=" << (M_.has_offsets ? "applied" : "none");
        if (feature_fault_) os << " FEATURE-MAP-FAULT(hold-last)";
        return os.str();
    }

    // Explicit measurement remap, so a model identified on channel k can be run
    // without editing source (the mpc_test.m feature_map problem).
    void set_feature_map(const std::vector<int>& idx) { feature_map_ = idx; }

private:
    int feature_map_index(int i) const {
        if (i < (int)feature_map_.size()) return feature_map_[(size_t)i];
        return i;
    }

    void build_prediction_matrices() {
        const int N = cfg_.N;
        F_ = Mat(p_ * N, n_, 0.0);
        Mat G(p_ * N, m_ * N, 0.0);

        // Apow tracks A^i; CA_pow_B[d] caches C*A^d*B so the double loop below
        // does not recompute matrix powers O(N^2) times.
        std::vector<Mat> CAB;
        CAB.reserve((size_t)N);
        Mat Ad = Mat::identity(n_);
        for (int d = 0; d < N; ++d) {
            CAB.push_back(matmul(matmul(M_.C, Ad), M_.B));   // C*A^d*B
            Ad = matmul(M_.A, Ad);
        }

        Mat Apow = Mat::identity(n_);
        for (int i = 1; i <= N; ++i) {
            Apow = matmul(M_.A, Apow);                       // A^i
            const Mat CApow = matmul(M_.C, Apow);            // C*A^i
            for (int r = 0; r < p_; ++r)
                for (int c = 0; c < n_; ++c)
                    F_((i - 1) * p_ + r, c) = CApow(r, c);

            for (int j = 1; j <= i; ++j) {
                const Mat& blk = CAB[(size_t)(i - j)];
                for (int r = 0; r < p_; ++r)
                    for (int c = 0; c < m_; ++c) {
                        double v = blk(r, c);
                        if (i == j) v += M_.D(r, c);
                        G((i - 1) * p_ + r, (j - 1) * m_ + c) = v;
                    }
            }
        }

        // hold-last map S: u_i = z_{min(i, Nu-1)}
        S_ = Mat(m_ * N, m_ * cfg_.Nu, 0.0);
        for (int i = 1; i <= N; ++i) {
            const int j = std::min(i, cfg_.Nu);
            for (int c = 0; c < m_; ++c) S_((i - 1) * m_ + c, (j - 1) * m_ + c) = 1.0;
        }

        GS_ = matmul(G, S_);
    }

    void build_hessian() {
        const int N = cfg_.N;
        // Per-output / per-input weight vectors override the scalars (MIMO:
        // heterogeneous feature scales -- the volt-scale lesson, 2026-08-31).
        Mat Q = Mat::identity(p_);
        for (int i = 0; i < p_; ++i)
            Q(i, i) = (i < (int)cfg_.q_weights.size()) ? cfg_.q_weights[(size_t)i]
                                                       : cfg_.q_weight;
        Mat R = Mat::identity(m_);
        for (int i = 0; i < m_; ++i)
            R(i, i) = (i < (int)cfg_.r_weights.size()) ? cfg_.r_weights[(size_t)i]
                                                       : cfg_.r_weight;

        const Mat Qbar = kron_identity(N, Q);
        const Mat Rbar = kron_identity(N, R);

        const Mat GSt = transpose(GS_);
        GStQbar_ = matmul(GSt, Qbar);                       // cached for the tick

        const Mat St = transpose(S_);
        Mat H = add(matmul(GStQbar_, GS_), matmul(matmul(St, Rbar), S_));
        H = symmetrize(H);

        // z is the CENTERED command, so the physical box [umin, umax] shifts by
        // each input's own offset (mpc_test.m:223-224).
        const int nz = m_ * cfg_.Nu;
        Vec lb((size_t)nz), ub((size_t)nz);
        for (int k = 0; k < nz; ++k) {
            const int c = k % m_;
            lb[(size_t)k] = cfg_.umin - M_.uOff[(size_t)c];
            ub[(size_t)k] = cfg_.umax - M_.uOff[(size_t)c];
        }
        qp_.setup(H, lb, ub, cfg_.qp_iters, cfg_.qp_tol);
    }

    // Steady-state Kalman gain by Riccati iteration -- no toolbox, no optional
    // dependency, and therefore no silent fallback path.
    void build_observer() {
        const Mat Q = scale(Mat::identity(n_), cfg_.qScale);
        const Mat R = Mat::identity(p_);

        Mat Pp = Mat::identity(n_);
        Mat K;
        bool ok = false;

        for (int iter = 0; iter < 5000; ++iter) {
            const Mat CP  = matmul(M_.C, Pp);                       // C*Pp
            const Mat S   = add(matmul(CP, transpose(M_.C)), R);    // C*Pp*C' + R
            Mat X;
            // K = Pp*C' * inv(S)  <=>  S' X' = C*Pp  (S symmetric)
            if (!chol_solve(S, CP, X)) return;                      // ill-conditioned
            K = transpose(X);                                       // [n x p]

            const Mat Pf = sub(Pp, matmul(K, CP));                  // Pp - K*C*Pp
            Mat Pnext = add(matmul(matmul(M_.A, Pf), transpose(M_.A)), Q);
            Pnext = symmetrize(Pnext);
            if (!all_finite(Pnext)) return;

            const double delta = fro_norm(sub(Pnext, Pp)) / std::max(1.0, fro_norm(Pp));
            Pp = Pnext;
            ok = true;
            if (delta < 1e-12) break;
        }
        if (!ok) return;

        // Accept only a demonstrably stable estimator: e_{k+1} = (I - L*C)*A*e
        const Mat ILC = sub(Mat::identity(n_), matmul(K, M_.C));
        observer_pole_ = spectral_radius(matmul(ILC, M_.A), 400);
        if (!(observer_pole_ < 1.0)) return;                        // leaves L_ zero

        L_ = K;
        observer_active_ = true;
    }

    LtiModel M_;
    MpcConfig cfg_;
    int out_count_;
    int n_ = 0, m_ = 0, p_ = 0;

    Mat F_, S_, GS_, GStQbar_;
    Mat L_;
    bool observer_active_ = false;
    double observer_pole_ = 0.0;

    BoxQpSolver qp_;
    Vec xhat_, u_last_, target_stack_, z_;
    std::vector<int> feature_map_;
    bool feature_fault_ = false;

    int last_iters_ = 0;
    bool last_converged_ = true;
    long long qp_failures_ = 0;
};

}  // namespace ctl
