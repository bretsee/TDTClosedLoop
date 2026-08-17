// nn_controller.hpp -- neural-network control policy, evaluated natively.
//
// WHY NOT LIBTORCH
// This runs inside a 10 ms tick that must not miss. LibTorch is a ~2 GB
// dependency whose allocator and dispatcher introduce latency variance that is
// hard to bound, and it would defeat the point of a backup path that has to
// build from nothing. The networks that fit this problem are small -- a
// 16-64-64-16 MLP is ~5k parameters, microseconds as a plain matmul -- so the
// forward pass is implemented directly and the training side (PyTorch, GPU, all
// the usual tooling) exports weights via training/export_nnw.py.
//
// The arithmetic here is verified against PyTorch by training/verify_export.py,
// which runs the same input through both and compares. Do not modify a forward
// pass here without re-running it.
//
// SUPPORTED ARCHITECTURES
//   linear         one affine layer -- the ridge/least-squares baseline
//   mlp            stacked affine + activation
//   residual_mlp   as mlp with skip connections (the winner of the acute
//                  architecture search)
//   gru            recurrent, for genuinely temporal policies
//   any of the above with history > 1, which stacks the last K feature vectors
//   into the input -- a dependency-free way to give a feedforward net temporal
//   context, and how the TCN-style models are deployed.
//
// SAFETY
// A network can emit anything. Three guards are applied after every forward
// pass, in this order: clamp to the physical amplitude bounds, optional slew
// limit, and a non-finite check that falls back to the previous command. The
// slew limit matters most -- an untrained or mis-normalised network will
// otherwise step the stimulation amplitude across its full range in one tick.
#pragma once

#include <algorithm>
#include <cmath>
#include <sstream>
#include <string>
#include <vector>

#include "controller.hpp"
#include "linalg.hpp"
#include "model_io.hpp"

namespace ctl {

struct NnConfig {
    double umin = 0.0;
    double umax = 40.0;
    double max_rate = 0.0;   // max |change| per tick; 0 disables the slew limit
};

class NnController : public IController {
public:
    NnController(const NnModel& model, const NnConfig& cfg, int output_count)
        : M_(model), cfg_(cfg), out_count_(output_count) {
        hist_.assign((size_t)(M_.input * M_.history), 0.0);
        u_last_.assign((size_t)M_.output, 0.0);

        // Recurrent hidden state, one buffer per GRU layer.
        for (const Layer& L : M_.layers)
            h_.push_back(L.kind == LayerKind::Gru ? Vec((size_t)L.out, 0.0) : Vec());

        // Scratch buffers sized to the widest layer, so the tick allocates nothing.
        int widest = M_.net_input_dim();
        for (const Layer& L : M_.layers) widest = std::max(widest, L.out * 3);
        scratch_a_.resize((size_t)widest);
        scratch_b_.resize((size_t)widest);
    }

    std::string name() const override { return "nn:" + M_.arch; }

    void reset() override {
        std::fill(hist_.begin(), hist_.end(), 0.0);
        std::fill(u_last_.begin(), u_last_.end(), 0.0);
        for (Vec& h : h_) std::fill(h.begin(), h.end(), 0.0);
        primed_ = false;
        ticks_ = 0;
    }

    std::vector<double> step(const std::vector<double>& features) override {
        ++ticks_;

        // ---- normalise this timestep's features --------------------------
        Vec x((size_t)M_.input, 0.0);
        for (int i = 0; i < M_.input; ++i) {
            const double raw = (i < (int)features.size()) ? features[(size_t)i] : 0.0;
            const double v = (raw - M_.in_mean[(size_t)i]) / M_.in_std[(size_t)i];
            x[(size_t)i] = std::isfinite(v) ? v : 0.0;
        }

        // ---- shift into the history window --------------------------------
        // Oldest first, newest last: [t-K+1 ... t]. On the very first tick the
        // window is filled with the current sample rather than zeros, so the
        // network does not see a fabricated step edge before it has context.
        if (M_.history > 1) {
            if (!primed_) {
                for (int k = 0; k < M_.history; ++k)
                    std::copy(x.begin(), x.end(), hist_.begin() + (size_t)k * M_.input);
                primed_ = true;
            } else {
                std::move(hist_.begin() + M_.input, hist_.end(), hist_.begin());
                std::copy(x.begin(), x.end(), hist_.end() - M_.input);
            }
        } else {
            hist_ = x;
        }

        // ---- forward pass --------------------------------------------------
        Vec cur = hist_;
        for (size_t li = 0; li < M_.layers.size(); ++li) {
            const Layer& L = M_.layers[li];
            switch (L.kind) {
                case LayerKind::Linear:   cur = forward_affine(L, cur, false); break;
                case LayerKind::Residual: cur = forward_affine(L, cur, true);  break;
                case LayerKind::Gru:      cur = forward_gru(L, cur, h_[li]);   break;
            }
        }

        // ---- de-normalise and guard ----------------------------------------
        Vec u((size_t)M_.output, 0.0);
        bool finite = true;
        for (int i = 0; i < M_.output; ++i) {
            double v = cur[(size_t)i] * M_.out_std[(size_t)i] + M_.out_mean[(size_t)i];
            if (!std::isfinite(v)) { finite = false; break; }
            u[(size_t)i] = v;
        }

        if (!finite) {
            // A non-finite forward pass means the network or its normalisation is
            // broken. Holding the previous command is the only safe response, and
            // it is counted so the operator sees it rather than it passing silently.
            ++nonfinite_;
            u = u_last_;
        }

        for (int i = 0; i < M_.output; ++i) {
            double v = std::min(std::max(u[(size_t)i], cfg_.umin), cfg_.umax);
            if (cfg_.max_rate > 0.0) {
                const double prev = u_last_[(size_t)i];
                const double d = v - prev;
                if (d >  cfg_.max_rate) { v = prev + cfg_.max_rate; ++slew_limited_; }
                if (d < -cfg_.max_rate) { v = prev - cfg_.max_rate; ++slew_limited_; }
            }
            u[(size_t)i] = v;
        }
        u_last_ = u;

        Vec out((size_t)out_count_, 0.0);
        for (int i = 0; i < out_count_ && i < M_.output; ++i) out[(size_t)i] = u[(size_t)i];
        return out;
    }

    std::string status() const override {
        std::ostringstream os;
        os << "arch=" << M_.arch << " hist=" << M_.history
           << " nonFinite=" << nonfinite_ << " slewLimited=" << slew_limited_;
        return os.str();
    }

private:
    static double act_apply(Act a, double v) {
        switch (a) {
            case Act::Relu: return v > 0.0 ? v : 0.0;
            case Act::Tanh: return std::tanh(v);
            default:        return v;
        }
    }

    Vec forward_affine(const Layer& L, const Vec& in, bool residual) const {
        Vec out((size_t)L.out, 0.0);
        for (int i = 0; i < L.out; ++i) {
            const double* w = &L.W.a[(size_t)i * L.in];
            double s = L.b[(size_t)i];
            for (int j = 0; j < L.in; ++j) s += w[j] * in[(size_t)j];
            s = act_apply(L.act, s);
            if (residual) s += in[(size_t)i];
            out[(size_t)i] = s;
        }
        return out;
    }

    // PyTorch GRUCell semantics, gates ordered r, z, n in the stacked weights:
    //   r = sig(W_ir x + b_ir + W_hr h + b_hr)
    //   z = sig(W_iz x + b_iz + W_hz h + b_hz)
    //   n = tanh(W_in x + b_in + r * (W_hn h + b_hn))
    //   h'= (1 - z) * n + z * h
    // Note r multiplies the HIDDEN term only, after its bias -- a common place
    // to get this subtly wrong, and why verify_export.py exists.
    Vec forward_gru(const Layer& L, const Vec& x, Vec& h) const {
        const int H = L.out;
        Vec gi((size_t)(3 * H), 0.0), gh((size_t)(3 * H), 0.0);

        for (int i = 0; i < 3 * H; ++i) {
            const double* w = &L.W_ih.a[(size_t)i * L.in];
            double s = L.b_ih[(size_t)i];
            for (int j = 0; j < L.in; ++j) s += w[j] * x[(size_t)j];
            gi[(size_t)i] = s;
        }
        for (int i = 0; i < 3 * H; ++i) {
            const double* w = &L.W_hh.a[(size_t)i * H];
            double s = L.b_hh[(size_t)i];
            for (int j = 0; j < H; ++j) s += w[j] * h[(size_t)j];
            gh[(size_t)i] = s;
        }

        Vec h_new((size_t)H, 0.0);
        for (int i = 0; i < H; ++i) {
            const double r = sigmoid(gi[(size_t)i]           + gh[(size_t)i]);
            const double z = sigmoid(gi[(size_t)(H + i)]     + gh[(size_t)(H + i)]);
            const double n = std::tanh(gi[(size_t)(2 * H + i)] + r * gh[(size_t)(2 * H + i)]);
            h_new[(size_t)i] = (1.0 - z) * n + z * h[(size_t)i];
        }
        h = h_new;
        return h_new;
    }

    static double sigmoid(double v) { return 1.0 / (1.0 + std::exp(-v)); }

    NnModel M_;
    NnConfig cfg_;
    int out_count_;

    Vec hist_, u_last_;
    std::vector<Vec> h_;
    Vec scratch_a_, scratch_b_;
    bool primed_ = false;
    long long ticks_ = 0, nonfinite_ = 0, slew_limited_ = 0;
};

}  // namespace ctl
