// linalg.hpp -- minimal dense linear algebra for the real-time controller.
//
// WHY THIS EXISTS RATHER THAN EIGEN
// This is the backup control path. Its entire value is that it builds and runs
// when the primary (MATLAB) path is unavailable, so it deliberately has zero
// external dependencies: no Eigen, no BLAS, no CMake. Every matrix here is small
// -- state dimension <= ~12, horizon <= 20, 16 inputs -- so a straightforward
// dense implementation is both fast enough and far more predictable than a
// general-purpose library inside a 10 ms tick.
//
// Everything allocates on construction and never inside the control loop's hot
// path, provided the caller preallocates its workspace (which MpcController does).
#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace ctl {

struct Mat {
    int rows = 0;
    int cols = 0;
    std::vector<double> a;   // row-major

    Mat() = default;
    Mat(int r, int c, double fill = 0.0) : rows(r), cols(c), a((size_t)r * c, fill) {}

    double& operator()(int i, int j)             { return a[(size_t)i * cols + j]; }
    double  operator()(int i, int j) const       { return a[(size_t)i * cols + j]; }

    int size() const { return rows * cols; }
    bool empty() const { return rows == 0 || cols == 0; }

    static Mat identity(int n) {
        Mat m(n, n, 0.0);
        for (int i = 0; i < n; ++i) m(i, i) = 1.0;
        return m;
    }
};

using Vec = std::vector<double>;

// --------------------------------------------------------------------------
// basic products
// --------------------------------------------------------------------------
inline Mat matmul(const Mat& A, const Mat& B) {
    if (A.cols != B.rows)
        throw std::runtime_error("matmul: dimension mismatch " +
                                 std::to_string(A.rows) + "x" + std::to_string(A.cols) + " * " +
                                 std::to_string(B.rows) + "x" + std::to_string(B.cols));
    Mat C(A.rows, B.cols, 0.0);
    for (int i = 0; i < A.rows; ++i) {
        for (int k = 0; k < A.cols; ++k) {
            const double aik = A(i, k);
            if (aik == 0.0) continue;
            const double* brow = &B.a[(size_t)k * B.cols];
            double* crow = &C.a[(size_t)i * C.cols];
            for (int j = 0; j < B.cols; ++j) crow[j] += aik * brow[j];
        }
    }
    return C;
}

inline Vec matvec(const Mat& A, const Vec& x) {
    if ((int)x.size() != A.cols)
        throw std::runtime_error("matvec: dimension mismatch");
    Vec y((size_t)A.rows, 0.0);
    for (int i = 0; i < A.rows; ++i) {
        const double* row = &A.a[(size_t)i * A.cols];
        double s = 0.0;
        for (int j = 0; j < A.cols; ++j) s += row[j] * x[(size_t)j];
        y[(size_t)i] = s;
    }
    return y;
}

inline Mat transpose(const Mat& A) {
    Mat T(A.cols, A.rows);
    for (int i = 0; i < A.rows; ++i)
        for (int j = 0; j < A.cols; ++j) T(j, i) = A(i, j);
    return T;
}

inline Mat add(const Mat& A, const Mat& B) {
    Mat C(A.rows, A.cols);
    for (int i = 0; i < A.size(); ++i) C.a[i] = A.a[i] + B.a[i];
    return C;
}

inline Mat sub(const Mat& A, const Mat& B) {
    Mat C(A.rows, A.cols);
    for (int i = 0; i < A.size(); ++i) C.a[i] = A.a[i] - B.a[i];
    return C;
}

inline Mat scale(const Mat& A, double s) {
    Mat C = A;
    for (auto& v : C.a) v *= s;
    return C;
}

inline Mat symmetrize(const Mat& A) {
    Mat C(A.rows, A.cols);
    for (int i = 0; i < A.rows; ++i)
        for (int j = 0; j < A.cols; ++j) C(i, j) = 0.5 * (A(i, j) + A(j, i));
    return C;
}

inline double fro_norm(const Mat& A) {
    double s = 0.0;
    for (double v : A.a) s += v * v;
    return std::sqrt(s);
}

inline bool all_finite(const Mat& A) {
    for (double v : A.a) if (!std::isfinite(v)) return false;
    return true;
}

// --------------------------------------------------------------------------
// Cholesky solve for symmetric positive definite systems: solve A X = B.
// Used for the Kalman innovation covariance. Returns false if A is not
// numerically SPD, which the caller treats as "this gain is not trustworthy"
// rather than pushing on with a garbage result.
// --------------------------------------------------------------------------
inline bool chol_factor(const Mat& A, Mat& Lo) {
    const int n = A.rows;
    Lo = Mat(n, n, 0.0);
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j <= i; ++j) {
            double s = A(i, j);
            for (int k = 0; k < j; ++k) s -= Lo(i, k) * Lo(j, k);
            if (i == j) {
                if (!(s > 1e-300) || !std::isfinite(s)) return false;
                Lo(i, j) = std::sqrt(s);
            } else {
                Lo(i, j) = s / Lo(j, j);
            }
        }
    }
    return true;
}

inline bool chol_solve(const Mat& A, const Mat& B, Mat& X) {
    Mat Lo;
    if (!chol_factor(A, Lo)) return false;
    const int n = A.rows, m = B.cols;
    X = Mat(n, m, 0.0);
    Mat Y(n, m, 0.0);
    for (int c = 0; c < m; ++c) {                    // forward substitution
        for (int i = 0; i < n; ++i) {
            double s = B(i, c);
            for (int k = 0; k < i; ++k) s -= Lo(i, k) * Y(k, c);
            Y(i, c) = s / Lo(i, i);
        }
        for (int i = n - 1; i >= 0; --i) {           // back substitution
            double s = Y(i, c);
            for (int k = i + 1; k < n; ++k) s -= Lo(k, i) * X(k, c);
            X(i, c) = s / Lo(i, i);
        }
    }
    return all_finite(X);
}

// --------------------------------------------------------------------------
// Spectral radius by power iteration.
//
// Used for two things: the observer stability check (|eig((I-LC)A)| < 1) and the
// QP's Lipschitz constant. Power iteration finds the DOMINANT magnitude, which is
// exactly what both callers want, and needs no eigen-decomposition.
//
// Caveat worth knowing: for a matrix whose dominant eigenvalues are a complex
// conjugate pair, plain power iteration on a single vector can oscillate rather
// than converge. We therefore track the running maximum Rayleigh-style estimate
// over iterations and return that, which upper-bounds correctly for the uses here
// (a conservative Lipschitz constant is safe; a conservative stability estimate
// errs toward declaring instability, which is the safe direction).
// --------------------------------------------------------------------------
inline double spectral_radius(const Mat& A, int iters = 500) {
    const int n = A.rows;
    if (n == 0) return 0.0;
    Vec v((size_t)n, 0.0);
    for (int i = 0; i < n; ++i) v[(size_t)i] = 1.0 / std::sqrt((double)n);
    double best = 0.0;
    for (int it = 0; it < iters; ++it) {
        Vec w = matvec(A, v);
        double nw = 0.0;
        for (double x : w) nw += x * x;
        nw = std::sqrt(nw);
        if (!std::isfinite(nw)) return std::numeric_limits<double>::infinity();
        if (nw < 1e-300) return 0.0;
        best = std::max(best, nw);
        for (int i = 0; i < n; ++i) v[(size_t)i] = w[(size_t)i] / nw;
    }
    return best;
}

// --------------------------------------------------------------------------
// helpers shared by the controllers
// --------------------------------------------------------------------------
inline void sanitize(Vec& x, double limit) {
    for (auto& v : x) {
        if (!std::isfinite(v)) v = 0.0;
        v = std::min(std::max(v, -limit), limit);
    }
}

inline Mat kron_identity(int n, const Mat& M) {
    // kron(I_n, M)
    Mat K(n * M.rows, n * M.cols, 0.0);
    for (int b = 0; b < n; ++b)
        for (int i = 0; i < M.rows; ++i)
            for (int j = 0; j < M.cols; ++j)
                K(b * M.rows + i, b * M.cols + j) = M(i, j);
    return K;
}

}  // namespace ctl
