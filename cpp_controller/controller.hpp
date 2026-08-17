// controller.hpp -- the interface every control architecture implements.
//
// One tick in, one command vector out. The server owns the socket and the
// timing; a controller only ever sees a feature vector and returns amplitudes.
// Keeping that boundary narrow is what lets an MPC, a neural network, or a
// constant be swapped by a command-line flag with nothing else changing -- and
// what lets each be tested off-line without a socket.
#pragma once

#include <string>
#include <vector>

namespace ctl {

class IController {
public:
    virtual ~IController() = default;

    // One control tick. `features` is the preprocessed vector from the C++
    // acquisition loop; the return is one commanded amplitude per stimulation
    // channel, already clamped to the configured physical bounds.
    //
    // IMPLEMENTATIONS MUST NOT THROW from here. This runs inside the 10 ms
    // budget; a controller that fails should return its fail-safe command
    // (typically the previous one, or zeros) and report through status().
    virtual std::vector<double> step(const std::vector<double>& features) = 0;

    // Clear all internal state -- estimator, recurrent state, warm start.
    virtual void reset() = 0;

    virtual std::string name() const = 0;

    // Human-readable one-liner describing the last tick, for the server log.
    virtual std::string status() const { return std::string(); }
};

}  // namespace ctl
