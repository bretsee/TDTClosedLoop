// test demo: start MATLAB, generate example input, run MPC step, quantize output, print diagnostics
#include <iostream>
#include <vector>
#include "MatlabEngine.hpp"
#include "MatlabDataArray.hpp"

// Calls MATLAB mpc_step(x) and converts data between C++ std::vector and MATLAB arrays
static std::vector<double> call_mpc_step(matlab::engine::MATLABEngine& eng,
                                         const std::vector<double>& x)
{
    using matlab::data::Array;
    using matlab::data::ArrayFactory;
    using matlab::data::TypedArray;

    ArrayFactory f;

    // Convert std::vector -> MATLAB Nx1 double
    TypedArray<double> x_m = f.createArray<double>({x.size(), 1});
    for (size_t i = 0; i < x.size(); ++i)
        x_m[i] = x[i];

    // Call MATLAB
    std::vector<Array> out = eng.feval(u"mpc_step", 1, std::vector<Array>{x_m});
    TypedArray<double> u_m = out[0];

    // Convert MATLAB -> std::vector
    std::vector<double> u(u_m.getNumberOfElements());
    for (size_t i = 0; i < u.size(); ++i)
        u[i] = u_m[i];

    return u;
}

// Scale, clamp, and round floating-point control outputs to integer DAC/amplitude values
static std::vector<int32_t> quantize_amplitudes(const std::vector<double>& u,
                                                double scale,
                                                int32_t minVal,
                                                int32_t maxVal)
{
    std::vector<int32_t> out(u.size());
    for (size_t i = 0; i < u.size(); ++i) {
        double v = u[i] * scale;
        if (v < (double)minVal) v = (double)minVal;
        if (v > (double)maxVal) v = (double)maxVal;
        out[i] = (int32_t)llround(v);
    }
    return out;
}


int main()
{
    auto eng = matlab::engine::startMATLAB();

    eng->eval(u"cd('C:/Users/brets/Documents/MATLAB')");

    // Example input vector
    const size_t N = 16;
    std::vector<double> x(N);
    for (size_t i = 0; i < N; ++i)
        x[i] = double(i + 1);

    std::vector<double> u = call_mpc_step(*eng, x);
    auto amps = quantize_amplitudes(u, /*scale=*/1.0, /*min=*/0, /*max=*/100000);
    std::cout << "amps[0] = " << amps[0] << "\n";

    std::cout << "u length = " << u.size() << "\n";
    std::cout << "u[0] = " << u[0] << "\n";

    return 0;
}
