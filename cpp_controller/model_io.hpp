// model_io.hpp -- loaders for the two model file formats this controller consumes.
//
// Both formats are PLAIN TEXT, whitespace-tokenised. That is a deliberate choice
// for a backup system: the files are greppable, diffable, hand-editable at the
// rig, and need no serialisation library. The models are small (a 16-64-64-16
// network is ~5k parameters) so parse cost is milliseconds, once, at startup.
//
//   .lti  -- discrete-time state-space plant, written by export_plant_lti.m from
//            the same AllModels(10).sys the MATLAB controller uses
//   .nnw  -- neural network weights, written by training/export_nnw.py
//
// Both loaders fail loudly with a specific message. A backup control path that
// silently loads a partially-parsed model would be worse than one that refuses
// to start -- that failure mode is exactly the observer-gain defect that made the
// MATLAB controller run open-loop for months.
#pragma once

#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "linalg.hpp"

namespace ctl {

// --------------------------------------------------------------------------
// tokeniser
// --------------------------------------------------------------------------
class Tokens {
public:
    explicit Tokens(const std::string& path) {
        std::ifstream f(path);
        if (!f) throw std::runtime_error("cannot open model file: " + path);
        std::string tok;
        while (f >> tok) {
            if (!tok.empty() && tok[0] == '#') {   // comment to end of line
                std::string rest;
                std::getline(f, rest);
                continue;
            }
            t_.push_back(tok);
        }
        path_ = path;
    }

    bool done() const { return i_ >= t_.size(); }

    std::string next() {
        if (done()) throw std::runtime_error("unexpected end of " + path_);
        return t_[i_++];
    }

    void expect(const std::string& want) {
        const std::string got = next();
        if (got != want)
            throw std::runtime_error(path_ + ": expected '" + want + "' but found '" + got + "'");
    }

    double num() {
        const std::string s = next();
        try {
            return std::stod(s);
        } catch (...) {
            throw std::runtime_error(path_ + ": expected a number, found '" + s + "'");
        }
    }

    int integer() { return (int)num(); }

    std::string peek() const { return done() ? std::string() : t_[i_]; }

    Mat matrix(int r, int c) {
        Mat m(r, c);
        for (int i = 0; i < r; ++i)
            for (int j = 0; j < c; ++j) m(i, j) = num();
        return m;
    }

    Vec vector(int n) {
        Vec v((size_t)n);
        for (int i = 0; i < n; ++i) v[(size_t)i] = num();
        return v;
    }

private:
    std::vector<std::string> t_;
    size_t i_ = 0;
    std::string path_;
};

// --------------------------------------------------------------------------
// .lti -- discrete state-space plant
// --------------------------------------------------------------------------
struct LtiModel {
    Mat A, B, C, D;
    double Ts = 0.01;
    int n = 0, m = 0, p = 0;
    // Operating-point offsets (export_plant_lti.m trailing blocks, optional for
    // old files). The model is fitted on CENTERED data: y = yOff + C x + D (u -
    // uOff). A controller that ignores these on an offset model regulates the
    // wrong plant -- the 2026-08-20 hazard, closed 2026-09-01.
    Vec uOff, yOff;   // sized m / p; zeros when the file carries no offsets
    bool has_offsets = false;
};

inline LtiModel load_lti(const std::string& path) {
    Tokens t(path);
    t.expect("LTI");
    const int version = t.integer();
    if (version != 1) throw std::runtime_error(path + ": unsupported LTI version");

    LtiModel M;
    t.expect("Ts"); M.Ts = t.num();
    t.expect("n");  M.n  = t.integer();
    t.expect("m");  M.m  = t.integer();
    t.expect("p");  M.p  = t.integer();
    if (M.n <= 0 || M.m <= 0 || M.p <= 0)
        throw std::runtime_error(path + ": degenerate model dimensions");

    t.expect("A"); M.A = t.matrix(M.n, M.n);
    t.expect("B"); M.B = t.matrix(M.n, M.m);
    t.expect("C"); M.C = t.matrix(M.p, M.n);
    t.expect("D"); M.D = t.matrix(M.p, M.m);

    if (!all_finite(M.A) || !all_finite(M.B) || !all_finite(M.C) || !all_finite(M.D))
        throw std::runtime_error(path + ": model contains non-finite entries");

    // Optional trailing offset blocks (either order; both or neither expected in
    // practice -- export_plant_lti.m writes uOffset then yOffset).
    M.uOff.assign((size_t)M.m, 0.0);
    M.yOff.assign((size_t)M.p, 0.0);
    while (!t.done()) {
        const std::string key = t.next();
        if (key == "uOffset")      { M.uOff = t.vector(M.m); M.has_offsets = true; }
        else if (key == "yOffset") { M.yOff = t.vector(M.p); M.has_offsets = true; }
        else throw std::runtime_error(path + ": unrecognised trailing block '" + key + "'");
    }
    for (double v : M.uOff) if (!std::isfinite(v))
        throw std::runtime_error(path + ": non-finite uOffset");
    for (double v : M.yOff) if (!std::isfinite(v))
        throw std::runtime_error(path + ": non-finite yOffset");
    return M;
}

// --------------------------------------------------------------------------
// .nnw -- neural network weights
// --------------------------------------------------------------------------
enum class Act { None, Relu, Tanh };

inline Act parse_act(const std::string& s) {
    if (s == "none") return Act::None;
    if (s == "relu") return Act::Relu;
    if (s == "tanh") return Act::Tanh;
    throw std::runtime_error("unknown activation: " + s);
}

enum class LayerKind { Linear, Residual, Gru };

struct Layer {
    LayerKind kind = LayerKind::Linear;
    int in = 0, out = 0;
    Act act = Act::None;

    Mat W;      // linear/residual: [out x in]
    Vec b;      // linear/residual: [out]

    // GRU (PyTorch GRUCell layout: gates ordered r, z, n)
    Mat W_ih;   // [3*hidden x in]
    Mat W_hh;   // [3*hidden x hidden]
    Vec b_ih;   // [3*hidden]
    Vec b_hh;   // [3*hidden]
};

struct NnModel {
    std::string arch = "mlp";
    int input = 0;          // features per timestep
    int output = 0;
    int history = 1;        // timesteps stacked into the network input
    bool recurrent = false;

    Vec in_mean, in_std;    // per-timestep-feature normalisation
    Vec out_mean, out_std;  // output de-normalisation
    double out_min = 0.0, out_max = 40.0;

    std::vector<Layer> layers;

    int net_input_dim() const { return input * history; }
};

inline NnModel load_nnw(const std::string& path) {
    Tokens t(path);
    t.expect("NNW");
    const int version = t.integer();
    if (version != 1) throw std::runtime_error(path + ": unsupported NNW version");

    NnModel M;
    t.expect("arch");    M.arch    = t.next();
    t.expect("input");   M.input   = t.integer();
    t.expect("output");  M.output  = t.integer();
    t.expect("history"); M.history = t.integer();
    if (M.input <= 0 || M.output <= 0 || M.history <= 0)
        throw std::runtime_error(path + ": degenerate network dimensions");

    t.expect("in_mean");   M.in_mean   = t.vector(M.input);
    t.expect("in_std");    M.in_std    = t.vector(M.input);
    t.expect("out_mean");  M.out_mean  = t.vector(M.output);
    t.expect("out_std");   M.out_std   = t.vector(M.output);
    t.expect("out_min");   M.out_min   = t.num();
    t.expect("out_max");   M.out_max   = t.num();

    // A zero std would divide by zero on the first tick and emit NaN commands.
    for (double& s : M.in_std)  if (!(std::fabs(s) > 1e-12)) s = 1.0;
    for (double& s : M.out_std) if (!(std::fabs(s) > 1e-12)) s = 1.0;

    t.expect("layers");
    const int nlayers = t.integer();
    if (nlayers <= 0 || nlayers > 64)
        throw std::runtime_error(path + ": implausible layer count");

    for (int i = 0; i < nlayers; ++i) {
        t.expect("layer");
        const std::string kind = t.next();
        Layer L;
        if (kind == "linear" || kind == "residual") {
            L.kind = (kind == "residual") ? LayerKind::Residual : LayerKind::Linear;
            L.in  = t.integer();
            L.out = t.integer();
            L.act = parse_act(t.next());
            if (L.kind == LayerKind::Residual && L.in != L.out)
                throw std::runtime_error(path + ": residual layer needs in == out");
            t.expect("W"); L.W = t.matrix(L.out, L.in);
            t.expect("b"); L.b = t.vector(L.out);
        } else if (kind == "gru") {
            L.kind = LayerKind::Gru;
            L.in  = t.integer();
            L.out = t.integer();          // hidden size
            M.recurrent = true;
            t.expect("W_ih"); L.W_ih = t.matrix(3 * L.out, L.in);
            t.expect("W_hh"); L.W_hh = t.matrix(3 * L.out, L.out);
            t.expect("b_ih"); L.b_ih = t.vector(3 * L.out);
            t.expect("b_hh"); L.b_hh = t.vector(3 * L.out);
        } else {
            throw std::runtime_error(path + ": unknown layer kind '" + kind + "'");
        }
        M.layers.push_back(std::move(L));
    }

    // Dimensional consistency: catch a mismatched export at load time rather
    // than as a garbage command on the first control tick.
    int dim = M.net_input_dim();
    for (size_t i = 0; i < M.layers.size(); ++i) {
        const Layer& L = M.layers[i];
        if (L.in != dim)
            throw std::runtime_error(path + ": layer " + std::to_string(i) +
                                     " expects input " + std::to_string(L.in) +
                                     " but receives " + std::to_string(dim));
        dim = L.out;
    }
    if (dim != M.output)
        throw std::runtime_error(path + ": final layer emits " + std::to_string(dim) +
                                 " values but output is declared " + std::to_string(M.output));
    return M;
}

}  // namespace ctl
