// main.cpp -- native controller server for the TDT closed-loop rig.
//
// A DROP-IN REPLACEMENT for matlab_controller_server.m. It binds the same ports,
// speaks the same big-endian wire protocol, and writes the same capture CSV
// format, so MpcPo8eUdpClosedLoop.exe runs against it unchanged and unrebuilt
// with --controller localhost. That is what makes it a usable backup: the piece
// of the system that is benchmarked and trusted does not move.
//
// It exists because the primary path depends on MATLAB, which on this machine
// has no Control System Toolbox and no System Identification Toolbox, needs a
// licence, costs ~30 s to start, and imposes a Windows timer-quantum workaround
// to hit its latency target. This binary has none of those dependencies.
//
// MODES
//   constant   fixed output, for checking the transport end to end
//   openloop   designed excitation + (u,y) capture, for system identification
//   mpc        condensed-QP MPC on a .lti plant model  (port of mpc_test.m)
//   nn         neural-network policy from a .nnw weights file
//
// Build: build_cpp_controller.bat        Self-test: cpp_controller.exe --selftest

// NOMINMAX is mandatory: <windows.h>, pulled in by winsock2.h, defines min and
// max as macros, which then break every std::min / std::max in the headers below.
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

#include "controller.hpp"
#include "excitation.hpp"
#include "linalg.hpp"
#include "model_io.hpp"
#include "mpc_controller.hpp"
#include "nn_controller.hpp"
#include "wire.hpp"

#pragma comment(lib, "ws2_32.lib")

using namespace ctl;

// --------------------------------------------------------------------------
// trivial controllers
// --------------------------------------------------------------------------
class ConstantController : public IController {
public:
    ConstantController(double v, int n) : v_(v), n_(n) {}
    std::vector<double> step(const std::vector<double>&) override {
        return std::vector<double>((size_t)n_, v_);
    }
    void reset() override {}
    std::string name() const override { return "constant"; }
private:
    double v_; int n_;
};

// --------------------------------------------------------------------------
// options
// --------------------------------------------------------------------------
struct Options {
    std::string mode = "constant";
    int request_port = 31000;
    int reply_port = 31001;
    int output_count = 16;
    long long max_packets = 0;          // 0 = run until interrupted
    double constant_value = 5.0;

    std::string model_path;             // .lti for mpc, .nnw for nn
    std::string capture_file;
    std::string log_file;
    std::string play_file;              // openloop: replay a designed u CSV verbatim
    std::string reference_file;         // mpc: per-tick target trajectory CSV (r1..rp)

    double target = 0.0;
    std::string target_file;            // re-read live, mirrors MATLAB's MPC_TARGET
    std::vector<int> feature_map;
    std::vector<int> stim_pairs;        // controller output i -> wire slot pairs[i]

    MpcConfig mpc;
    NnConfig  nn;
    ExcitationConfig exc;
    bool selftest = false;
};

// Load the columns of a CSV whose header names start with `prefix` followed by
// a digit (u1..uM for designed commands, r1..rp for reference trajectories).
// This is how a MATLAB-designed, validator-audited sequence gets replayed with
// no MATLAB in the real-time path: design offline, play verbatim here.
static std::vector<std::vector<double>> load_csv_prefix(const std::string& path,
                                                        const std::string& prefix) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("cannot open " + path);
    std::string line;
    if (!std::getline(f, line)) throw std::runtime_error("empty CSV " + path);

    std::vector<int> cols;
    {
        std::string cur;
        int idx = 0;
        for (char c : line + ",") {
            if (c == ',') {
                if (!cur.empty() && cur.back() == '\r') cur.pop_back();
                if (cur.size() > prefix.size() && cur.compare(0, prefix.size(), prefix) == 0 &&
                    std::isdigit((unsigned char)cur[prefix.size()]))
                    cols.push_back(idx);
                ++idx;
                cur.clear();
            } else cur += c;
        }
    }
    if (cols.empty())
        throw std::runtime_error("no '" + prefix + "N' columns in " + path);

    std::vector<std::vector<double>> rows;
    while (std::getline(f, line)) {
        if (line.empty() || line == "\r") continue;
        std::vector<double> vals;
        std::string cur;
        for (char c : line + ",") {
            if (c == ',') { vals.push_back(std::atof(cur.c_str())); cur.clear(); }
            else cur += c;
        }
        std::vector<double> row;
        row.reserve(cols.size());
        for (int ci : cols) {
            if (ci >= (int)vals.size())
                throw std::runtime_error("short row " + std::to_string(rows.size() + 2) +
                                         " in " + path);
            row.push_back(vals[(size_t)ci]);
        }
        rows.push_back(std::move(row));
    }
    if (rows.empty()) throw std::runtime_error("no data rows in " + path);
    return rows;
}

static bool parse_int_list(const std::string& s, std::vector<int>& out) {
    out.clear();
    std::string cur;
    for (char c : s + ",") {
        if (c == ',' || c == ' ') {
            if (!cur.empty()) { out.push_back(std::atoi(cur.c_str())); cur.clear(); }
        } else cur += c;
    }
    return !out.empty();
}

static void usage() {
    std::printf(
        "cpp_controller -- native localhost controller server (backup for MATLAB)\n\n"
        "  --mode constant|openloop|mpc|nn     controller architecture\n"
        "  --request-port N (31000)  --reply-port N (31001)\n"
        "  --output-count N (16)     --max-packets N (0 = forever)\n"
        "  --constant-output V       constant mode value\n"
        "  --model PATH              .lti plant (mpc) or .nnw weights (nn)\n"
        "  --capture PATH            write (u,y) CSV, openloop mode\n"
        "  --log PATH                per-packet timing CSV\n"
        "  --play PATH               openloop: replay u1..uM columns of a designed\n"
        "                            CSV verbatim (design in MATLAB, validate with\n"
        "                            validate_impulse_design.py, play here -- no\n"
        "                            MATLAB in the real-time path). Zeros after the\n"
        "                            last row. max-packets defaults to the row count.\n"
        "  --target V                MPC setpoint\n"
        "  --target-file PATH        re-read setpoint live from a text file\n"
        "  --reference PATH          mpc: per-tick target from r1..rp columns of a\n"
        "                            reference CSV (build_touch_reference.py output).\n"
        "                            NO horizon preview -- the MATLAB server remains\n"
        "                            the primary tracking path; this is the backup.\n"
        "                            Holds the last row after the trajectory ends.\n"
        "  --feature-map 7,3         which feature indices are the model outputs (1-based)\n"
        "  --pairs 3                 map controller output k to bipolar pair slot k\n"
        "                            (1-based; word k on the wire drives pair k). A\n"
        "                            1-output model with no --pairs drives pair 1.\n"
        "  --horizon N (20)  --control-horizon N (2)\n"
        "  --q-weight V (1)  --r-weight V (1)  --q-scale V (0.01)\n"
        "  --umin V (0)      --umax V (40)     --max-rate V (0 = no slew limit)\n"
        "  --exc-kind prbs|multilevel|steps|chirp   --exc-clock N (5)\n"
        "  --exc-hold N (50) --exc-levels N (4)     --exc-seed N\n"
        "  --exc-channels 3,7        1-based active stim channels (default all)\n"
        "  --selftest                run offline checks and exit\n");
}

static bool parse_args(int argc, char** argv, Options& o) {
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        auto next = [&](const char* what) -> std::string {
            if (i + 1 >= argc) { std::printf("missing value after %s\n", what); std::exit(2); }
            return argv[++i];
        };
        if      (a == "--mode")            o.mode = next("--mode");
        else if (a == "--request-port")    o.request_port = std::atoi(next("--request-port").c_str());
        else if (a == "--reply-port")      o.reply_port = std::atoi(next("--reply-port").c_str());
        else if (a == "--output-count")    o.output_count = std::atoi(next("--output-count").c_str());
        else if (a == "--max-packets")     o.max_packets = std::atoll(next("--max-packets").c_str());
        else if (a == "--constant-output") o.constant_value = std::atof(next("--constant-output").c_str());
        else if (a == "--model")           o.model_path = next("--model");
        else if (a == "--capture")         o.capture_file = next("--capture");
        else if (a == "--log")             o.log_file = next("--log");
        else if (a == "--play")            o.play_file = next("--play");
        else if (a == "--reference")       o.reference_file = next("--reference");
        else if (a == "--target")          o.target = std::atof(next("--target").c_str());
        else if (a == "--target-file")     o.target_file = next("--target-file");
        else if (a == "--feature-map")     parse_int_list(next("--feature-map"), o.feature_map);
        else if (a == "--pairs")           parse_int_list(next("--pairs"), o.stim_pairs);
        else if (a == "--horizon")         o.mpc.N = std::atoi(next("--horizon").c_str());
        else if (a == "--control-horizon") o.mpc.Nu = std::atoi(next("--control-horizon").c_str());
        else if (a == "--q-weight")        o.mpc.q_weight = std::atof(next("--q-weight").c_str());
        else if (a == "--r-weight")        o.mpc.r_weight = std::atof(next("--r-weight").c_str());
        else if (a == "--q-scale")         o.mpc.qScale = std::atof(next("--q-scale").c_str());
        else if (a == "--umin")            { o.mpc.umin = o.nn.umin = o.exc.umin = std::atof(next("--umin").c_str()); }
        else if (a == "--umax")            { o.mpc.umax = o.nn.umax = o.exc.umax = std::atof(next("--umax").c_str()); }
        else if (a == "--max-rate")        o.nn.max_rate = std::atof(next("--max-rate").c_str());
        else if (a == "--exc-kind")        o.exc.kind = next("--exc-kind");
        else if (a == "--exc-clock")       o.exc.clock_ticks = std::atoi(next("--exc-clock").c_str());
        else if (a == "--exc-hold")        o.exc.hold_ticks = std::atoi(next("--exc-hold").c_str());
        else if (a == "--exc-levels")      o.exc.levels = std::atoi(next("--exc-levels").c_str());
        else if (a == "--exc-seed")        o.exc.seed = (unsigned)std::atoi(next("--exc-seed").c_str());
        else if (a == "--exc-channels")    parse_int_list(next("--exc-channels"), o.exc.active);
        else if (a == "--selftest")        o.selftest = true;
        else if (a == "--help" || a == "-h") { usage(); return false; }
        else { std::printf("unknown argument: %s\n\n", a.c_str()); usage(); return false; }
    }
    return true;
}

// --------------------------------------------------------------------------
// self-test -- offline verification, no socket and no hardware
//
// This is the check to run after any change here and before any rig day. It
// exercises the numerics that are easy to get silently wrong: the wire codec
// round-trip, the QP against a case with a known closed-form answer, the
// observer's refusal to accept an unstable estimator, and the MPC's ability to
// drive a known plant to a reachable setpoint.
// --------------------------------------------------------------------------
static int selftest() {
    int failures = 0;
    auto check = [&](const char* what, bool ok, const std::string& detail = "") {
        std::printf("  %-46s %s%s%s\n", what, ok ? "PASS" : "FAIL",
                    detail.empty() ? "" : "  ", detail.c_str());
        if (!ok) ++failures;
    };
    std::printf("cpp_controller self-test\n\n");

    // ---- wire codec ------------------------------------------------------
    {
        std::vector<double> vals{0.0, 1.5, -2.25, 40.0, 1e-3};
        unsigned char buf[256];
        const int n = build_response(12345, vals, buf, sizeof buf);
        Request rq;
        const bool ok = n > 0 && parse_request(buf, n, rq) && rq.seq == 12345 &&
                        rq.features.size() == vals.size();
        double maxerr = 0.0;
        if (ok) for (size_t i = 0; i < vals.size(); ++i)
            maxerr = std::max(maxerr, std::fabs(rq.features[i] - vals[i]));
        check("wire codec round-trip", ok && maxerr < 1e-6,
              "max err " + std::to_string(maxerr));
    }

    // ---- QP against a known answer ---------------------------------------
    {
        // min 1/2 z'Hz + q'z with H = I, q = [-5, 3] and bounds [0, 2]:
        // unconstrained optimum is [5, -3]; clamped it is exactly [2, 0].
        Mat H = Mat::identity(2);
        Vec lb{0.0, 0.0}, ub{2.0, 2.0}, q{-5.0, 3.0}, z;
        BoxQpSolver qp;
        qp.setup(H, lb, ub, 500, 1e-10);
        qp.solve(q, z);
        const double err = std::fabs(z[0] - 2.0) + std::fabs(z[1] - 0.0);
        check("box QP hits the clamped optimum", err < 1e-6, "err " + std::to_string(err));
    }
    {
        // Correlated H, interior solution: H=[[2,0.5],[0.5,1]], q=[-1,-1]
        // exact optimum z = H^-1 [1,1] = [0.2857142857, 0.8571428571]
        Mat H(2, 2); H(0,0)=2.0; H(0,1)=0.5; H(1,0)=0.5; H(1,1)=1.0;
        Vec lb{-10.0, -10.0}, ub{10.0, 10.0}, q{-1.0, -1.0}, z;
        BoxQpSolver qp;
        qp.setup(H, lb, ub, 2000, 1e-12);
        qp.solve(q, z);
        const double err = std::fabs(z[0] - 2.0 / 7.0) + std::fabs(z[1] - 6.0 / 7.0);
        check("box QP interior optimum (correlated H)", err < 1e-5, "err " + std::to_string(err));
    }

    // ---- Cholesky solve ---------------------------------------------------
    {
        Mat A(2, 2); A(0,0)=4.0; A(0,1)=1.0; A(1,0)=1.0; A(1,1)=3.0;
        Mat B(2, 1); B(0,0)=1.0; B(1,0)=2.0;
        Mat X;
        const bool ok = chol_solve(A, B, X);
        const Mat R = matmul(A, X);
        const double err = std::fabs(R(0,0) - 1.0) + std::fabs(R(1,0) - 2.0);
        check("Cholesky solve A X = B", ok && err < 1e-12, "err " + std::to_string(err));
    }

    // ---- MPC on a known stable first-order plant --------------------------
    {
        LtiModel M;
        M.n = M.m = M.p = 1;
        M.Ts = 0.01;
        M.A = Mat(1,1); M.A(0,0) = 0.9512;
        M.B = Mat(1,1); M.B(0,0) = 0.00975;
        M.C = Mat(1,1); M.C(0,0) = 1.0;
        M.D = Mat(1,1); M.D(0,0) = 0.0;

        MpcConfig cfg;
        MpcController mpc(M, cfg, 1);
        check("observer gain accepted (not silently zero)", mpc.observer_active(),
              "|pole| " + std::to_string(mpc.observer_pole()));
        check("observer error dynamics stable", mpc.observer_pole() < 1.0);

        // Closed-loop check on a plant whose DC gain is B/(1-A) = 0.19967.
        //
        // IMPORTANT PROPERTY, inherited faithfully from mpc_test.m: R penalises
        // the ABSOLUTE input, not its increment, and there is no integral action.
        // So the controller deliberately settles SHORT of its setpoint, at the
        // cost-optimal trade-off between tracking error and input effort:
        //
        //     u* = r_sp*g / (g^2 + R/Q)      y* = g*u*
        //
        // With Q = R = 1 and g = 0.1997 that is y* ~ 0.19 for a setpoint of 5 --
        // the input penalty dominates because the plant gain is small. This is
        // NOT a defect and not a porting error; it is what the MATLAB controller
        // does too. It matters operationally: on a low-gain plant, a default-
        // weighted MPC will look like it is barely responding when it is in fact
        // at its optimum. Lower r_weight (or raise q_weight) to close the gap.
        auto run_closed_loop = [&](double r_weight, int steps) {
            MpcConfig c = cfg;
            c.r_weight = r_weight;
            MpcController m(M, c, 1);
            m.set_target({5.0});
            double x = 0.0, u = 0.0;
            for (int k = 0; k < steps; ++k) {
                u = m.step({x})[0];
                x = M.A(0,0) * x + M.B(0,0) * u;
            }
            return std::pair<double, double>(x, u);
        };

        const std::pair<double, double> def = run_closed_loop(1.0, 4000);
        check("MPC settles at the cost-optimal offset (R = I)",
              def.first > 0.05 && def.first < 1.0,
              "y " + std::to_string(def.first) + " u " + std::to_string(def.second));

        // With the input penalty made negligible the same machinery must track
        // the setpoint closely. This is what actually proves the prediction
        // matrices, the condensation and the QP are correct -- the offset above
        // is a weighting choice, this is the arithmetic.
        const std::pair<double, double> tight = run_closed_loop(1e-4, 4000);
        check("MPC tracks setpoint when input penalty is small",
              std::fabs(tight.first - 5.0) < 0.25,
              "y " + std::to_string(tight.first) + " u " + std::to_string(tight.second));

        // The command must MOVE with the measurement -- the exact property whose
        // absence meant the MATLAB controller ran open-loop for months.
        double umin_seen = 1e30, umax_seen = -1e30;
        mpc.reset();
        mpc.set_target({5.0});
        for (int k = 0; k < 600; ++k) {
            const double meas = 3.0 + 3.0 * std::sin(k * 0.05);
            const double uk = mpc.step({meas})[0];
            if (k > 100) { umin_seen = std::min(umin_seen, uk); umax_seen = std::max(umax_seen, uk); }
        }
        check("MPC command responds to its measurement",
              (umax_seen - umin_seen) > 1e-3,
              "range " + std::to_string(umax_seen - umin_seen));
    }

    // ---- observer must REFUSE an unobservable model ----------------------
    {
        LtiModel M;
        M.n = 2; M.m = 1; M.p = 1;
        M.Ts = 0.01;
        M.A = Mat(2,2); M.A(0,0)=1.6; M.A(0,1)=0.0; M.A(1,0)=0.0; M.A(1,1)=1.4;
        M.B = Mat(2,1); M.B(0,0)=1.0; M.B(1,0)=0.0;
        M.C = Mat(1,2); M.C(0,0)=1.0; M.C(0,1)=0.0;   // 2nd state unobservable & unstable
        M.D = Mat(1,1); M.D(0,0)=0.0;
        MpcController mpc(M, MpcConfig(), 1);
        check("unstable-unobservable model rejected loudly", !mpc.observer_active(),
              "|pole| " + std::to_string(mpc.observer_pole()));
    }

    // ---- CSV replay loader (--play / --reference) ------------------------
    {
        const char* tmp = "cpp_ctl_selftest_tmp.csv";
        {
            std::ofstream f(tmp);
            f << "tick,u1,u2,y1\n1,0,5.5,9\n2,25,0,9\n3,0,0,9\n";
        }
        bool ok = false;
        std::string detail;
        try {
            const auto rows = load_csv_prefix(tmp, "u");
            ok = rows.size() == 3 && rows[0].size() == 2 &&
                 rows[0][1] == 5.5 && rows[1][0] == 25.0 && rows[2][0] == 0.0;
            detail = "3 rows x 2 u-cols, values exact";
            // header without the prefix must throw, not misload
            bool threw = false;
            try { load_csv_prefix(tmp, "r"); } catch (const std::exception&) { threw = true; }
            ok = ok && threw;
        } catch (const std::exception& e) {
            detail = e.what();
        }
        std::remove(tmp);
        check("CSV replay loader (--play/--reference)", ok, detail);
    }

    // ---- excitation ------------------------------------------------------
    {
        ExcitationConfig ec;
        ec.kind = "prbs"; ec.umin = 0; ec.umax = 30; ec.active = {3};
        Excitation ex(ec, 600, 16);
        double lo, hi; ex.range(lo, hi);
        bool others_zero = true, ch3_moves = false;
        double c3lo = 1e30, c3hi = -1e30;
        for (int t = 0; t < 600; ++t) {
            const std::vector<double> row = ex.at(t);
            for (int c = 0; c < 16; ++c)
                if (c != 2 && row[(size_t)c] != 0.0) others_zero = false;
            c3lo = std::min(c3lo, row[2]); c3hi = std::max(c3hi, row[2]);
        }
        ch3_moves = (c3hi - c3lo) > 1.0;
        check("excitation: only requested channel moves", others_zero && ch3_moves,
              "ch3 range " + std::to_string(c3lo) + ".." + std::to_string(c3hi));
        check("excitation: respects amplitude bounds", lo >= 0.0 && hi <= 30.0);
    }

    std::printf("\n%s (%d failure%s)\n", failures ? "SELF-TEST FAILED" : "SELF-TEST PASSED",
                failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}

// --------------------------------------------------------------------------
// live target file
// --------------------------------------------------------------------------
static bool read_target_file(const std::string& path, double& value) {
    std::ifstream f(path);
    if (!f) return false;
    double v;
    if (!(f >> v) || !std::isfinite(v)) return false;
    value = v;
    return true;
}

// --------------------------------------------------------------------------
int main(int argc, char** argv) {
    // Unbuffered stdout: this server is watched live in a terminal, and when it
    // dies the buffered tail is exactly the part that would explain why.
    setvbuf(stdout, NULL, _IONBF, 0);

    Options o;
    if (!parse_args(argc, argv, o)) return 1;
    if (o.selftest) return selftest();

    // ---- controller ------------------------------------------------------
    std::unique_ptr<IController> controller;
    std::unique_ptr<Excitation> excitation;
    MpcController* mpc_ptr = nullptr;
    std::vector<std::vector<double>> playU;    // openloop --play rows
    std::vector<std::vector<double>> refRows;  // mpc --reference rows

    try {
        if (o.mode == "constant") {
            controller.reset(new ConstantController(o.constant_value, o.output_count));
        } else if (o.mode == "openloop" && !o.play_file.empty()) {
            playU = load_csv_prefix(o.play_file, "u");
            double lo = 1e300, hi = -1e300;
            for (const auto& r : playU)
                for (double v : r) { lo = std::min(lo, v); hi = std::max(hi, v); }
            if (o.max_packets <= 0) o.max_packets = (long long)playU.size();
            std::printf("openloop: replaying %s verbatim -- %zu ticks (%.1f s), "
                        "%zu u columns, u in [%g %g], zeros after the last row\n",
                        o.play_file.c_str(), playU.size(), playU.size() / 100.0,
                        playU[0].size(), lo, hi);
            if ((int)playU[0].size() != o.output_count)
                std::printf("WARNING: design has %zu u columns but output-count is %d; "
                            "rows will be %s\n", playU[0].size(), o.output_count,
                            (int)playU[0].size() < o.output_count ? "zero-padded" : "truncated");
            if (o.capture_file.empty()) {
                o.capture_file = "capture_openloop_cpp.csv";
                std::printf("openloop: capture defaulted to %s\n", o.capture_file.c_str());
            }
        } else if (o.mode == "openloop") {
            const int ticks = (int)(o.max_packets > 0 ? o.max_packets : 6000);
            if (o.max_packets <= 0) {
                o.max_packets = ticks;
                std::printf("openloop: max-packets defaulted to %d ticks (%.0f s)\n",
                            ticks, ticks / 100.0);
            }
            excitation.reset(new Excitation(o.exc, ticks, o.output_count));
            double lo, hi; excitation->range(lo, hi);
            std::printf("openloop: %s excitation, %d ticks (%.1f s), u in [%g %g]\n",
                        o.exc.kind.c_str(), ticks, ticks / 100.0, lo, hi);
            std::printf("openloop: active stim channels [");
            for (size_t i = 0; i < excitation->active_channels().size(); ++i)
                std::printf("%s%d", i ? " " : "", excitation->active_channels()[i]);
            std::printf("] of %d\n", o.output_count);
            if (o.capture_file.empty()) {
                o.capture_file = "capture_openloop_cpp.csv";
                std::printf("openloop: capture defaulted to %s\n", o.capture_file.c_str());
            }
        } else if (o.mode == "mpc") {
            if (o.model_path.empty()) { std::printf("--mode mpc requires --model <file.lti>\n"); return 2; }
            const LtiModel M = load_lti(o.model_path);
            std::printf("Loaded plant %s: n=%d m=%d p=%d Ts=%g\n",
                        o.model_path.c_str(), M.n, M.m, M.p, M.Ts);
            std::unique_ptr<MpcController> mpc(new MpcController(M, o.mpc, o.output_count));
            if (!o.feature_map.empty()) {
                std::vector<int> zero_based;
                for (int v : o.feature_map) zero_based.push_back(v - 1);
                mpc->set_feature_map(zero_based);
                std::printf("Feature map (1-based): ");
                for (int v : o.feature_map) std::printf("%d ", v);
                std::printf("\n");
            }
            mpc->set_target(std::vector<double>((size_t)M.p, o.target));
            std::printf("Observer: %s (|pole| = %.6f)   target = %g\n",
                        mpc->observer_active() ? "ACTIVE" : "*** INACTIVE -- OPEN LOOP ***",
                        mpc->observer_pole(), o.target);
            if (!mpc->observer_active())
                std::printf("WARNING: the controller will ignore its measurement. "
                            "Do not trust closed-loop behaviour.\n");
            mpc_ptr = mpc.get();
            controller.reset(mpc.release());
            if (!o.reference_file.empty()) {
                refRows = load_csv_prefix(o.reference_file, "r");
                if (o.max_packets <= 0) o.max_packets = (long long)refRows.size();
                double lo = 1e300, hi = -1e300;
                for (const auto& r : refRows)
                    for (double v : r) { lo = std::min(lo, v); hi = std::max(hi, v); }
                std::printf("mpc: reference %s -- %zu ticks (%.1f s), %zu output(s), "
                            "range [%g %g]. Per-tick target, NO horizon preview "
                            "(backup path; MATLAB server previews).\n",
                            o.reference_file.c_str(), refRows.size(),
                            refRows.size() / 100.0, refRows[0].size(), lo, hi);
            }
            if (!o.stim_pairs.empty()) {
                std::printf("mpc: controller output(s) mapped to stim pair slot(s) [");
                for (size_t i = 0; i < o.stim_pairs.size(); ++i)
                    std::printf("%s%d", i ? " " : "", o.stim_pairs[i]);
                std::printf("]; all other slots 0.\n");
            } else {
                std::printf("NOTE: no --pairs given; a 1-output model drives PAIR 1 only.\n");
            }
        } else if (o.mode == "nn") {
            if (o.model_path.empty()) { std::printf("--mode nn requires --model <file.nnw>\n"); return 2; }
            const NnModel M = load_nnw(o.model_path);
            std::printf("Loaded network %s: arch=%s input=%d history=%d output=%d layers=%zu\n",
                        o.model_path.c_str(), M.arch.c_str(), M.input, M.history,
                        M.output, M.layers.size());
            std::printf("Guards: u in [%g %g], slew %s\n", o.nn.umin, o.nn.umax,
                        o.nn.max_rate > 0 ? std::to_string(o.nn.max_rate).c_str() : "disabled");
            controller.reset(new NnController(M, o.nn, o.output_count));
        } else {
            std::printf("unknown mode: %s\n", o.mode.c_str());
            return 2;
        }
    } catch (const std::exception& e) {
        std::printf("FATAL: %s\n", e.what());
        return 3;
    }

    // ---- socket ----------------------------------------------------------
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) { std::printf("WSAStartup failed\n"); return 4; }

    SOCKET s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (s == INVALID_SOCKET) { std::printf("socket() failed\n"); WSACleanup(); return 4; }

    sockaddr_in local{};
    local.sin_family = AF_INET;
    local.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    local.sin_port = htons((u_short)o.request_port);
    if (bind(s, (sockaddr*)&local, sizeof local) == SOCKET_ERROR) {
        std::printf("bind(%d) failed (%d) -- is another controller server running?\n",
                    o.request_port, WSAGetLastError());
        closesocket(s); WSACleanup(); return 4;
    }

    sockaddr_in reply{};
    reply.sin_family = AF_INET;
    reply.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    reply.sin_port = htons((u_short)o.reply_port);

    // 1 s receive timeout: long enough that idling does not spin, short enough
    // that a bounded run notices the loop has exited and flushes its logs.
    DWORD tv = 1000;
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);

    // openloop mode drives `excitation` and deliberately leaves `controller` null
    // (there is nothing to step -- the sequence is precomputed). Dereferencing it
    // here for a display string crashed the server at startup in that mode.
    const std::string mode_name = controller ? controller->name() : o.mode;
    std::printf("\nNative controller server ready. mode=%s requestPort=%d replyPort=%d outputCount=%d\n",
                mode_name.c_str(), o.request_port, o.reply_port, o.output_count);
    if (o.max_packets > 0) std::printf("Will stop automatically after %lld serviced packets.\n", o.max_packets);
    std::printf("Press Ctrl+C to stop.\n");

    // ---- loop ------------------------------------------------------------
    std::vector<unsigned char> rx(65536), tx(65536);
    long long packets = 0;
    std::vector<double> turnarounds;
    turnarounds.reserve(o.max_packets > 0 ? (size_t)o.max_packets : 20000);

    std::vector<std::vector<double>> cap_u, cap_y;
    std::vector<unsigned> cap_seq;
    std::vector<double> cap_t;

    std::ofstream logf;
    if (!o.log_file.empty()) { logf.open(o.log_file); logf << "seq,computeMs,turnaroundMs\n"; }

    const auto t_start = std::chrono::steady_clock::now();
    auto now_ms = [&]() {
        return std::chrono::duration<double, std::milli>(
                   std::chrono::steady_clock::now() - t_start).count();
    };

    while (true) {
        sockaddr_in from{};
        int fromlen = sizeof from;
        const int n = recvfrom(s, (char*)rx.data(), (int)rx.size(), 0, (sockaddr*)&from, &fromlen);
        if (n == SOCKET_ERROR) {
            if (o.max_packets > 0 && packets > 0) {
                std::printf("Idle after %lld packets; stopping bounded run.\n", packets);
                break;
            }
            continue;
        }

        const double t_wake = now_ms();
        Request rq;
        if (!parse_request(rx.data(), n, rq)) {
            std::printf("Ignoring malformed request (%d bytes)\n", n);
            continue;
        }
        ++packets;

        const double t_compute0 = now_ms();
        std::vector<double> u;
        if (!playU.empty()) {
            // Verbatim replay, indexed by packet count (same convention as the
            // generated excitation: a dropped request must not skip a slice of
            // the design). Past the last row the output is zero -- probe over.
            if (packets - 1 < (long long)playU.size())
                u = playU[(size_t)(packets - 1)];
            u.resize((size_t)o.output_count, 0.0);
        } else if (excitation) {
            // Indexed by packet count, not seq -- a dropped request must not skip
            // a slice of the designed sequence.
            u = excitation->at((int)(packets - 1));
            if ((int)u.size() != o.output_count) u.resize((size_t)o.output_count, 0.0);
        } else {
            if (mpc_ptr && !refRows.empty()) {
                // Per-tick reference: hold the final row after the trajectory
                // ends (a touch reference ends at baseline, so holding = idle).
                const size_t k = std::min((size_t)(packets - 1), refRows.size() - 1);
                mpc_ptr->set_target(refRows[k]);
            } else if (mpc_ptr && !o.target_file.empty() && (packets % 25 == 0)) {
                double tv2;
                if (read_target_file(o.target_file, tv2)) mpc_ptr->set_target({tv2});
            }
            u = controller->step(rq.features);
            if (!o.stim_pairs.empty()) {
                // Route controller output i to its physical bipolar pair slot
                // (matches matlab_controller_server's cfg.stimPairs). Without
                // this, a model identified on pair 3 would stimulate pair 1.
                std::vector<double> mapped((size_t)o.output_count, 0.0);
                for (size_t i = 0; i < o.stim_pairs.size() && i < u.size(); ++i) {
                    const int slot = o.stim_pairs[i] - 1;
                    if (slot >= 0 && slot < o.output_count)
                        mapped[(size_t)slot] = u[i];
                }
                u = mapped;
            }
        }
        const double compute_ms = now_ms() - t_compute0;

        const int tn = build_response(rq.seq, u, tx.data(), (int)tx.size());
        if (tn > 0) sendto(s, (const char*)tx.data(), tn, 0, (sockaddr*)&reply, sizeof reply);
        const double turn_ms = now_ms() - t_wake;
        turnarounds.push_back(turn_ms);

        if (logf) logf << rq.seq << "," << compute_ms << "," << turn_ms << "\n";

        if (!o.capture_file.empty()) {
            cap_seq.push_back(rq.seq);
            cap_t.push_back(now_ms());
            cap_u.push_back(u);
            cap_y.push_back(rq.features);
        }

        if (packets <= 5 || packets % 100 == 0) {
            // Same null-controller trap as the startup banner: in openloop mode
            // there is no IController to ask for status, only a precomputed
            // excitation sequence.
            const std::string status =
                controller ? controller->status()
                           : std::string(playU.empty() ? "excitation" : "replay");
            std::printf("Reply #%lld seq=%u feature0=%.6f out0=%.6f compute=%.3fms turnaround=%.3fms %s\n",
                        packets, rq.seq,
                        rq.features.empty() ? 0.0 : rq.features[0],
                        u.empty() ? 0.0 : u[0],
                        compute_ms, turn_ms, status.c_str());
        }

        if (o.max_packets > 0 && packets >= o.max_packets) break;
    }

    // ---- reporting -------------------------------------------------------
    if (!turnarounds.empty()) {
        std::vector<double> t = turnarounds;
        std::sort(t.begin(), t.end());
        double sum = 0.0; for (double v : t) sum += v;
        std::printf("\nServer turnaround over %zu packets: avg %.3f ms, median %.3f ms, "
                    "p95 %.3f ms, max %.3f ms\n",
                    t.size(), sum / t.size(), t[t.size() / 2],
                    t[(size_t)(0.95 * (t.size() - 1))], t.back());
    }
    if (!o.capture_file.empty() && !cap_u.empty()) {
        std::ofstream f(o.capture_file);
        f << "tick,seq,t_ms";
        for (size_t i = 0; i < cap_u[0].size(); ++i) f << ",u" << (i + 1);
        for (size_t i = 0; i < cap_y[0].size(); ++i) f << ",y" << (i + 1);
        f << "\n";
        f.precision(9);
        for (size_t k = 0; k < cap_u.size(); ++k) {
            f << (k + 1) << "," << cap_seq[k] << "," << cap_t[k];
            for (double v : cap_u[k]) f << "," << v;
            for (double v : cap_y[k]) f << "," << v;
            f << "\n";
        }
        std::printf("Wrote %zu capture rows to %s\n", cap_u.size(), o.capture_file.c_str());
    }
    if (logf) std::printf("Wrote timing log to %s\n", o.log_file.c_str());

    closesocket(s);
    WSACleanup();
    return 0;
}
