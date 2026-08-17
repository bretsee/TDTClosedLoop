// excitation.hpp -- open-loop system-ID excitation, ported from make_excitation.m.
//
// Present so the backup path can also collect the identification data, not only
// run a controller. Sequences are generated in full BEFORE the first packet, so
// no allocation or RNG work happens inside a control tick and the exact commanded
// sequence is known before any current is delivered.
//
// The PRBS is the same 9-bit maximal LFSR (x^9 + x^5 + 1, period 511) as the
// MATLAB version, with the same per-channel shift, so captures from the two
// servers are directly comparable.
#pragma once

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

namespace ctl {

struct ExcitationConfig {
    std::string kind = "prbs";      // prbs | multilevel | steps | chirp
    int    clock_ticks = 5;         // ticks each PRBS/multilevel value is held
    int    hold_ticks = 50;         // ticks per step for 'steps'
    int    levels = 4;
    double umin = 0.0;
    double umax = 30.0;
    unsigned seed = 12345;
    double f0 = 0.2, f1 = 20.0;     // chirp sweep, Hz
    std::vector<int> active;        // 1-based channels allowed to move; empty = all
};

class Excitation {
public:
    Excitation(const ExcitationConfig& cfg, int ticks, int channels)
        : cfg_(cfg), ticks_(ticks), ch_(channels) {
        U_.assign((size_t)ticks * channels, cfg.umin);
        if      (cfg.kind == "prbs")       build_prbs();
        else if (cfg.kind == "multilevel") build_multilevel();
        else if (cfg.kind == "steps")      build_steps();
        else if (cfg.kind == "chirp")      build_chirp();
        else throw std::runtime_error("unknown excitation kind: " + cfg.kind);

        for (double& v : U_) v = std::min(std::max(v, cfg.umin), cfg.umax);
        apply_active_mask();
    }

    // Indexed by packet count, not sequence number, so a dropped request does
    // not skip a slice of the designed sequence (matching the MATLAB server).
    std::vector<double> at(int packet_index) const {
        const int i = std::min(std::max(packet_index, 0), ticks_ - 1);
        return std::vector<double>(U_.begin() + (size_t)i * ch_,
                                   U_.begin() + (size_t)(i + 1) * ch_);
    }

    void range(double& lo, double& hi) const {
        lo = hi = U_.empty() ? 0.0 : U_[0];
        for (double v : U_) { lo = std::min(lo, v); hi = std::max(hi, v); }
    }

    const std::vector<int>& active_channels() const { return active_; }

private:
    double& at(int t, int c) { return U_[(size_t)t * ch_ + c]; }

    void apply_active_mask() {
        active_.clear();
        if (cfg_.active.empty()) {
            for (int c = 1; c <= ch_; ++c) active_.push_back(c);
            return;
        }
        std::vector<bool> keep((size_t)ch_, false);
        for (int c : cfg_.active) {
            if (c < 1 || c > ch_)
                throw std::runtime_error("activeChannels entry out of range: " + std::to_string(c));
            keep[(size_t)(c - 1)] = true;
        }
        for (int c = 0; c < ch_; ++c) {
            if (keep[(size_t)c]) active_.push_back(c + 1);
            else for (int t = 0; t < ticks_; ++t) at(t, c) = cfg_.umin;
        }
    }

    static std::vector<char> lfsr(int nbits, int len) {
        std::vector<char> reg((size_t)nbits, 1), bits((size_t)len, 0);
        const int taps[2] = {9, 5};
        for (int i = 0; i < len; ++i) {
            bits[(size_t)i] = reg[(size_t)(nbits - 1)];
            int fb = 0;
            for (int t : taps) fb ^= reg[(size_t)(t - 1)];
            for (int k = nbits - 1; k > 0; --k) reg[(size_t)k] = reg[(size_t)(k - 1)];
            reg[0] = (char)fb;
        }
        return bits;
    }

    void build_prbs() {
        const int nbits = 9, len = (1 << nbits) - 1;
        const std::vector<char> bits = lfsr(nbits, len);
        for (int c = 0; c < ch_; ++c) {
            const int shift = (ch_ > 1) ? (int)std::lround((double)c * len / ch_) : 0;
            for (int t = 0; t < ticks_; ++t) {
                const int idx = ((t / cfg_.clock_ticks) + shift) % len;
                at(t, c) = bits[(size_t)idx] ? cfg_.umax : cfg_.umin;
            }
        }
    }

    void build_multilevel() {
        const int nl = std::max(2, cfg_.levels);
        std::vector<double> lv((size_t)nl);
        for (int i = 0; i < nl; ++i)
            lv[(size_t)i] = cfg_.umin + (cfg_.umax - cfg_.umin) * i / (nl - 1);

        unsigned rs = cfg_.seed ? cfg_.seed : 12345u;
        auto rnd = [&rs]() {
            rs = (unsigned)((16807ULL * rs) % 2147483647ULL);
            return (double)(rs - 1) / 2147483646.0;
        };
        for (int c = 0; c < ch_; ++c) {
            double prev = -1e30;
            const int holds = (ticks_ + cfg_.clock_ticks - 1) / cfg_.clock_ticks;
            std::vector<double> vals((size_t)holds);
            for (int h = 0; h < holds; ++h) {
                double pick = prev;
                for (int guard = 0; guard < 20 && pick == prev; ++guard)
                    pick = lv[(size_t)std::min(nl - 1, (int)(rnd() * nl))];
                vals[(size_t)h] = pick;
                prev = pick;
            }
            for (int t = 0; t < ticks_; ++t) at(t, c) = vals[(size_t)(t / cfg_.clock_ticks)];
        }
    }

    void build_steps() {
        const int nl = std::max(2, cfg_.levels);
        std::vector<double> ladder;
        for (int i = 0; i < nl; ++i)
            ladder.push_back(cfg_.umin + (cfg_.umax - cfg_.umin) * i / (nl - 1));
        for (int i = nl - 2; i >= 1; --i) ladder.push_back(ladder[(size_t)i]);

        for (int c = 0; c < ch_; ++c) {
            const int offset = (ch_ > 1) ? (int)std::lround((double)c * cfg_.hold_ticks / ch_) : 0;
            for (int t = 0; t < ticks_; ++t) {
                const int idx = ((t + offset) / cfg_.hold_ticks) % (int)ladder.size();
                at(t, c) = ladder[(size_t)idx];
            }
        }
    }

    void build_chirp() {
        const double Ts = 0.01;
        const double T = std::max(Ts, (ticks_ - 1) * Ts);
        const double mid = 0.5 * (cfg_.umin + cfg_.umax);
        const double amp = 0.5 * (cfg_.umax - cfg_.umin);
        for (int c = 0; c < ch_; ++c) {
            const double phase = (ch_ > 1) ? 2.0 * 3.14159265358979 * c / ch_ : 0.0;
            for (int t = 0; t < ticks_; ++t) {
                const double tt = t * Ts;
                const double inst = cfg_.f0 * tt + (cfg_.f1 - cfg_.f0) * tt * tt / (2.0 * T);
                at(t, c) = mid + amp * std::sin(2.0 * 3.14159265358979 * inst + phase);
            }
        }
    }

    ExcitationConfig cfg_;
    int ticks_, ch_;
    std::vector<double> U_;
    std::vector<int> active_;
};

}  // namespace ctl
