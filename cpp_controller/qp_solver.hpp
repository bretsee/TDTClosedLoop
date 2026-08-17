// qp_solver.hpp -- box-constrained convex QP by accelerated projected gradient.
//
//      minimize   1/2 z' H z + q' z        subject to   lb <= z <= ub
//
// WHY NOT OSQP
// The MATLAB controller uses OSQP. Vendoring OSQP here would mean a second build
// system and a dependency the backup path is specifically meant to avoid. More
// importantly, THIS problem is easier than the general QP OSQP solves: the only
// constraints are simple bounds, so projection onto the feasible set is a clamp
// and an accelerated projected-gradient (FISTA) method applies directly with no
// KKT factorisation, no ADMM parameters, and no ill-conditioning failure modes.
//
// The problem is also tiny -- z has m*Nu entries, i.e. 32 for 16 inputs and a
// control horizon of 2 -- and MPC warm-starts naturally from the previous
// solution, so convergence is typically a handful of iterations.
//
// REAL-TIME PROPERTIES, which matter more here than raw speed:
//   * bounded work: max_iters is a hard cap, so the worst case is known ahead of
//     time rather than data-dependent as an active-set method's would be
//   * no allocation after construction
//   * every iterate is FEASIBLE, because it is produced by a clamp. So even if
//     the iteration is stopped early by the cap, the returned command still
//     respects the stimulation amplitude bounds. That is the property that makes
//     early termination safe on hardware.
#pragma once

#include <algorithm>
#include <cmath>
#include <vector>

#include "linalg.hpp"

namespace ctl {

struct QpResult {
    bool   converged = false;
    int    iters     = 0;
    double step_inf  = 0.0;   // final ||z_{k+1} - z_k||_inf
};

class BoxQpSolver {
public:
    BoxQpSolver() = default;

    // H must be symmetric positive semidefinite. lb/ub are per-variable bounds.
    void setup(const Mat& H, const Vec& lb, const Vec& ub,
               int max_iters = 200, double tol = 1e-7) {
        H_ = H;
        lb_ = lb;
        ub_ = ub;
        n_ = H.rows;
        max_iters_ = max_iters;
        tol_ = tol;

        // Lipschitz constant of the gradient = largest eigenvalue of H. Power
        // iteration returns a slight over-estimate in the worst case, which is
        // the safe direction: a larger L means a smaller step, i.e. slower but
        // still convergent. An under-estimate would diverge.
        const double lmax = spectral_radius(H_, 200);
        L_ = (std::isfinite(lmax) && lmax > 1e-12) ? lmax : 1.0;
        inv_L_ = 1.0 / L_;

        z_.assign((size_t)n_, 0.0);
        y_.assign((size_t)n_, 0.0);
        z_prev_.assign((size_t)n_, 0.0);
        grad_.assign((size_t)n_, 0.0);
        for (int i = 0; i < n_; ++i) z_[(size_t)i] = clampi(0.0, i);
    }

    int dim() const { return n_; }

    // Warm start from the caller's previous solution. MPC's successive problems
    // differ only by the linear term, so this is what keeps the iteration count
    // in single digits during steady operation.
    void warm_start(const Vec& z0) {
        if ((int)z0.size() != n_) return;
        for (int i = 0; i < n_; ++i) z_[(size_t)i] = clampi(z0[(size_t)i], i);
    }

    QpResult solve(const Vec& q, Vec& z_out) {
        QpResult res;
        y_ = z_;
        double t = 1.0;

        for (int it = 0; it < max_iters_; ++it) {
            z_prev_ = z_;

            // grad = H y + q
            for (int i = 0; i < n_; ++i) {
                const double* row = &H_.a[(size_t)i * n_];
                double s = q[(size_t)i];
                for (int j = 0; j < n_; ++j) s += row[j] * y_[(size_t)j];
                grad_[(size_t)i] = s;
            }

            // projected gradient step -- the clamp IS the projection, so z_ is
            // feasible at every iteration including an early-terminated one
            double step_inf = 0.0;
            for (int i = 0; i < n_; ++i) {
                const double zi = clampi(y_[(size_t)i] - inv_L_ * grad_[(size_t)i], i);
                step_inf = std::max(step_inf, std::fabs(zi - z_prev_[(size_t)i]));
                z_[(size_t)i] = zi;
            }

            res.iters = it + 1;
            res.step_inf = step_inf;
            if (step_inf < tol_) {
                res.converged = true;
                break;
            }

            // Nesterov extrapolation
            const double t_next = 0.5 * (1.0 + std::sqrt(1.0 + 4.0 * t * t));
            const double beta = (t - 1.0) / t_next;
            for (int i = 0; i < n_; ++i)
                y_[(size_t)i] = z_[(size_t)i] + beta * (z_[(size_t)i] - z_prev_[(size_t)i]);
            t = t_next;
        }

        z_out = z_;
        return res;
    }

    double objective(const Vec& q, const Vec& z) const {
        double quad = 0.0, lin = 0.0;
        for (int i = 0; i < n_; ++i) {
            const double* row = &H_.a[(size_t)i * n_];
            double s = 0.0;
            for (int j = 0; j < n_; ++j) s += row[j] * z[(size_t)j];
            quad += z[(size_t)i] * s;
            lin  += q[(size_t)i] * z[(size_t)i];
        }
        return 0.5 * quad + lin;
    }

private:
    double clampi(double v, int i) const {
        if (!std::isfinite(v)) v = 0.0;
        return std::min(std::max(v, lb_[(size_t)i]), ub_[(size_t)i]);
    }

    Mat H_;
    Vec lb_, ub_;
    Vec z_, y_, z_prev_, grad_;
    int n_ = 0;
    int max_iters_ = 200;
    double tol_ = 1e-7;
    double L_ = 1.0, inv_L_ = 1.0;
};

}  // namespace ctl
