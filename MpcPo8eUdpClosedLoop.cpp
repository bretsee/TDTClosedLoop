#include <cstdlib>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include <algorithm>
#include <cmath>
#include <exception>
#include <iostream>
#include <string>
#include <inttypes.h>
#include <fstream>
#include <memory>
#include <limits>
#include <atomic>

#include "PO8e.h"
#include "SampleSource.h"
#include "compat.h"
#include "TDTUDP.h"
#include "MatlabEngine.hpp"
#include "MatlabDataArray.hpp"

// ============================================================================
// SECTION 1: UDP/Winsock bootstrap helpers
// ----------------------------------------------------------------------------
// These wrappers keep socket startup/cleanup explicit in main().
// ============================================================================
static bool udp_init()
{
    WSADATA wsa;
    return (WSAStartup(MAKEWORD(2, 2), &wsa) == 0);
}

static void udp_cleanup()
{
    WSACleanup();
}

static int64_t hires_now_us()
{
    LARGE_INTEGER freq {};
    if (QueryPerformanceFrequency(&freq) == 0 || freq.QuadPart == 0)
        return 0;

    LARGE_INTEGER t {};
    QueryPerformanceCounter(&t);
    return (int64_t)((t.QuadPart * 1000000LL) / freq.QuadPart);
}

struct HiResClock
{
    LARGE_INTEGER freq {};
    bool ok = false;

    HiResClock()
    {
        ok = (QueryPerformanceFrequency(&freq) != 0);
    }

    int64_t now_us() const
    {
        if (!ok || freq.QuadPart == 0)
            return 0;
        return hires_now_us();
    }
};

struct TimingStats
{
    uint64_t count = 0;
    int64_t totalUs = 0;
    int64_t minUs = INT64_MAX;
    int64_t maxUs = 0;

    void add(int64_t us)
    {
        if (us < 0)
            us = 0;
        ++count;
        totalUs += us;
        minUs = std::min(minUs, us);
        maxUs = std::max(maxUs, us);
    }
};

static void print_timing_stats(const char* label, const TimingStats& stats)
{
    const int64_t minUs = (stats.count > 0) ? stats.minUs : 0;
    const double avgUs = (stats.count > 0)
        ? ((double)stats.totalUs / (double)stats.count)
        : 0.0;
    const int64_t maxUs = (stats.count > 0) ? stats.maxUs : 0;
    std::printf("%s count=%llu minUs=%lld avgUs=%.1f maxUs=%lld\n",
                label,
                (unsigned long long)stats.count,
                (long long)minUs,
                avgUs,
                (long long)maxUs);
}

struct LocalhostRequestDiagnostics
{
    int drainedReplies = 0;
    int staleReplies = 0;
    int64_t roundTripUs = 0;
};

static std::vector<double> normalize_controller_output(const std::vector<double>& rawOutput,
                                                       size_t outputCount);

// Resolve the user-provided host/IP to an IPv4 address usable by openSocket().
// openSocket() expects a raw IPv4 value (in network byte order).
static uint32_t resolve_ipv4_addr(const char* host)
{
    if (!host || !*host)
        return INADDR_NONE;

    const unsigned long dotted = inet_addr(host);
    if (dotted != INADDR_NONE)
        return (uint32_t)dotted;

    addrinfo hints {};
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_DGRAM;
    hints.ai_protocol = IPPROTO_UDP;

    addrinfo* res = nullptr;
    if (getaddrinfo(host, "22022", &hints, &res) != 0 || !res)
        return INADDR_NONE;

    const sockaddr_in* sin = reinterpret_cast<const sockaddr_in*>(res->ai_addr);
    const uint32_t out = sin->sin_addr.S_un.S_addr;
    freeaddrinfo(res);
    return out;
}

static SOCKET open_localhost_controller_socket(const char* host,
                                               uint16_t remotePort,
                                               uint16_t localPort,
                                               int timeoutMs)
{
    addrinfo hints {};
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_DGRAM;
    hints.ai_protocol = IPPROTO_UDP;

    char remotePortText[16] = { 0 };
    std::snprintf(remotePortText, sizeof(remotePortText), "%u", (unsigned)remotePort);

    addrinfo* res = nullptr;
    if (getaddrinfo(host, remotePortText, &hints, &res) != 0 || !res)
        return INVALID_SOCKET;

    SOCKET sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock == INVALID_SOCKET)
    {
        freeaddrinfo(res);
        return INVALID_SOCKET;
    }

    sockaddr_in localAddr {};
    localAddr.sin_family = AF_INET;
    localAddr.sin_port = htons(localPort);
    localAddr.sin_addr.S_un.S_addr = htonl(INADDR_LOOPBACK);

    if (bind(sock, reinterpret_cast<const sockaddr*>(&localAddr), sizeof(localAddr)) != 0)
    {
        closesocket(sock);
        freeaddrinfo(res);
        return INVALID_SOCKET;
    }

    if (connect(sock, res->ai_addr, (int)res->ai_addrlen) != 0)
    {
        closesocket(sock);
        freeaddrinfo(res);
        return INVALID_SOCKET;
    }

    const DWORD timeout = (DWORD)std::max(timeoutMs, 1);
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    freeaddrinfo(res);
    return sock;
}

static bool set_socket_nonblocking(SOCKET sock, bool enabled)
{
    u_long mode = enabled ? 1UL : 0UL;
    return (ioctlsocket(sock, FIONBIO, &mode) == 0);
}

static bool try_parse_localhost_reply_header(const char* recvBuf,
                                             int got,
                                             uint32_t* replySeq,
                                             uint32_t* replyCount)
{
    if (!recvBuf || got < 8 || !replySeq || !replyCount)
        return false;

    uint32_t replySeqNet = 0;
    uint32_t replyCountNet = 0;
    std::memcpy(&replySeqNet, recvBuf, 4);
    std::memcpy(&replyCountNet, recvBuf + 4, 4);
    *replySeq = ntohl(replySeqNet);
    *replyCount = ntohl(replyCountNet);
    return true;
}

static bool send_localhost_controller_request(SOCKET sock,
                                              uint32_t sequence,
                                              const std::vector<double>& features,
                                              std::string* errorMessage)
{
    // Requests are packed as [seq][count][float32 payload] in network byte order.
    // The single-thread async loop calls this only when no older request is in flight.
    const uint32_t featureCount = (uint32_t)features.size();
    const size_t packetBytes = 8 + (size_t)featureCount * 4;
    std::vector<char> packet(packetBytes, 0);

    const uint32_t seqNet = htonl(sequence);
    const uint32_t countNet = htonl(featureCount);
    std::memcpy(packet.data(), &seqNet, sizeof(seqNet));
    std::memcpy(packet.data() + 4, &countNet, sizeof(countNet));
    for (uint32_t i = 0; i < featureCount; ++i)
    {
        float v = (float)features[i];
        uint32_t bits = 0;
        std::memcpy(&bits, &v, sizeof(v));
        bits = htonl(bits);
        std::memcpy(packet.data() + 8 + (size_t)i * 4, &bits, 4);
    }

    const int sent = send(sock, packet.data(), (int)packet.size(), 0);
    if (sent != (int)packet.size())
    {
        if (errorMessage != NULL)
            *errorMessage = "localhost controller send failed";
        return false;
    }
    return true;
}

static bool try_recv_localhost_controller_reply(SOCKET sock,
                                                uint32_t expectedSequence,
                                                std::vector<double>* response,
                                                LocalhostRequestDiagnostics* diagnostics,
                                                std::string* errorMessage)
{
    // Poll one or more queued datagrams without blocking. We accept only the
    // reply matching the current in-flight sequence and silently discard older
    // replies that arrived after the scheduler had already moved on.
    if (response == NULL)
        return false;
    response->clear();
    if (diagnostics != NULL)
        *diagnostics = LocalhostRequestDiagnostics {};

    char recvBuf[4096] = { 0 };
    int staleReplies = 0;
    for (;;)
    {
        const int got = recv(sock, recvBuf, sizeof(recvBuf), 0);
        if (got == SOCKET_ERROR)
        {
            const int wsa = WSAGetLastError();
            if (wsa == WSAEWOULDBLOCK)
                return false;
            if (errorMessage != NULL)
                *errorMessage = "localhost controller recv failed";
            return false;
        }

        uint32_t replySeq = 0;
        uint32_t replyCount = 0;
        if (!try_parse_localhost_reply_header(recvBuf, got, &replySeq, &replyCount))
        {
            continue;
        }

        if (replySeq != expectedSequence)
        {
            ++staleReplies;
            if (diagnostics != NULL)
                diagnostics->staleReplies = staleReplies;
            continue;
        }
        if (got < (int)(8 + (size_t)replyCount * 4))
        {
            if (errorMessage != NULL)
                *errorMessage = "localhost controller reply payload truncated";
            return false;
        }

        response->assign(replyCount, 0.0);
        for (uint32_t i = 0; i < replyCount; ++i)
        {
            uint32_t bitsNet = 0;
            std::memcpy(&bitsNet, recvBuf + 8 + (size_t)i * 4, 4);
            uint32_t bits = ntohl(bitsNet);
            float v = 0.0f;
            std::memcpy(&v, &bits, sizeof(v));
            (*response)[i] = (double)v;
        }
        if (diagnostics != NULL)
            diagnostics->staleReplies = staleReplies;
        return true;
    }
}

// ============================================================================
// SECTION 2: MATLAB MPC bridge helpers
// ----------------------------------------------------------------------------
// call_matlab_controller() converts C++ vector -> MATLAB array, calls the named
// MATLAB controller function, then converts MATLAB output back into a C++ vector.
// ============================================================================
static std::vector<double> call_matlab_controller(matlab::engine::MATLABEngine& eng,
                                                  const std::u16string& functionName,
                                                  const std::vector<double>& x)
{
    using matlab::data::Array;
    using matlab::data::ArrayFactory;
    using matlab::data::TypedArray;

    ArrayFactory f;
    TypedArray<double> x_m = f.createArray<double>({x.size(), 1});
    for (size_t i = 0; i < x.size(); ++i)
        x_m[i] = x[i];

    std::vector<Array> args;
    args.push_back(x_m);
    std::vector<Array> out = eng.feval(functionName, 1, args);
    TypedArray<double> u_m = out[0];

    std::vector<double> u(u_m.getNumberOfElements());
    for (size_t i = 0; i < u.size(); ++i)
        u[i] = u_m[i];

    return u;
}

static std::vector<double> normalize_controller_output(const std::vector<double>& rawOutput,
                                                       size_t outputCount)
{
    // Controllers may return either a scalar or a full output vector. Normalize
    // both into a fixed-width vector so downstream UDP code can stay simple.
    //
    // A scalar reply goes to SLOT 0 ONLY. It used to be broadcast to every
    // output, which is a safety defect in the standard workflow: a single-pair
    // sysid capture yields an m=1 model, mpc_test then returns a scalar, and the
    // broadcast delivered that command to all 8 bipolar pairs -- stimulating 7
    // sites the operator believes are off. The mapping from a single-input model
    // to the RIGHT pair belongs server-side (matlab_controller_server
    // cfg.stimPairs / 4_mpc_server -Pairs), which returns a full-width vector.
    const size_t nOut = std::max<size_t>(outputCount, 1);
    std::vector<double> out(nOut, 0.0);
    if (rawOutput.empty())
        return out;

    if (rawOutput.size() == 1 && nOut > 1)
    {
        static bool warned = false;
        if (!warned)
        {
            warned = true;
            std::printf("WARNING: controller replied with 1 value for %zu outputs; "
                        "sending it on OUTPUT 1 ONLY (no broadcast). If a different "
                        "stim pair was identified, set the server-side pair mapping "
                        "(4_mpc_server -Pairs <n>).\n", nOut);
        }
        out[0] = rawOutput[0];
        return out;
    }

    const size_t nCopy = std::min(rawOutput.size(), out.size());
    for (size_t i = 0; i < nCopy; ++i)
        out[i] = rawOutput[i];
    return out;
}

// Clamp/scale MPC outputs into int32 amplitudes for UDP transmission.
// Current tuning is pass-through scale=1.0 and [0, 100000] clamp in main().
static std::vector<int32_t> quantize_amplitudes(const std::vector<double>& u,
                                                double scale,
                                                int32_t minVal,
                                                int32_t maxVal)
{
    std::vector<int32_t> out(u.size());
    for (size_t i = 0; i < u.size(); ++i)
    {
        double v = u[i] * scale;
        if (v < (double)minVal) v = (double)minVal;
        if (v > (double)maxVal) v = (double)maxVal;
        out[i] = (int32_t)llround(v);
    }
    return out;
}

static std::vector<float> clamp_amplitudes_f32(const std::vector<double>& u,
                                               float minVal,
                                               float maxVal)
{
    std::vector<float> out(u.size());
    for (size_t i = 0; i < u.size(); ++i)
    {
        float v = (float)u[i];
        if (v < minVal) v = minVal;
        if (v > maxVal) v = maxVal;
        out[i] = v;
    }
    return out;
}

static std::vector<float> clamp_amplitudes_f32_from_cached(const std::vector<double>& rawOutput,
                                                           size_t outputCount,
                                                           float minVal,
                                                           float maxVal)
{
    const size_t nOut = std::max<size_t>(outputCount, 1);
    std::vector<float> out(nOut, 0.0f);
    if (rawOutput.empty())
        return out;

    if (rawOutput.size() == 1 && nOut > 1)
    {
        // Slot 0 only -- same no-broadcast rule as normalize_controller_output.
        float v = (float)rawOutput[0];
        if (v < minVal) v = minVal;
        if (v > maxVal) v = maxVal;
        out[0] = v;
        return out;
    }

    const size_t nCopy = std::min(rawOutput.size(), out.size());
    for (size_t i = 0; i < nCopy; ++i)
    {
        float v = (float)rawOutput[i];
        if (v < minVal) v = minVal;
        if (v > maxVal) v = maxVal;
        out[i] = v;
    }
    return out;
}

// Build MATLAB input vector from preprocessed control features.
// The first inputCount entries come from the feature vector. The vector is padded
// out to outputCount so MATLAB can emit one value per intended UDP output channel.
static std::vector<double> build_mpc_input(const std::vector<double>& features,
                                           size_t inputCount,
                                           size_t outputCount)
{
    const size_t totalCount = std::max(inputCount, outputCount);
    std::vector<double> x(totalCount, 0.0);
    const size_t n = std::min(inputCount, features.size());
    for (size_t i = 0; i < n; ++i)
        x[i] = features[i];
    return x;
}

static std::vector<double> build_constant_input(size_t count, double value)
{
    std::vector<double> x(std::max<size_t>(count, 1), value);
    return x;
}

static void shutdown_matlab_controller(std::unique_ptr<matlab::engine::MATLABEngine>& eng,
                                       const std::string& controllerMode)
{
    if (!eng)
        return;

    try
    {
        if (controllerMode == "mpc_test")
            eng->eval(u"try, mpc_test([]); catch, end");
    }
    catch (...)
    {
        // Best-effort reset only.
    }

    eng.reset();
}

struct SampleRingBuffer
{
    size_t capacity = 0;
    size_t writeIndex = 0;
    size_t size = 0;
    std::vector<int64_t> timestampsUs;
    std::vector<std::vector<float> > channelValues;

    void initialize(size_t channelCount, size_t bufferCapacity)
    {
        capacity = std::max<size_t>(bufferCapacity, 1);
        writeIndex = 0;
        size = 0;
        timestampsUs.assign(capacity, 0);
        channelValues.assign(channelCount, std::vector<float>(capacity, 0.0f));
    }

    void pushFrame(const std::vector<float>& frame, int64_t timestampUs)
    {
        if (capacity == 0 || channelValues.empty())
            return;

        timestampsUs[writeIndex] = timestampUs;
        const size_t n = std::min(frame.size(), channelValues.size());
        for (size_t ch = 0; ch < n; ++ch)
            channelValues[ch][writeIndex] = frame[ch];

        writeIndex = (writeIndex + 1) % capacity;
        if (size < capacity)
            ++size;
    }

    // Placeholder preprocessing: mean absolute value over the most recent window.
    std::vector<double> computeMeanAbsWindow(size_t inputCount,
                                             int64_t windowEndUs,
                                             int64_t windowUs,
                                             size_t* minSamplesSeen = NULL) const
    {
        std::vector<double> out(inputCount, 0.0);
        if (size == 0 || channelValues.empty())
        {
            if (minSamplesSeen != NULL)
                *minSamplesSeen = 0;
            return out;
        }

        const int64_t windowStartUs = windowEndUs - windowUs;
        std::vector<size_t> counts(inputCount, 0);

        for (size_t k = 0; k < size; ++k)
        {
            const size_t idx = (writeIndex + capacity - 1 - k) % capacity;
            const int64_t ts = timestampsUs[idx];
            if (ts < windowStartUs)
                break;

            const size_t n = std::min(inputCount, channelValues.size());
            for (size_t ch = 0; ch < n; ++ch)
            {
                out[ch] += std::fabs((double)channelValues[ch][idx]);
                ++counts[ch];
            }
        }

        for (size_t ch = 0; ch < inputCount; ++ch)
        {
            if (counts[ch] > 0)
                out[ch] /= (double)counts[ch];
        }

        if (minSamplesSeen != NULL)
        {
            size_t minCount = counts.empty() ? 0 : counts[0];
            for (size_t ch = 1; ch < counts.size(); ++ch)
                minCount = std::min(minCount, counts[ch]);
            *minSamplesSeen = minCount;
        }

        return out;
    }

    // Fixed-sample-count preprocessing: mean absolute value over the most recent
    // nSamples frames per channel, independent of when those samples ARRIVED.
    //
    // This replaces computeMeanAbsWindow for the live path. The PO8e delivers in
    // bursts, so a fixed 10 ms of ARRIVAL time held anywhere from 3 to 5,439
    // samples on hardware -- at the top end averaging ~200 ms of signal, which
    // washes out the 15-28 ms evoked response we are trying to measure. A fixed
    // count makes every tick's feature comparable regardless of delivery jitter.
    //
    // It also lets the window be chosen as a whole number of stim periods. At
    // 610.3516 Hz acquisition (base/40) and 101.7253 Hz stim (base/240) there are
    // exactly 6 samples per stim period, so any multiple of 6 spans a whole number
    // of artifact cycles and the artifact becomes a constant offset rather than a
    // tick-to-tick wobble that would look like signal.
    // signedMean = false (default): mean(|x|), the validated rectified feature.
    // signedMean = true (--feature-signed, 2026-08-20): plain mean(x) -- a
    // block-averaged decimation of the signed LFP, matching Choi 2016's use of
    // the signed 5-200 Hz LFP as the controlled variable. Same window, same
    // carrier alignment; only the rectification differs.
    std::vector<double> computeMeanAbsSamples(size_t inputCount,
                                              size_t nSamples,
                                              size_t* samplesUsed = NULL,
                                              bool signedMean = false) const
    {
        std::vector<double> out(inputCount, 0.0);
        const size_t take = std::min(nSamples, size);
        if (samplesUsed != NULL)
            *samplesUsed = take;
        if (take == 0 || channelValues.empty())
            return out;

        const size_t n = std::min(inputCount, channelValues.size());
        for (size_t k = 0; k < take; ++k)
        {
            const size_t idx = (writeIndex + capacity - 1 - k) % capacity;
            for (size_t ch = 0; ch < n; ++ch)
            {
                const double v = (double)channelValues[ch][idx];
                out[ch] += signedMean ? v : std::fabs(v);
            }
        }

        for (size_t ch = 0; ch < n; ++ch)
            out[ch] /= (double)take;

        return out;
    }
};

// Drive every stim output to zero before releasing the RZ2.
//
// StimGen free-runs and the RZ2 HOLDS the last commanded amplitude, so simply
// exiting leaves the stimulator delivering that amplitude indefinitely. Measured
// 2026-08-14 (block LD-260814-155801): 41.5 s of continuous stimulation at the
// full commanded amplitude after the controller exited, ending only when the
// recording was stopped by hand. This applies to crashes and Ctrl+C too, which is
// exactly when nobody is watching the console.
//
// send_envelope.py has always zeroed on exit; the control loop never did.
// Sent repeatedly because UDP is lossy and this is the one packet that must land.
//
// Deliberately allocation-free: this is also called from the console-control and
// unhandled-exception handlers below, where the heap may be the thing that broke
// (2026-08-15: the 0xc0000374 crashes were heap corruption).
static void zero_stim_outputs(SOCKET sock, size_t outputCount);

// Emergency-zero state. C++ catch blocks cannot see console close, Ctrl+C, or
// SEH faults, so before 2026-08-15 every one of those left the RZ2 holding the
// last commanded amplitude (measured: 41.5 s of continuous stim after exit,
// block LD-260814-155801). The handlers below are armed once the RZ socket is
// live and cover:
//   - Ctrl+C / Ctrl+Break / console close  (SetConsoleCtrlHandler)
//   - unhandled SEH faults, best effort    (SetUnhandledExceptionFilter;
//     returns EXCEPTION_CONTINUE_SEARCH so WER still writes the crash dump)
// A hard external kill (TerminateProcess / Stop-Process) still bypasses
// everything a process can do -- the durable answer is an RZ2-side watchdog
// that zeros on UDP silence, which does not exist yet.
static std::atomic<uintptr_t> g_emergencySock{(uintptr_t)INVALID_SOCKET};
static std::atomic<size_t>    g_emergencyOutputs{0};

static void zero_stim_outputs(SOCKET sock, size_t outputCount)
{
    if (sock == INVALID_SOCKET || outputCount == 0)
        return;
    const uint8_t n = (uint8_t)std::min<size_t>(outputCount, (size_t)MAX_SAMPLES);
    static float zeros[MAX_SAMPLES] = { 0.0f };
    int sent = 0;
    for (int i = 0; i < 5; ++i)
    {
        if (sendUDPPacketWords(sock, zeros, n) != SOCKET_ERROR)
            ++sent;
        compatUSleep(2000);
    }
    std::printf("Cleanup trace: zeroed %u stim output(s), %d/5 packets acknowledged by send()\n",
                (unsigned)n, sent);
    // One zeroing is enough; disarm so a later Ctrl+C on a closed socket is a no-op.
    g_emergencySock.store((uintptr_t)INVALID_SOCKET);
}

static void emergency_zero_now(const char* why)
{
    const SOCKET sock = (SOCKET)g_emergencySock.exchange((uintptr_t)INVALID_SOCKET);
    const size_t n = g_emergencyOutputs.load();
    if (sock == INVALID_SOCKET || n == 0)
        return;
    std::printf("\nEMERGENCY STIM ZERO (%s)\n", why);
    const uint8_t count = (uint8_t)std::min<size_t>(n, (size_t)MAX_SAMPLES);
    static float zeros[MAX_SAMPLES] = { 0.0f };
    for (int i = 0; i < 5; ++i)
        sendUDPPacketWords(sock, zeros, count);
}

static BOOL WINAPI console_ctrl_zero_handler(DWORD ctrlType)
{
    (void)ctrlType;
    emergency_zero_now("console control event");
    return FALSE;   // let the default handler terminate the process afterwards
}

static LONG WINAPI unhandled_exception_zero_filter(EXCEPTION_POINTERS* info)
{
    (void)info;
    emergency_zero_now("unhandled exception");
    return EXCEPTION_CONTINUE_SEARCH;   // WER still runs and writes the dump
}

static void arm_emergency_zero(SOCKET sock, size_t outputCount)
{
    g_emergencyOutputs.store(outputCount);
    g_emergencySock.store((uintptr_t)sock);
    SetConsoleCtrlHandler(console_ctrl_zero_handler, TRUE);
    SetUnhandledExceptionFilter(unhandled_exception_zero_filter);
}

int main(int argc, char** argv)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    std::printf("MpcPo8eUdpClosedLoop build: %s %s\n", __DATE__, __TIME__);

    // --test-udp mode:
    //   MpcPo8eUdpClosedLoop.exe --test-udp [tdt_host_or_ip] [value] [count] [period_ms]
    // Example:
    //   MpcPo8eUdpClosedLoop.exe --test-udp 10.1.0.100 12345 4 20
    // (RZ2 = 10.1.0.100; 10.1.0.1 is this PC's own static address, not a target.)
    if (argc >= 2 && std::string(argv[1]) == "--test-udp")
    {
        const char* testHost = (argc >= 3) ? argv[2] : "10.1.0.100";
        const float testValue = (argc >= 4) ? (float)std::atof(argv[3]) : 1000.0f;
        int testCount = (argc >= 5) ? std::atoi(argv[4]) : 1;
        const int periodMs = (argc >= 6) ? std::max(1, std::atoi(argv[5])) : 20;

        if (testCount < 1) testCount = 1;
        if (testCount > MAX_SAMPLES) testCount = MAX_SAMPLES;

        if (!udp_init())
        {
            std::printf("UDP init failed.\n");
            return 1;
        }

        const uint32_t rzIp = resolve_ipv4_addr(testHost);
        if (rzIp == INADDR_NONE)
        {
            std::printf("Failed to resolve IPv4 target '%s'\n", testHost);
            udp_cleanup();
            return 1;
        }

        SOCKET testSock = openSocket(rzIp);
        if (testSock == INVALID_SOCKET)
        {
            std::printf("Failed to open UDP socket to '%s'.\n", testHost);
            udp_cleanup();
            return 1;
        }

        // Match UDPExample behavior, but avoid indefinite block in checkRZ().
        {
            DWORD timeoutMs = 1000;
            setsockopt(testSock, SOL_SOCKET, SO_RCVTIMEO,
                       reinterpret_cast<const char*>(&timeoutMs), sizeof(timeoutMs));
        }
        if (checkRZ(testSock))
            std::printf("checkRZ: ACK received.\n");
        else
            std::printf("checkRZ: no ACK (continuing test send).\n");

        if (!setRemoteIp(testSock))
            std::printf("Warning: SET_REMOTE_IP failed.\n");

        std::printf("UDP test mode: host=%s value=%g count=%d periodMs=%d\n",
                    testHost, (double)testValue, testCount, periodMs);
        std::printf("Payload format: sendUDPPacket(float), network byte order\n");
        std::printf("Press Ctrl+C to stop.\n");

        float v = testValue;
        while (true)
        {
            // Test mode sends one float in network byte order.
            if (sendUDPPacket(testSock, v) == SOCKET_ERROR)
                std::printf("Warning: UDP send failed.\n");
            if (testCount > 1)
                v += 1.0f;
            compatUSleep((uint32_t)periodMs * 1000);
        }

        disconnectRZ(testSock);
        udp_cleanup();
        return 0;
    }

    if (argc >= 2 && std::string(argv[1]) == "--test-udp-once")
    {
        const char* testHost = (argc >= 3) ? argv[2] : "10.1.0.100";
        const float testValue = (argc >= 4) ? (float)std::atof(argv[3]) : 5.0f;

        if (!udp_init())
        {
            std::printf("UDP init failed.\n");
            return 1;
        }

        const uint32_t rzIp = resolve_ipv4_addr(testHost);
        if (rzIp == INADDR_NONE)
        {
            std::printf("Failed to resolve IPv4 target '%s'\n", testHost);
            udp_cleanup();
            return 1;
        }

        SOCKET testSock = openSocket(rzIp);
        if (testSock == INVALID_SOCKET)
        {
            std::printf("Failed to open UDP socket to '%s'.\n", testHost);
            udp_cleanup();
            return 1;
        }

        if (!setRemoteIp(testSock))
            std::printf("Warning: SET_REMOTE_IP failed.\n");

        std::printf("UDP one-shot mode: host=%s value=%g\n", testHost, (double)testValue);
        std::printf("Payload format: single float, network byte order\n");
        const int sent = sendUDPPacket(testSock, testValue);
        std::printf("sendUDPPacket returned: %d\n", sent);

        disconnectRZ(testSock);
        udp_cleanup();
        return (sent == SOCKET_ERROR) ? 1 : 0;
    }

    if (argc >= 2 && std::string(argv[1]) == "--test-udp-words")
    {
        const char* testHost = (argc >= 3) ? argv[2] : "10.1.0.100";
        int testCount = (argc >= 4) ? std::atoi(argv[3]) : 8;
        const float baseValue = (argc >= 5) ? (float)std::atof(argv[4]) : 5.0f;
        const float stepValue = (argc >= 6) ? (float)std::atof(argv[5]) : 5.0f;
        const int periodMs = (argc >= 7) ? std::max(1, std::atoi(argv[6])) : 100;

        if (testCount < 1) testCount = 1;
        if (testCount > MAX_SAMPLES) testCount = MAX_SAMPLES;

        if (!udp_init())
        {
            std::printf("UDP init failed.\n");
            return 1;
        }

        const uint32_t rzIp = resolve_ipv4_addr(testHost);
        if (rzIp == INADDR_NONE)
        {
            std::printf("Failed to resolve IPv4 target '%s'\n", testHost);
            udp_cleanup();
            return 1;
        }

        SOCKET testSock = openSocket(rzIp);
        if (testSock == INVALID_SOCKET)
        {
            std::printf("Failed to open UDP socket to '%s'.\n", testHost);
            udp_cleanup();
            return 1;
        }

        if (!setRemoteIp(testSock))
            std::printf("Warning: SET_REMOTE_IP failed.\n");

        std::vector<float> payload((size_t)testCount, 0.0f);
        for (int i = 0; i < testCount; ++i)
            payload[(size_t)i] = baseValue + stepValue * (float)i;

        std::printf("UDP multi-word test: host=%s count=%d periodMs=%d\n", testHost, testCount, periodMs);
        std::printf("Payload[0..%d]:", testCount - 1);
        for (int i = 0; i < testCount; ++i)
            std::printf(" %g", (double)payload[(size_t)i]);
        std::printf("\n");
        std::printf("Payload format: %d float words, network byte order\n", testCount);
        std::printf("Press Ctrl+C to stop.\n");

        while (true)
        {
            if (sendUDPPacketWords(testSock, payload.data(), (uint8_t)testCount) == SOCKET_ERROR)
                std::printf("Warning: UDP send failed.\n");
            compatUSleep((uint32_t)periodMs * 1000);
        }

        disconnectRZ(testSock);
        udp_cleanup();
        return 0;
    }

    // =========================================================================
    // SECTION 3: Runtime arguments
    // -------------------------------------------------------------------------
    // argv[1]: RZ target host/IP
    // argv[2]: MATLAB working directory containing mpc_step.m
    // argv[3]: MPC input vector size
    // Optional flags:
    //   --controller constant|ramp|mpc_test|mpc_test_cached|localhost|localhost_constant
    //   --constant-output V
    //   --udp-output-count N
    //   --ring-buffer-capacity N
    //   --validate-log path.csv
    //   --matlab-start-delay-ticks N
    //   --fast-exit
    //   --skip-udp-send
    //   --max-control-ticks N
    //   --feature-window-samples N
    //                            frames per channel averaged into each feature
    //                            (default 6 = one 101.7253 Hz stim period at the
    //                            610.3516 Hz acquisition rate). Prefer multiples
    //                            of 6 so the stim artifact spans whole cycles.
    //   --feature-signed         feature = mean(x) instead of mean(|x|): the
    //                            signed block-averaged LFP (Choi 2016 controls
    //                            the signed 5-200 Hz LFP). Default remains the
    //                            rectified mean; models/references fitted in
    //                            one mode are NOT valid in the other.
    //   --tick-frames N          0 (default) = wall-clock 10 ms scheduling.
    //                            N>0 = FRAME-LOCKED via a software PLL: ticks fire
    //                            on the smooth PC clock, with period/phase steered
    //                            onto the PO8e frame-counter grid (the RZ2
    //                            crystal). N=6 at 610.3516 Hz = 9.8304 ms =
    //                            exactly one 101.7253 Hz stim-carrier period, so
    //                            each single-tick command window gates exactly one
    //                            carrier latch. Wall-clock ticking beat against
    //                            the carrier (1.9% missed / 4.2% doubled probe
    //                            pulses, 2026-08-18 AM); firing directly on frame
    //                            arrival inherited chunky-arrival jitter and was
    //                            far worse (21.6%/21.0%, run seq1) -- hence the
    //                            PLL. A stalled stream keeps ticking on the PC
    //                            clock, so the localhost zero policy stays alive.
    //                            NOTE: the control rate becomes fs/N (101.7253
    //                            Hz); fine for probe runs (analysis is per tick),
    //                            but align Ts in mpc_test/fit_sysid/
    //                            export_plant_lti before CLOSED-loop use.
    //   --tick-phase-us X        frame-locked only: shift the (counter-quantized)
    //                            tick grid by X us. check_impulse_delivery.py
    //                            prints the value that centers commands
    //                            mid-latch-period.
    //   --sim-input sine|noise|file:<path>   (run with no PO8e card)
    //   --sim-fs <hz>            emulated acquisition rate (default 610.3516,
    //                            the real NPro1 rate = base 24414.0625 / 40)
    //   --sim-channels <n>       emulated channel count (default = mpc input size)
    //   --sim-sine-hz <hz>       sine test frequency (default 10)
    //   --sim-amp <a>            sim signal amplitude in int16 units (default 1000)
    // =========================================================================
    const char* tdt_host = (argc >= 2) ? argv[1] : "10.1.0.100"; //"TDT_UDP_28_2869";
    const char* matlab_workdir = (argc >= 3) ? argv[2] : "C:/Users/brets/Documents/MATLAB";
    const size_t mpcInputCount = (argc >= 4) ? static_cast<size_t>(std::max(1, std::atoi(argv[3]))) : 16;
    size_t requestedUdpOutputCount = 0;
    size_t ringBufferCapacity = 65536;
    size_t matlabStartDelayTicks = 0;
    size_t maxControlTicks = 0;
    std::string localhostControllerHost = "127.0.0.1";
    uint16_t localhostControllerPort = 31000;
    uint16_t localhostReplyPort = 31001;
    int localhostTimeoutMs = 5;
    bool fastExit = false;
    bool skipUdpSend = false;
    bool validateLogEnabled = false;
    std::string validateLogPath;
    std::string controllerMode = "ramp";
    bool constantOutputEnabled = false;
    float constantOutputValue = 0.0f;
    bool simInputEnabled = false;
    SimSampleSource::Mode simMode = SimSampleSource::SINE;
    std::string simFilePath;
    // Real NPro1 rate: base 24414.0625 / 40. The old 24414 default ran simulation
    // 40x faster than hardware, which is why sim showed a healthy ~250 samples per
    // window while the rig showed 3-5439.
    double simFs = 610.3516;
    int simChannels = 0;            // 0 => default to mpcInputCount below
    double simSineHz = 10.0;
    double simAmplitude = 1000.0;
    // Frames per channel averaged into each feature. 6 = one stim period at
    // 101.7253 Hz against 610.3516 Hz acquisition; multiples of 6 keep the stim
    // artifact contribution constant tick to tick.
    size_t featureWindowSamples = 6;
    // false = rectified mean(|x|) (validated default); true = signed mean(x),
    // the Choi-2016-style signed LFP feature (--feature-signed, 2026-08-20).
    bool featureSigned = false;
    // 0 = wall-clock 10 ms ticks; N>0 = tick every N ingested frames (see docs).
    size_t tickFrames = 0;
    // Frame-locked grid phase trim in us (may be negative). The tick grid is
    // quantized to absolute multiples of the stream counter, and the carrier
    // divides the SAME counter, so the command->latch delay is a fixed,
    // per-session constant. check_impulse_delivery.py measures it and prints
    // the value to pass here to center commands mid-latch-period (max margin
    // against the ~1 ms tick-fire jitter).
    double tickPhaseUs = 0.0;
    for (int i = 1; i < argc; ++i)
    {
        const std::string arg = argv[i];
        if (arg == "--controller" && (i + 1) < argc)
        {
            controllerMode = argv[i + 1];
            ++i;
        }
        else if (arg == "--constant-output" && (i + 1) < argc)
        {
            constantOutputEnabled = true;
            constantOutputValue = (float)std::atof(argv[i + 1]);
            controllerMode = "constant";
            ++i;
        }
        else if (arg == "--validate-log" && (i + 1) < argc)
        {
            validateLogEnabled = true;
            validateLogPath = argv[i + 1];
            ++i;
        }
        else if (arg == "--udp-output-count" && (i + 1) < argc)
        {
            requestedUdpOutputCount = static_cast<size_t>(std::max(1, std::atoi(argv[i + 1])));
            ++i;
        }
        else if (arg == "--feature-window-samples" && (i + 1) < argc)
        {
            featureWindowSamples = static_cast<size_t>(std::max(1, std::atoi(argv[i + 1])));
            ++i;
        }
        else if (arg == "--feature-signed")
        {
            featureSigned = true;
        }
        else if (arg == "--tick-frames" && (i + 1) < argc)
        {
            tickFrames = static_cast<size_t>(std::max(0, std::atoi(argv[i + 1])));
            ++i;
        }
        else if (arg == "--tick-phase-us" && (i + 1) < argc)
        {
            tickPhaseUs = std::atof(argv[i + 1]);
            ++i;
        }
        else if (arg == "--ring-buffer-capacity" && (i + 1) < argc)
        {
            ringBufferCapacity = static_cast<size_t>(std::max(1, std::atoi(argv[i + 1])));
            ++i;
        }
        else if (arg == "--matlab-start-delay-ticks" && (i + 1) < argc)
        {
            matlabStartDelayTicks = static_cast<size_t>(std::max(0, std::atoi(argv[i + 1])));
            ++i;
        }
        else if (arg == "--fast-exit")
        {
            fastExit = true;
        }
        else if (arg == "--skip-udp-send")
        {
            skipUdpSend = true;
        }
        else if (arg == "--max-control-ticks" && (i + 1) < argc)
        {
            maxControlTicks = static_cast<size_t>(std::max(0, std::atoi(argv[i + 1])));
            ++i;
        }
        else if (arg == "--localhost-controller-host" && (i + 1) < argc)
        {
            localhostControllerHost = argv[i + 1];
            ++i;
        }
        else if (arg == "--localhost-controller-port" && (i + 1) < argc)
        {
            localhostControllerPort = (uint16_t)std::max(1, std::atoi(argv[i + 1]));
            ++i;
        }
        else if (arg == "--localhost-reply-port" && (i + 1) < argc)
        {
            localhostReplyPort = (uint16_t)std::max(1, std::atoi(argv[i + 1]));
            ++i;
        }
        else if (arg == "--localhost-timeout-ms" && (i + 1) < argc)
        {
            localhostTimeoutMs = std::max(1, std::atoi(argv[i + 1]));
            ++i;
        }
        else if (arg == "--sim-input" && (i + 1) < argc)
        {
            simInputEnabled = true;
            const std::string spec = argv[i + 1];
            if (spec == "sine")
                simMode = SimSampleSource::SINE;
            else if (spec == "noise")
                simMode = SimSampleSource::NOISE;
            else if (spec.rfind("file:", 0) == 0)
            {
                simMode = SimSampleSource::FILE;
                simFilePath = spec.substr(5);
            }
            else
                std::printf("Unknown --sim-input spec '%s'; defaulting to sine.\n", spec.c_str());
            ++i;
        }
        else if (arg == "--sim-fs" && (i + 1) < argc)
        {
            simFs = std::atof(argv[i + 1]);
            ++i;
        }
        else if (arg == "--sim-channels" && (i + 1) < argc)
        {
            simChannels = std::max(1, std::atoi(argv[i + 1]));
            ++i;
        }
        else if (arg == "--sim-sine-hz" && (i + 1) < argc)
        {
            simSineHz = std::atof(argv[i + 1]);
            ++i;
        }
        else if (arg == "--sim-amp" && (i + 1) < argc)
        {
            simAmplitude = std::atof(argv[i + 1]);
            ++i;
        }
    }

    matlab::engine::MATLABEngine* engRaw = nullptr;
    PO8e* card = nullptr;
    std::unique_ptr<ISampleSource> source;
    SOCKET rzSock = INVALID_SOCKET;
    // Mirrors udpOutputCount (which is scoped inside the try) so the cleanup
    // paths know how many words to zero.
    size_t activeUdpOutputCount = 0;
    SOCKET localhostControllerSock = INVALID_SOCKET;
    bool udpReady = false;
        std::ofstream validateLog;
        std::vector<double> postSetupCachedU;
        std::vector<float> postSetupCachedAmps;
        std::vector<double> localhostLastOutput;
        uint32_t localhostSequence = 1;
        uint32_t localhostLastSeenReplySeq = 0;
        bool localhostRequestInFlight = false;
        uint32_t localhostInFlightSequence = 0;
        int64_t localhostInFlightSentUs = 0;
        int64_t localhostLatestReplyUs = 0;
        std::string localhostLastError;
    bool useFastExitShutdown = false;

    std::unique_ptr<matlab::engine::MATLABEngine> eng;

    try
    {
        // =====================================================================
        // SECTION 4: Start MATLAB Engine and set working folder for mpc_step.m
        // ---------------------------------------------------------------------
        // In constant-output mode we skip MATLAB entirely so we can isolate
        // native-library failures from the control/transport path.
        // =====================================================================
        std::u16string matlabControllerName = u"mpc_step";
        const bool useMpcTestController =
            (controllerMode == "mpc_test" || controllerMode == "mpc_test_cached");
        const bool useMpcTestCachedMode = (controllerMode == "mpc_test_cached");
        const bool useLocalhostController =
            (controllerMode == "localhost" || controllerMode == "localhost_constant");
        useFastExitShutdown = (fastExit || useMpcTestController);
        if (useMpcTestController)
            matlabControllerName = u"mpc_test";
        else if (controllerMode != "ramp" && controllerMode != "constant" && !useLocalhostController)
            throw std::runtime_error("Unknown controller mode. Use constant, ramp, mpc_test, mpc_test_cached, localhost, or localhost_constant.");

        if (controllerMode != "constant" && !useLocalhostController)
        {
            eng = matlab::engine::startMATLAB();
            engRaw = eng.get();
            eng->eval(u"warning('off','all')");
            {
                std::u16string cdCmd = u"cd('";
                for (const char* p = matlab_workdir; *p; ++p)
                    cdCmd.push_back(static_cast<char16_t>(*p));
                cdCmd += u"')";
                eng->eval(cdCmd);
            }
            std::cout << "MATLAB started. controller=" << controllerMode
                      << " path=" << matlab_workdir << "\n";

            const size_t warmupOutputCount = (requestedUdpOutputCount > 0)
                ? requestedUdpOutputCount
                : std::max<size_t>(mpcInputCount, 1);
            const std::vector<double> warmupX =
                build_constant_input(std::max(mpcInputCount, warmupOutputCount), 123.0);
            std::printf("MATLAB warmup: calling controller with %zu-element input...\n", warmupX.size());
            const std::vector<double> warmupRawU =
                call_matlab_controller(*engRaw, matlabControllerName, warmupX);
            const std::vector<double> warmupU =
                normalize_controller_output(warmupRawU, warmupOutputCount);
            const double warmupRaw0 = warmupRawU.empty() ? 0.0 : warmupRawU[0];
            const double warmupU0 = warmupU.empty() ? 0.0 : warmupU[0];
            std::printf("MATLAB warmup result: raw=%zu normalized=%zu raw0=%.6f out0=%.6f\n",
                        warmupRawU.size(), warmupU.size(), warmupRaw0, warmupU0);

            const std::vector<double> warmupRawU2 =
                call_matlab_controller(*engRaw, matlabControllerName, warmupX);
            const std::vector<double> warmupU2 =
                normalize_controller_output(warmupRawU2, warmupOutputCount);
            const double warmupRaw02 = warmupRawU2.empty() ? 0.0 : warmupRawU2[0];
            const double warmupU02 = warmupU2.empty() ? 0.0 : warmupU2[0];
            std::printf("MATLAB warmup result 2: raw=%zu normalized=%zu raw0=%.6f out0=%.6f\n",
                        warmupRawU2.size(), warmupU2.size(), warmupRaw02, warmupU02);

            if (useMpcTestController)
            {
                eng->eval(u"mpc_test([]);");
                std::printf("MATLAB controller state reset after warmup probes.\n");
            }
        }
        else if (useLocalhostController)
        {
            std::printf("Localhost controller mode enabled: host=%s controllerPort=%u replyPort=%u timeoutMs=%d\n",
                        localhostControllerHost.c_str(),
                        (unsigned)localhostControllerPort,
                        (unsigned)localhostReplyPort,
                        localhostTimeoutMs);
        }
        else
        {
            std::printf("Constant-output mode enabled: skipping MATLAB, value=%g\n",
                        (double)constantOutputValue);
        }

        // =====================================================================
        // SECTION 5: Open acquisition stream (live PO8e card or --sim-input)
        // =====================================================================
        if (simInputEnabled)
        {
            const int simCh = (simChannels > 0) ? simChannels : (int)mpcInputCount;
            std::printf("Sim input enabled: bypassing PO8e card.\n");
            source.reset(new SimSampleSource(simCh, simFs, simMode, simFilePath,
                                             simSineHz, simAmplitude));
        }
        else
        {
            int total = PO8e::cardCount();
            std::printf("Found %d card(s) in the system.\n", total);
            if (total <= 0) return 0;

            std::printf("Connecting to card 0...\n");
            card = PO8e::connectToCard(0);
            if (!card)
            {
                std::printf("Connection failed.\n");
                return 1;
            }
            std::printf("Connected: %p\n", (void*)card);
            source.reset(new Po8eSampleSource(card));
        }

        if (!source->startCollecting())
        {
            std::printf("startCollecting() failed with: %d\n", source->getLastError());
            return 1;
        }
        std::printf("Source is collecting (%s).\n", source->name());

        std::printf("Waiting for stream...\n");
        while (source->samplesReady(nullptr) == 0)
            compatUSleep(5000);

        const int nCh = source->numChannels();
        // Bytes per sample is set by the Synapse gizmo, NOT by this code: 2 = int16,
        // 4 = float32. Sizing the read buffer for int16 while the card streams
        // float32 overruns the heap by nCh*2 bytes on EVERY readBlock -- that was
        // the 2026-08-14/15 crash (0xc0000374, caught in PO8eStreaming.dll by
        // PageHeap), and the misread bytes also made every feature garbage.
        const int sampleBytes = source->sampleSizeBytes();
        std::printf("Streaming. numChannels=%d sampleBytes=%d (%s)\n",
                    nCh, sampleBytes,
                    sampleBytes == 4 ? "float32" : (sampleBytes == 2 ? "int16" : "UNRECOGNIZED"));
        if (sampleBytes != 2 && sampleBytes != 4)
        {
            std::printf("FATAL: unsupported stream sample size %d bytes -- check the Synapse "
                        "gizmo data format (expected int16 or float32).\n", sampleBytes);
            return 1;
        }
        // The RZ2 UDP receive gizmo reads 8 float words -- one per BIPOLAR STIM PAIR
        // (sSig[2k] = -sSig[2k-1], verified exact on 2026-08-12). Defaulting to the
        // live stream width would silently send 32 words once the 32-channel
        // recording is in use, and everything past word 8 is discarded with no
        // error anywhere. 8 is the real actuator count, not a truncation.
        static const size_t DEFAULT_UDP_OUTPUT_COUNT = 8;
        const size_t udpOutputCount = (requestedUdpOutputCount > 0)
            ? requestedUdpOutputCount
            : DEFAULT_UDP_OUTPUT_COUNT;
        activeUdpOutputCount = udpOutputCount;
        std::printf("Output channels per UDP packet=%zu (bipolar stim pairs)\n", udpOutputCount);
        std::printf("Feature window=%zu samples/channel (fixed count, not arrival time), mode=%s\n",
                    featureWindowSamples,
                    featureSigned ? "SIGNED mean(x) [Choi-style LFP]" : "rectified mean(|x|)");

        // =====================================================================
        // SECTION 6: Open UDP path to RZ and register local sender IP
        // ---------------------------------------------------------------------
        // setRemoteIp() tells the RZ to send/accept traffic to/from this host.
        // =====================================================================
        if (!udp_init())
        {
            std::printf("UDP init failed.\n");
            return 1;
        }
        udpReady = true;

        if (useLocalhostController)
        {
            localhostControllerSock = open_localhost_controller_socket(localhostControllerHost.c_str(),
                                                                       localhostControllerPort,
                                                                       localhostReplyPort,
                                                                       localhostTimeoutMs);
            if (localhostControllerSock == INVALID_SOCKET)
            {
                std::printf("Failed to open localhost controller socket to %s:%u (reply port %u).\n",
                            localhostControllerHost.c_str(),
                            (unsigned)localhostControllerPort,
                            (unsigned)localhostReplyPort);
                return 1;
            }
            localhostLastOutput.assign(udpOutputCount, 0.0);
            set_socket_nonblocking(localhostControllerSock, true);
            std::printf("Localhost controller socket ready: %s:%u -> local port %u\n",
                        localhostControllerHost.c_str(),
                        (unsigned)localhostControllerPort,
                        (unsigned)localhostReplyPort);
            std::printf("Localhost controller mode: single-thread async poll with one in-flight request\n");
        }

        const uint32_t rzIp = resolve_ipv4_addr(tdt_host);
        if (rzIp == INADDR_NONE)
        {
            std::printf("Failed to resolve IPv4 target '%s'\n", tdt_host);
            return 1;
        }
        rzSock = openSocket(rzIp);
        if (rzSock == INVALID_SOCKET)
        {
            std::printf("Failed to open UDP socket to RZ target '%s'.\n", tdt_host);
            return 1;
        }
        std::printf("UDP socket connected to RZ target: %s:%u\n", tdt_host, (unsigned)LISTEN_PORT);
        arm_emergency_zero(rzSock, activeUdpOutputCount);

        // Handshake check. checkRZ() does a blocking recv() with no timeout, which
        // is why this was commented out since the first commit. The cost was that
        // production had zero confirmation anything was listening: openSocket() uses
        // connect()+send() with no bind, so send() returns the full byte count even
        // when the destination does not exist. That is exactly how the 2026-08-09
        // network fault stayed silent. A 1 s SO_RCVTIMEO makes the check safe --
        // it warns and continues instead of hanging.
        //
        // Only checkRZ() receives on this socket (setRemoteIp/disconnectRZ are
        // send-only), so the timeout affects nothing else.
        {
            DWORD rzRecvTimeoutMs = 1000;
            setsockopt(rzSock, SOL_SOCKET, SO_RCVTIMEO,
                       (const char*)&rzRecvTimeoutMs, sizeof rzRecvTimeoutMs);
            if (checkRZ(rzSock))
                std::printf("checkRZ: RZ2 ACK received.\n");
            else
                std::printf("WARNING: RZ2 did not ACK GET_VERSION - nothing may be receiving.\n");
        }

        if (!setRemoteIp(rzSock))
            std::printf("Warning: SET_REMOTE_IP failed.\n");
        else
            std::printf("Sent SET_REMOTE_IP command.\n");

        if (validateLogEnabled)
        {
            validateLog.open(validateLogPath.c_str(), std::ios::out | std::ios::trunc);
            if (!validateLog.is_open())
            {
                std::printf("Failed to open validate log file: %s\n", validateLogPath.c_str());
                return 1;
            }
            validateLog << "packet,offset,input0,u0,amp0,t_in_us,t_mpc_done_us,t_udp_send_us,mpc_ms,in_to_udp_ms\n";
            std::printf("Validation logging enabled: %s\n", validateLogPath.c_str());
        }

        if (controllerMode != "constant" && !useLocalhostController)
        {
            const std::vector<double> postSetupX =
                build_constant_input(std::max(mpcInputCount, udpOutputCount), 123.0);
            std::printf("MATLAB post-setup probe: calling controller with %zu-element input...\n", postSetupX.size());
            const std::vector<double> postSetupRawU =
                call_matlab_controller(*engRaw, matlabControllerName, postSetupX);
            const std::vector<double> postSetupU =
                normalize_controller_output(postSetupRawU, udpOutputCount);
            postSetupCachedU = postSetupU;
            postSetupCachedAmps =
                clamp_amplitudes_f32_from_cached(postSetupCachedU, udpOutputCount, 0.0f, 100000.0f);
            const double postSetupRaw0 = postSetupRawU.empty() ? 0.0 : postSetupRawU[0];
            const double postSetupU0 = postSetupU.empty() ? 0.0 : postSetupU[0];
            std::printf("MATLAB post-setup result: raw=%zu normalized=%zu raw0=%.6f out0=%.6f\n",
                        postSetupRawU.size(), postSetupU.size(), postSetupRaw0, postSetupU0);
        }

        // =====================================================================
        // SECTION 7: Continuous acquisition + 100 Hz control loop
        // ---------------------------------------------------------------------
        // PO8e acquisition runs continuously and appends each sample frame into
        // a per-channel ring buffer. Every 10 ms, the controller:
        // 1) preprocesses the most recent featureWindowSamples frames into one
        //    scalar per input channel (mean absolute value placeholder).
        //    NOTE: a fixed SAMPLE COUNT, not a time window -- PO8e delivery is
        //    bursty, so an arrival-time window spanned 3-5439 samples on hardware.
        // 2) calls MATLAB mpc_step() once
        // 3) sends one UDP packet containing the output vector
        // =====================================================================
        static const int64_t CONTROL_INTERVAL_US = 10000;
        static const int POLL_SLEEP_US = 1000;
        // Frame-locked (PLL) mode: ticks fire on the smooth PC clock, but the
        // period and phase are steered toward the PO8e frame-counter grid (the
        // RZ2 crystal). Firing directly on frame ARRIVAL was tried 2026-08-18
        // and failed on hardware: frames arrive in irregular chunks, so tick
        // times inherited +/-2.5 ms arrival jitter and probe windows spanned
        // 0..2 carrier latches (21.6% missed / 21.0% doubled pulses, run seq1).
        // Low-gain feedback averages the chunky arrivals out: tick-to-tick
        // spacing stays ~= one carrier period while long-term phase tracks the
        // stream. A stalled stream keeps ticking on the PC clock (PLL simply
        // stops updating), so the localhost zero policy stays alive with no
        // separate watchdog.
        const double streamFsNominal = simInputEnabled ? simFs : 610.3515625;
        const double tickPeriodNomUs = (tickFrames > 0)
            ? 1e6 * (double)tickFrames / streamFsNominal
            : (double)CONTROL_INTERVAL_US;
        double tickPeriodUsF = tickPeriodNomUs;      // PLL frequency state
        double pllBasePos = 0.0;                     // stream pos of the grid origin
        uint64_t pllTicksSinceBase = 0;
        bool pllLocked = false;
        uint64_t pllResyncs = 0;
        double pllAbsErrSumUs = 0.0, pllAbsErrMaxUs = 0.0;
        uint64_t pllErrSamples = 0;
        int64_t lastFrameArrivalUs = 0;
        static const double PLL_PHASE_GAIN = 0.05;    // fraction of phase error per tick
        static const double PLL_PHASE_SLEW_US = 250.0; // max per-tick timing nudge
        static const double PLL_FREQ_GAIN = 0.0015;   // period trim per tick
        static const double PLL_FREQ_SLEW_US = 3.0;
        int64_t pos = 0;
        int64_t prevOffset = -1;
        int64_t expectedStep = 0;
        uint64_t sentPackets = 0;
        uint64_t controlTicks = 0;
        uint64_t undersampledWindows = 0;
        uint64_t droppedControlTicks = 0;
        uint64_t localhostRequests = 0;
        uint64_t localhostReplySuccesses = 0;
        uint64_t localhostReplyTimeouts = 0;
        uint64_t localhostReplyStaleDropped = 0;
        uint64_t localhostReplyPreSendDrained = 0;
        size_t minWindowSamplesSeen = (size_t)-1;
        size_t nominalWindowSamples = 0;
        TimingStats preprocessTiming;
        TimingStats controllerTiming;
        TimingStats normalizeClampTiming;
        TimingStats udpSendTiming;
        TimingStats totalTickTiming;
        TimingStats localhostOutputAgeTiming;
        static const uint64_t LIVE_CONTROLLER_WARMUP_TICKS = 5;
        static const uint64_t VERBOSE_CONTROL_TICKS = 2;
        static const int64_t LOCALHOST_FRESH_OUTPUT_US = 100000;
        static const int64_t LOCALHOST_MAX_HOLD_OUTPUT_US = 250000;
        uint64_t localhostTicksUsingFreshOutput = 0;
        uint64_t localhostTicksUsingHeldOutput = 0;
        uint64_t localhostTicksUsingZeroOutput = 0;
        uint64_t localhostFreshReplyTransitions = 0;
        uint64_t localhostPolicyTransitions = 0;
        int localhostOutputPolicy = -1;
        bool printedControllerShape = false;
        bool printedCachedPhaseStart = false;
        bool printedLiveFevalStart = false;
        bool ranPreTransitionWarmFeval = false;
        bool printedTick1BeforeSend = false;
        bool printedTick1AfterSend = false;
        const uint64_t printEveryPackets = 25;
        HiResClock clock;
        bool stopped = false;
        // Raw frame buffer sized per the PO8e contract: numChannels * dataSampleSize
        // bytes per frame (PO8e.h readBlock docs). Decoded into floats before the ring.
        std::vector<uint8_t> rawFrame((size_t)std::max(nCh, 1) * (size_t)sampleBytes);
        std::vector<float> frame((size_t)std::max(nCh, 1), 0.0f);
        const auto decodeFrame = [&]() {
            if (sampleBytes == 4)
            {
                std::memcpy(frame.data(), rawFrame.data(), frame.size() * sizeof(float));
            }
            else
            {
                const int16_t* s = reinterpret_cast<const int16_t*>(rawFrame.data());
                for (size_t ch = 0; ch < frame.size(); ++ch)
                    frame[ch] = (float)s[ch];
            }
        };
        SampleRingBuffer ring;
        ring.initialize((size_t)std::max(nCh, 1), ringBufferCapacity);
        uint64_t backlogFramesDropped = 0;

        // Discard whatever accumulated before the loop started.
        //
        // The PO8e streams continuously from the moment Synapse begins, so by the
        // time the operator confirms 'go' the card can hold tens of seconds of
        // history. On 2026-08-14 that was 22,249 frames (36.5 s). Draining it one
        // frame per readBlock() call cannot outrun live data still arriving, so the
        // card's buffer overran, the offset counter jumped 12,712 frames, and the
        // run died ~36 control ticks in.
        //
        // Nothing wants that history: the feature is the newest featureWindowSamples
        // frames, so old data is pure latency.
        {
            bool preStopped = false;
            const size_t backlog = source->samplesReady(&preStopped);
            if (backlog > 0)
            {
                source->flushBufferedData((int)backlog);
                backlogFramesDropped += backlog;
                std::printf("Discarded %zu frame(s) buffered before loop start "
                            "(stale history; the feature only uses the newest %zu).\n",
                            backlog, featureWindowSamples);
            }
        }

        int64_t nextControlUs = clock.now_us() + (int64_t)(tickPeriodUsF + 0.5);

        if (controllerMode == "mpc_test" && matlabStartDelayTicks > 0)
        {
            compatUSleep(20000);
            size_t preloadSamples = source->samplesReady(&stopped);
            const size_t preloadToRead = std::min<size_t>(preloadSamples, 64);
            for (size_t i = 0; i < preloadToRead && !stopped; ++i)
            {
                int64_t offsets[1];
                const size_t got = source->readBlock(rawFrame.data(), 1, offsets);
                if (got != 1)
                    break;
                decodeFrame();
                ring.pushFrame(frame, clock.now_us());
                source->flushBufferedData(1);
            }

            size_t preLoopWindowSamples = 0;
            const std::vector<double> preLoopFeatures =
                ring.computeMeanAbsSamples(mpcInputCount, featureWindowSamples, &preLoopWindowSamples,
                                           featureSigned);
            std::vector<double> preLoopX =
                build_mpc_input(preLoopFeatures, mpcInputCount, udpOutputCount);
            std::printf("Pre-loop live probe: buffered=%zu windowSamples=%zu feature0=%.6f\n",
                        ring.size,
                        preLoopWindowSamples,
                        preLoopFeatures.empty() ? 0.0 : preLoopFeatures[0]);
            const std::vector<double> preLoopRawU =
                call_matlab_controller(*engRaw, matlabControllerName, preLoopX);
            std::printf("Pre-loop live probe result: rawCount=%zu raw0=%.6f\n",
                        preLoopRawU.size(),
                        preLoopRawU.empty() ? 0.0 : preLoopRawU[0]);
            eng->eval(u"mpc_test([]);");
            std::printf("MATLAB controller state reset after pre-loop live probe.\n");
        }

        if (tickFrames > 0)
        {
            const double streamFs = simInputEnabled ? simFs : 610.3516;
            std::printf("Entering loop (MPC input size=%zu, UDP output count=%zu, control=FRAME-LOCKED %zu frames/tick (~%.4f Hz on the stream clock), ring capacity=%zu, matlabDelayTicks=%zu, maxControlTicks=%zu).\n",
                        mpcInputCount, udpOutputCount, tickFrames, streamFs / (double)tickFrames,
                        ringBufferCapacity, matlabStartDelayTicks, maxControlTicks);
        }
        else
        {
            std::printf("Entering loop (MPC input size=%zu, UDP output count=%zu, control=100 Hz, ring capacity=%zu, matlabDelayTicks=%zu, maxControlTicks=%zu).\n",
                        mpcInputCount, udpOutputCount, ringBufferCapacity, matlabStartDelayTicks, maxControlTicks);
        }

        while (!stopped)
        {
            // Poll buffered sample count directly. In practice this is more stable
            // than repeatedly calling the vendor semaphore wait with very short
            // timeouts inside the 100 Hz scheduler.
            size_t numSamples = source->samplesReady(&stopped);
            if (stopped)
            {
                std::printf("\nExit reason: PO8e stream reported stopped.\n");
                break;
            }

            if (numSamples == 0)
                compatUSleep(POLL_SLEEP_US);

            // Bounded ingest. If we ever fall behind, catch up by DISCARDING the
            // oldest frames instead of walking through them one vendor call at a
            // time -- that is precisely how the card was allowed to overrun. Frames
            // dropped here are counted and reported at exit; an overrun is silent,
            // unbounded, and corrupts the offset counter.
            static const size_t kMaxIngestPerPass = 4096;
            if (numSamples > kMaxIngestPerPass)
            {
                const size_t drop = numSamples - kMaxIngestPerPass;
                source->flushBufferedData((int)drop);
                backlogFramesDropped += drop;
                numSamples = kMaxIngestPerPass;
            }

            for (size_t i = 0; i < numSamples; ++i)
            {
                int64_t offsets[1];
                const size_t got = source->readBlock(rawFrame.data(), 1, offsets);
                if (got != 1)
                {
                    std::printf("readBlock failed.\n");
                    stopped = true;
                    std::printf("\nExit reason: readBlock() failed.\n");
                    break;
                }

                const int64_t offset = offsets[0];
                if (prevOffset < 0)
                {
                    // First sample establishes the stream position.
                    pos = offset;
                    prevOffset = offset;
                }
                else
                {
                    const int64_t step = offset - prevOffset;
                    if (expectedStep == 0 && step > 0)
                    {
                        // Learn the normal stride from the first valid delta.
                        expectedStep = step;
                        std::printf("\nDetected PO8e offset step=%lld\n", (long long)expectedStep);
                    }
                    else if (expectedStep > 0 && step > expectedStep)
                    {
                        // Only report when we exceed the learned stride.
                        std::printf("\nSkipping %lld to position %lld\n",
                                    (long long)(step - expectedStep),
                                    (long long)offset);
                    }
                    prevOffset = offset;
                    pos = offset;
                }

                const int64_t sampleTimeUs = clock.now_us();
                decodeFrame();
                ring.pushFrame(frame, sampleTimeUs);
                lastFrameArrivalUs = sampleTimeUs;   // PLL phase-detector input

                source->flushBufferedData(1);
            }

            // Tick scheduling. Both modes fire on the PC clock deadline; in
            // frame-locked mode the deadline is steered by the PLL (below) so
            // the tick grid tracks the RZ2 frame counter with smooth timing.
            int64_t nowUs = clock.now_us();
            if (nowUs >= nextControlUs)
            {
                const uint64_t tickIndex = controlTicks + 1;
                if (tickIndex <= VERBOSE_CONTROL_TICKS)
                {
                    std::printf("Tick trace: begin controlTick=%llu packet=%llu buffered=%zu\n",
                                (unsigned long long)tickIndex,
                                (unsigned long long)sentPackets,
                                ring.size);
                }
                const int64_t t_in_us = clock.now_us();
                size_t windowSamplesSeen = 0;
                const std::vector<double> features =
                    ring.computeMeanAbsSamples(mpcInputCount, featureWindowSamples, &windowSamplesSeen,
                                               featureSigned);
                const int64_t t_features_done_us = clock.now_us();
                if (tickIndex <= VERBOSE_CONTROL_TICKS)
                {
                    const double feature0 = features.empty() ? 0.0 : features[0];
                    std::printf("Tick trace: features controlTick=%llu windowSamples=%zu feature0=%.6f\n",
                                (unsigned long long)tickIndex,
                                windowSamplesSeen,
                                feature0);
                }
                std::vector<double> x = build_mpc_input(features, mpcInputCount, udpOutputCount);
                const bool useFixedControllerInput =
                    (controllerMode == "mpc_test" && controlTicks < LIVE_CONTROLLER_WARMUP_TICKS);
                if (useFixedControllerInput)
                    x = build_constant_input(std::max(mpcInputCount, udpOutputCount), 123.0);
                if (tickIndex <= VERBOSE_CONTROL_TICKS)
                {
                    const double x0 = x.empty() ? 0.0 : x[0];
                    std::printf("Tick trace: input controlTick=%llu inputMode=%s x0=%.6f\n",
                                (unsigned long long)tickIndex,
                                useFixedControllerInput ? "fixed123" : "live",
                                x0);
                }
                std::vector<double> rawU;
                const std::vector<double>* rawUView = NULL;
                bool usedPostSetupCache = false;
                const bool useDelayedMatlabCache =
                    (controllerMode == "mpc_test" &&
                     controlTicks < matlabStartDelayTicks &&
                     !postSetupCachedU.empty() &&
                     !postSetupCachedAmps.empty());
                if (controllerMode == "constant")
                {
                    rawU.assign(1, (double)constantOutputValue);
                    rawUView = &rawU;
                }
                else if (useLocalhostController)
                {
                    // Localhost mode is intentionally single-threaded here:
                    // 1) poll once for the currently in-flight reply
                    // 2) mark it complete or timed out
                    // 3) send a new request only if no older request is outstanding
                    //
                    // This keeps the 100 Hz scheduler nonblocking without needing
                    // a worker thread or a queue of stale controller jobs.
                    uint32_t submittedSeq = 0;
                    std::vector<double> localhostReplyRaw;
                    LocalhostRequestDiagnostics localhostDiag {};
                    std::string localhostReplyError;
                    bool gotReply = false;
                    if (localhostRequestInFlight)
                    {
                        gotReply = try_recv_localhost_controller_reply(localhostControllerSock,
                                                                      localhostInFlightSequence,
                                                                      &localhostReplyRaw,
                                                                      &localhostDiag,
                                                                      &localhostReplyError);
                        localhostReplyStaleDropped += (uint64_t)std::max(localhostDiag.staleReplies, 0);
                        if (gotReply)
                        {
                            localhostRequestInFlight = false;
                            localhostLastOutput = normalize_controller_output(localhostReplyRaw, udpOutputCount);
                            localhostLatestReplyUs = t_in_us;
                            localhostLastSeenReplySeq = localhostInFlightSequence;
                            ++localhostReplySuccesses;
                            ++localhostFreshReplyTransitions;
                            controllerTiming.add(t_in_us - localhostInFlightSentUs);
                            localhostLastError.clear();
                        }
                        else if (!localhostReplyError.empty())
                        {
                            localhostLastError = localhostReplyError;
                        }
                        else if ((t_in_us - localhostInFlightSentUs) > (int64_t)localhostTimeoutMs * 1000)
                        {
                            localhostRequestInFlight = false;
                            ++localhostReplyTimeouts;
                            localhostLastError = "timeout waiting for localhost controller reply";
                        }
                    }

                    if (!localhostRequestInFlight)
                    {
                        std::string localhostSendError;
                        submittedSeq = localhostSequence++;
                        if (send_localhost_controller_request(localhostControllerSock,
                                                              submittedSeq,
                                                              x,
                                                              &localhostSendError))
                        {
                            localhostRequestInFlight = true;
                            localhostInFlightSequence = submittedSeq;
                            localhostInFlightSentUs = t_in_us;
                            ++localhostRequests;
                        }
                        else
                        {
                            localhostLastError = localhostSendError;
                        }
                    }
                    else
                    {
                        ++localhostReplyPreSendDrained;
                    }

                    const bool localhostHasValidOutput = !localhostLastOutput.empty() && localhostLastSeenReplySeq != 0;
                    const uint32_t localhostLatestReplySeq = localhostLastSeenReplySeq;
                    const uint64_t localhostOverwrittenRequests = localhostReplyPreSendDrained;
                    int64_t localhostOutputAgeUs = -1;
                    const char* localhostPolicyName = "zero";
                    const char* localhostPolicyReason = "no reply yet";
                    int localhostCurrentPolicy = 0;

                    if (localhostHasValidOutput && localhostLatestReplyUs > 0)
                        localhostOutputAgeUs = t_in_us - localhostLatestReplyUs;

                    if (localhostHasValidOutput &&
                        localhostOutputAgeUs >= 0 &&
                        localhostOutputAgeUs <= LOCALHOST_FRESH_OUTPUT_US)
                    {
                        // Fresh output: use the newest reply directly.
                        rawU = localhostLastOutput;
                        localhostCurrentPolicy = 2;
                        localhostPolicyName = "fresh";
                        localhostPolicyReason = "reply age within fresh threshold";
                        ++localhostTicksUsingFreshOutput;
                        localhostOutputAgeTiming.add(localhostOutputAgeUs);
                    }
                    else if (localhostHasValidOutput &&
                             localhostOutputAgeUs >= 0 &&
                             localhostOutputAgeUs <= LOCALHOST_MAX_HOLD_OUTPUT_US)
                    {
                        // Held output: the controller is alive, but its newest reply is
                        // older than our "fresh" threshold, so we keep using it briefly.
                        rawU = localhostLastOutput;
                        localhostCurrentPolicy = 1;
                        localhostPolicyName = "hold-last";
                        localhostPolicyReason = "reply age within hold threshold";
                        ++localhostTicksUsingHeldOutput;
                        localhostOutputAgeTiming.add(localhostOutputAgeUs);
                    }
                    else
                    {
                        // Zero fail-safe: no valid reply has arrived yet, or the newest
                        // reply is too old to trust for stimulation output.
                        rawU.assign(udpOutputCount, 0.0);
                        localhostCurrentPolicy = 0;
                        localhostPolicyName = "zero";
                        localhostPolicyReason = localhostHasValidOutput
                            ? "reply too old"
                            : "no valid reply yet";
                        ++localhostTicksUsingZeroOutput;
                    }
                    rawUView = &rawU;

                    if (localhostCurrentPolicy != localhostOutputPolicy)
                    {
                        ++localhostPolicyTransitions;
                        localhostOutputPolicy = localhostCurrentPolicy;
                        const double replyAgeMs = (localhostOutputAgeUs >= 0)
                            ? (double)localhostOutputAgeUs / 1000.0
                            : -1.0;
                        const char* policyReason = localhostPolicyReason;
                        if (localhostCurrentPolicy == 0 && !localhostLastError.empty())
                            policyReason = localhostLastError.c_str();
                        std::printf("Localhost output policy: controlTick=%llu policy=%s latestReplySeq=%u ageMs=%.3f reason=%s overwritten=%llu\n",
                                    (unsigned long long)tickIndex,
                                    localhostPolicyName,
                                    (unsigned)localhostLatestReplySeq,
                                    replyAgeMs,
                                    policyReason,
                                    (unsigned long long)localhostOverwrittenRequests);
                    }
                    else if (tickIndex <= VERBOSE_CONTROL_TICKS)
                    {
                        const double replyAgeMs = (localhostOutputAgeUs >= 0)
                            ? (double)localhostOutputAgeUs / 1000.0
                            : -1.0;
                        std::printf("Localhost async: controlTick=%llu submittedSeq=%u latestReplySeq=%u policy=%s ageMs=%.3f overwritten=%llu\n",
                                    (unsigned long long)tickIndex,
                                    (unsigned)submittedSeq,
                                    (unsigned)localhostLatestReplySeq,
                                    localhostPolicyName,
                                    replyAgeMs,
                                    (unsigned long long)localhostOverwrittenRequests);
                    }
                }
                else if ((useMpcTestCachedMode && !postSetupCachedU.empty() && !postSetupCachedAmps.empty()) || useDelayedMatlabCache)
                {
                    usedPostSetupCache = true;
                    rawUView = &postSetupCachedU;
                }
                else
                {
                    const bool isFirstDelayedLiveFeval =
                        (controllerMode == "mpc_test" &&
                         matlabStartDelayTicks > 0 &&
                         !printedLiveFevalStart);
                    if (controllerMode == "mpc_test" && matlabStartDelayTicks > 0 && !printedLiveFevalStart)
                    {
                        std::printf("Controller transition: entering live MATLAB feval at controlTick=%llu packet=%llu\n",
                                    (unsigned long long)controlTicks,
                                    (unsigned long long)sentPackets);
                        printedLiveFevalStart = true;
                    }
                    if (isFirstDelayedLiveFeval && !ranPreTransitionWarmFeval)
                    {
                        std::printf("Controller transition: pre-warm MATLAB feval at controlTick=%llu packet=%llu\n",
                                    (unsigned long long)controlTicks,
                                    (unsigned long long)sentPackets);
                        const std::vector<double> warmRawU =
                            call_matlab_controller(*engRaw, matlabControllerName, x);
                        const double warmRaw0 = warmRawU.empty() ? 0.0 : warmRawU[0];
                        std::printf("Controller transition: pre-warm result rawCount=%zu raw0=%.6f\n",
                                    warmRawU.size(), warmRaw0);
                        ranPreTransitionWarmFeval = true;
                    }
                    rawU = call_matlab_controller(*engRaw, matlabControllerName, x);
                    rawUView = &rawU;
                }
                if (tickIndex <= VERBOSE_CONTROL_TICKS)
                {
                    const double raw0 = (!rawUView || rawUView->empty()) ? 0.0 : (*rawUView)[0];
                    const char* traceSource =
                        (useLocalhostController) ? "localhost" :
                        (usedPostSetupCache ? "postSetupCache" : "feval");
                    std::printf("Tick trace: controller controlTick=%llu source=%s rawCount=%zu raw0=%.6f\n",
                                (unsigned long long)tickIndex,
                                traceSource,
                                rawUView ? rawUView->size() : 0,
                                raw0);
                }
                const bool useCachedFastPath = usedPostSetupCache;
                std::vector<double> u;
                if (!useCachedFastPath)
                    u = normalize_controller_output(rawU, udpOutputCount);
                const int64_t t_mpc_done_us = clock.now_us();
                preprocessTiming.add(t_features_done_us - t_in_us);
                if (!useLocalhostController)
                    controllerTiming.add(t_mpc_done_us - t_features_done_us);
                const std::vector<float> amps = useCachedFastPath
                    ? postSetupCachedAmps
                    : clamp_amplitudes_f32(u, 0.0f, 100000.0f);
                const int64_t t_normalize_done_us = clock.now_us();
                normalizeClampTiming.add(t_normalize_done_us - t_mpc_done_us);
                if (tickIndex <= VERBOSE_CONTROL_TICKS)
                {
                    const double u0 = useCachedFastPath
                        ? ((!rawUView || rawUView->empty()) ? 0.0 : (*rawUView)[0])
                        : (u.empty() ? 0.0 : u[0]);
                    const double amp0 = amps.empty() ? 0.0 : amps[0];
                    std::printf("Tick trace: normalized controlTick=%llu path=%s u0=%.6f amp0=%.6f\n",
                                (unsigned long long)tickIndex,
                                useCachedFastPath ? "cachedFastPath" : "normal",
                                u0,
                                amp0);
                }
                if (usedPostSetupCache && !printedCachedPhaseStart)
                {
                    std::printf("Controller phase: cached output active at controlTick=%llu packet=%llu delayTicks=%zu\n",
                                (unsigned long long)controlTicks,
                                (unsigned long long)sentPackets,
                                matlabStartDelayTicks);
                    printedCachedPhaseStart = true;
                }
                if (!printedControllerShape)
                {
                    const double raw0 = (!rawUView || rawUView->empty()) ? 0.0 : (*rawUView)[0];
                    const double out0 = useCachedFastPath
                        ? ((!rawUView || rawUView->empty()) ? 0.0 : (*rawUView)[0])
                        : (u.empty() ? 0.0 : u[0]);
                    const char* inputMode = useFixedControllerInput ? "fixed123" : "live";
                    const char* sourceMode =
                        (useLocalhostController) ? "localhost" :
                        (usedPostSetupCache ? "postSetupCache" : "feval");
                    std::printf("Controller output shape: raw=%zu normalized=%zu raw0=%.6f out0=%.6f inputMode=%s source=%s\n",
                                rawUView ? rawUView->size() : 0, amps.size(), raw0, out0,
                                inputMode, sourceMode);
                    printedControllerShape = true;
                }
                ++controlTicks;
                minWindowSamplesSeen = std::min(minWindowSamplesSeen, windowSamplesSeen);
                // "Nominal" is now the REQUESTED count rather than a running max.
                // The old running-max form reported 299/300 windows undersampled
                // even in simulation, because the first tick set the high-water
                // mark and nothing afterwards could match it -- a false alarm that
                // masked the real arrival-time defect.
                nominalWindowSamples = featureWindowSamples;
                if (windowSamplesSeen < featureWindowSamples)
                    ++undersampledWindows;

                const uint8_t nPackets = (uint8_t)std::min<size_t>(amps.size(), (size_t)MAX_SAMPLES);
                if (nPackets > 0)
                {
                    // The scheduler can skip physical UDP transmit during bring-up while
                    // still exercising feature extraction, controller logic, and timing.
                    if (!printedTick1BeforeSend)
                    {
                        std::printf("Tick debug: before first UDP send controlTick=%llu packet=%llu nPackets=%u skipUdp=%s\n",
                                    (unsigned long long)controlTicks,
                                    (unsigned long long)sentPackets,
                                    (unsigned)nPackets,
                                    skipUdpSend ? "true" : "false");
                        printedTick1BeforeSend = true;
                    }
                    if (!skipUdpSend)
                    {
                        if (sendUDPPacketWords(rzSock, amps.data(), nPackets) == SOCKET_ERROR)
                            std::printf("Warning: UDP send failed.\n");
                    }
                    const int64_t t_udp_send_us = clock.now_us();
                    udpSendTiming.add(t_udp_send_us - t_normalize_done_us);
                    totalTickTiming.add(t_udp_send_us - t_in_us);
                    if (!printedTick1AfterSend)
                    {
                        std::printf("Tick debug: after first UDP send controlTick=%llu packet=%llu\n",
                                    (unsigned long long)controlTicks,
                                    (unsigned long long)sentPackets);
                        printedTick1AfterSend = true;
                    }
                    if (tickIndex <= VERBOSE_CONTROL_TICKS)
                    {
                        std::printf("Tick trace: send complete controlTick=%llu packet=%llu\n",
                                    (unsigned long long)tickIndex,
                                    (unsigned long long)sentPackets);
                    }

                    ++sentPackets;
                    if (validateLogEnabled && validateLog.is_open())
                    {
                        const double mpc_ms = (double)(t_mpc_done_us - t_in_us) / 1000.0;
                        const double total_ms = (double)(t_udp_send_us - t_in_us) / 1000.0;
                        const double x0 = x.empty() ? 0.0 : x[0];
                        const double u0 = useCachedFastPath
                            ? ((!rawUView || rawUView->empty()) ? 0.0 : (*rawUView)[0])
                            : (u.empty() ? 0.0 : u[0]);
                        const double amp0 = amps.empty() ? 0.0 : amps[0];
                        validateLog
                            << sentPackets << ','
                            << pos << ','
                            << x0 << ','
                            << u0 << ','
                            << amp0 << ','
                            << t_in_us << ','
                            << t_mpc_done_us << ','
                            << t_udp_send_us << ','
                            << mpc_ms << ','
                            << total_ms << std::endl;  // flushed per row so the CSV survives an abnormal termination
                    }
                    if ((sentPackets % printEveryPackets) == 0)
                    {
                        const double mpc_ms = (double)(t_mpc_done_us - t_in_us) / 1000.0;
                        const double total_ms = (double)(t_udp_send_us - t_in_us) / 1000.0;
                        std::printf("\nLatency: mpc=%.3f ms, in->udp=%.3f ms (packet=%llu)\n",
                                    mpc_ms, total_ms, (unsigned long long)sentPackets);
                        std::printf("pos=%lld buffered=%zu\n", (long long)pos, ring.size);
                    }
                }

                if (maxControlTicks > 0 && controlTicks >= maxControlTicks)
                {
                    stopped = true;
                    std::printf("\nExit reason: reached max control ticks (%zu).\n", maxControlTicks);
                    break;
                }

                if (tickFrames > 0)
                {
                    // PLL update. Phase detector: extrapolate the stream position
                    // to this tick's scheduled time from the newest frame's
                    // (position, arrival-time) pair, and compare against the tick
                    // grid target. Positive error = stream ahead of our grid =
                    // we are late -> shorten the next period slightly. Gains are
                    // deliberately low so chunky frame arrivals average out and
                    // tick-to-tick spacing stays smooth.
                    const int64_t schedUs = nextControlUs;
                    double corrUs = 0.0;
                    const double stepUnits = (expectedStep > 0) ? (double)expectedStep : 1.0;
                    const double unitsPerUs = streamFsNominal * stepUnits / 1e6;
                    const double unitsPerTick = (double)tickFrames * stepUnits;
                    if (prevOffset >= 0 && lastFrameArrivalUs > 0)
                    {
                        const double predictedPos = (double)pos +
                            (double)(schedUs - lastFrameArrivalUs) * unitsPerUs;
                        if (!pllLocked)
                        {
                            // Quantize the grid origin to an absolute multiple of
                            // unitsPerTick: the stim carrier divides the SAME
                            // counter, so this makes the command->latch phase a
                            // fixed per-session constant instead of start-time
                            // luck. --tick-phase-us then dials that constant to
                            // mid-latch-period (measured by
                            // check_impulse_delivery.py).
                            pllBasePos = std::ceil(predictedPos / unitsPerTick) * unitsPerTick
                                         + tickPhaseUs * unitsPerUs;
                            pllTicksSinceBase = 0;
                            pllLocked = true;
                        }
                        else
                        {
                            const double target =
                                pllBasePos + (double)pllTicksSinceBase * unitsPerTick;
                            const double phaseErrUs = (predictedPos - target) / unitsPerUs;
                            if (std::fabs(phaseErrUs) > 3.0 * tickPeriodNomUs)
                            {
                                // Offset jump or long stall: rebase instead of
                                // slewing through many periods of error.
                                pllBasePos = predictedPos;
                                pllTicksSinceBase = 0;
                                ++pllResyncs;
                                if (pllResyncs <= 5 || (pllResyncs % 100) == 0)
                                    std::printf("Frame-PLL resync: phase error %.1f ms "
                                                "(total resyncs %llu)\n",
                                                phaseErrUs / 1000.0,
                                                (unsigned long long)pllResyncs);
                            }
                            else
                            {
                                corrUs = PLL_PHASE_GAIN * phaseErrUs;
                                if (corrUs >  PLL_PHASE_SLEW_US) corrUs =  PLL_PHASE_SLEW_US;
                                if (corrUs < -PLL_PHASE_SLEW_US) corrUs = -PLL_PHASE_SLEW_US;
                                double trimUs = PLL_FREQ_GAIN * phaseErrUs;
                                if (trimUs >  PLL_FREQ_SLEW_US) trimUs =  PLL_FREQ_SLEW_US;
                                if (trimUs < -PLL_FREQ_SLEW_US) trimUs = -PLL_FREQ_SLEW_US;
                                tickPeriodUsF -= trimUs;
                                const double lim = 0.1 * tickPeriodNomUs;
                                if (tickPeriodUsF > tickPeriodNomUs + lim) tickPeriodUsF = tickPeriodNomUs + lim;
                                if (tickPeriodUsF < tickPeriodNomUs - lim) tickPeriodUsF = tickPeriodNomUs - lim;
                                pllAbsErrSumUs += std::fabs(phaseErrUs);
                                if (std::fabs(phaseErrUs) > pllAbsErrMaxUs)
                                    pllAbsErrMaxUs = std::fabs(phaseErrUs);
                                ++pllErrSamples;
                            }
                        }
                        ++pllTicksSinceBase;
                    }
                    nextControlUs += (int64_t)(tickPeriodUsF - corrUs + 0.5);
                    nowUs = clock.now_us();
                    if (nowUs >= nextControlUs)
                    {
                        const int64_t lateUs = nowUs - nextControlUs;
                        const uint64_t skipped =
                            1 + (uint64_t)((double)lateUs / tickPeriodNomUs);
                        droppedControlTicks += skipped;
                        nextControlUs = nowUs + (int64_t)(tickPeriodUsF + 0.5);
                        pllTicksSinceBase += skipped;   // keep the grid target aligned
                        if (droppedControlTicks <= 5 || (droppedControlTicks % 100) == 0)
                        {
                            std::printf("Scheduler resync: dropped=%llu totalDropped=%llu lateUs=%lld\n",
                                        (unsigned long long)skipped,
                                        (unsigned long long)droppedControlTicks,
                                        (long long)lateUs);
                        }
                    }
                }
                else
                {
                    nextControlUs += CONTROL_INTERVAL_US;
                    nowUs = clock.now_us();
                    if (nowUs >= nextControlUs)
                    {
                        const int64_t lateUs = nowUs - nextControlUs;
                        const uint64_t skipped = 1 + (uint64_t)(lateUs / CONTROL_INTERVAL_US);
                        droppedControlTicks += skipped;
                        nextControlUs = nowUs + CONTROL_INTERVAL_US;
                        if (droppedControlTicks <= 5 || (droppedControlTicks % 100) == 0)
                        {
                            std::printf("Scheduler resync: dropped=%llu totalDropped=%llu lateUs=%lld\n",
                                        (unsigned long long)skipped,
                                        (unsigned long long)droppedControlTicks,
                                        (long long)lateUs);
                        }
                    }
                }
                if (tickIndex <= VERBOSE_CONTROL_TICKS)
                {
                    std::printf("Tick trace: end controlTick=%llu nextPacket=%llu\n",
                                (unsigned long long)tickIndex,
                                (unsigned long long)sentPackets);
                }
            }
        }

        if (minWindowSamplesSeen == (size_t)-1)
            minWindowSamplesSeen = 0;
        // The summary is intended to answer three questions quickly:
        // 1) did the 100 Hz scheduler stay healthy?
        // 2) how expensive was each stage?
        // 3) in localhost mode, how often did we use fresh vs held vs zero output?
        std::printf("\nSummary: packets=%llu controlTicks=%llu droppedControlTicks=%llu finalBuffered=%zu/%zu nominalWindowSamples=%zu minWindowSamples=%zu undersampledWindows=%llu\n",
                    (unsigned long long)sentPackets,
                    (unsigned long long)controlTicks,
                    (unsigned long long)droppedControlTicks,
                    ring.size,
                    ring.capacity,
                    nominalWindowSamples,
                    minWindowSamplesSeen,
                    (unsigned long long)undersampledWindows);
        std::printf("Acquisition: backlogFramesDropped=%llu (stale pre-start history "
                    "plus any mid-run catch-up; not a data loss the controller can see)\n",
                    (unsigned long long)backlogFramesDropped);
        if (tickFrames > 0)
        {
            std::printf("Scheduler: tickMode=frame-locked-PLL(%zu frames/tick, nominal %.4f ms) "
                        "phaseErr avg %.2f ms max %.2f ms resyncs %llu\n",
                        tickFrames, tickPeriodNomUs / 1000.0,
                        pllErrSamples ? pllAbsErrSumUs / (double)pllErrSamples / 1000.0 : 0.0,
                        pllAbsErrMaxUs / 1000.0,
                        (unsigned long long)pllResyncs);
        }
        std::printf("Timing summary:\n");
        print_timing_stats("  preprocess", preprocessTiming);
        print_timing_stats("  controller", controllerTiming);
        print_timing_stats("  normalizeClamp", normalizeClampTiming);
        print_timing_stats("  udpSend", udpSendTiming);
        print_timing_stats("  totalTick", totalTickTiming);
        if (useLocalhostController)
        {
            print_timing_stats("  localhostOutputAge", localhostOutputAgeTiming);
            std::printf("Localhost summary: submitted=%llu replies=%llu failures=%llu timeouts=%llu staleDropped=%llu skippedWhileBusy=%llu freshTicks=%llu heldTicks=%llu zeroTicks=%llu freshReplyTransitions=%llu policyTransitions=%llu inFlight=%s lastReplySeq=%u\n",
                        (unsigned long long)localhostRequests,
                        (unsigned long long)localhostReplySuccesses,
                        (unsigned long long)0,
                        (unsigned long long)localhostReplyTimeouts,
                        (unsigned long long)localhostReplyStaleDropped,
                        (unsigned long long)localhostReplyPreSendDrained,
                        (unsigned long long)localhostTicksUsingFreshOutput,
                        (unsigned long long)localhostTicksUsingHeldOutput,
                        (unsigned long long)localhostTicksUsingZeroOutput,
                        (unsigned long long)localhostFreshReplyTransitions,
                        (unsigned long long)localhostPolicyTransitions,
                        localhostRequestInFlight ? "true" : "false",
                        (unsigned)localhostLastSeenReplySeq);
            if (!localhostLastError.empty())
                std::printf("Localhost last error: %s\n", localhostLastError.c_str());
        }
        std::printf("\nStopping.\n");
    }
    catch (const std::exception& ex)
    {
        // SECTION 8: Exception-safe cleanup path.
        std::cerr << "Fatal error: " << ex.what() << "\n";
        std::printf("Cleanup trace: exception path begin\n");
        if (card) std::printf("Cleanup trace: releasing PO8e card\n");
        if (card) PO8e::releaseCard(card);
        if (localhostControllerSock != INVALID_SOCKET) std::printf("Cleanup trace: closing localhost controller socket\n");
        if (localhostControllerSock != INVALID_SOCKET) closesocket(localhostControllerSock);
        if (rzSock != INVALID_SOCKET) zero_stim_outputs(rzSock, activeUdpOutputCount);
        if (rzSock != INVALID_SOCKET) std::printf("Cleanup trace: disconnecting RZ socket\n");
        if (rzSock != INVALID_SOCKET) disconnectRZ(rzSock);
        if (udpReady) std::printf("Cleanup trace: WSACleanup\n");
        if (udpReady) udp_cleanup();
        if (useFastExitShutdown)
        {
            std::printf("Fast exit shutdown active: skipping MATLAB engine teardown after exception.\n");
            std::fflush(stdout);
            _Exit(1);
        }
        shutdown_matlab_controller(eng, controllerMode);
        return 1;
    }
    catch (...)
    {
        // SECTION 8: Exception-safe cleanup path.
        std::cerr << "Fatal error: unknown exception\n";
        std::printf("Cleanup trace: unknown-exception path begin\n");
        if (card) std::printf("Cleanup trace: releasing PO8e card\n");
        if (card) PO8e::releaseCard(card);
        if (localhostControllerSock != INVALID_SOCKET) std::printf("Cleanup trace: closing localhost controller socket\n");
        if (localhostControllerSock != INVALID_SOCKET) closesocket(localhostControllerSock);
        if (rzSock != INVALID_SOCKET) zero_stim_outputs(rzSock, activeUdpOutputCount);
        if (rzSock != INVALID_SOCKET) std::printf("Cleanup trace: disconnecting RZ socket\n");
        if (rzSock != INVALID_SOCKET) disconnectRZ(rzSock);
        if (udpReady) std::printf("Cleanup trace: WSACleanup\n");
        if (udpReady) udp_cleanup();
        if (useFastExitShutdown)
        {
            std::printf("Fast exit shutdown active: skipping MATLAB engine teardown after unknown exception.\n");
            std::fflush(stdout);
            _Exit(1);
        }
        shutdown_matlab_controller(eng, controllerMode);
        return 1;
    }

    // SECTION 9: Normal shutdown cleanup.
    // Shutdown ordering is left explicit because teardown has been a recurring
    // debugging focus during this project, especially when MATLAB/UDP state is live.
    std::printf("Cleanup trace: normal shutdown begin\n");
    // Zero the stimulator BEFORE dropping the socket. The RZ2 holds the last
    // commanded amplitude, so exiting without this leaves stim running.
    if (rzSock != INVALID_SOCKET) zero_stim_outputs(rzSock, activeUdpOutputCount);
    if (rzSock != INVALID_SOCKET) std::printf("Cleanup trace: disconnecting RZ socket\n");
    if (rzSock != INVALID_SOCKET) disconnectRZ(rzSock);
    if (localhostControllerSock != INVALID_SOCKET) std::printf("Cleanup trace: closing localhost controller socket\n");
    if (localhostControllerSock != INVALID_SOCKET) closesocket(localhostControllerSock);
    if (udpReady) std::printf("Cleanup trace: WSACleanup\n");
    if (udpReady) udp_cleanup();
    if (card) std::printf("Cleanup trace: releasing PO8e card\n");
    if (card) PO8e::releaseCard(card);
    if (useFastExitShutdown)
    {
        std::printf("Fast exit shutdown active: skipping MATLAB engine teardown.\n");
        std::fflush(stdout);
        _Exit(0);
    }
    shutdown_matlab_controller(eng, controllerMode);
    return 0;
}
