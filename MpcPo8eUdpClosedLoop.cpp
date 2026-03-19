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

#include "PO8e.h"
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
        LARGE_INTEGER t {};
        QueryPerformanceCounter(&t);
        return (int64_t)((t.QuadPart * 1000000LL) / freq.QuadPart);
    }
};

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

// ============================================================================
// SECTION 2: MATLAB MPC bridge helpers
// ----------------------------------------------------------------------------
// call_mpc_step() converts C++ vector -> MATLAB array, calls mpc_step(), then
// converts MATLAB output back into a C++ vector.
// ============================================================================
static std::vector<double> call_mpc_step(matlab::engine::MATLABEngine& eng,
                                         const std::vector<double>& x)
{
    using matlab::data::Array;
    using matlab::data::ArrayFactory;
    using matlab::data::TypedArray;

    ArrayFactory f;
    TypedArray<double> x_m = f.createArray<double>({x.size(), 1});
    for (size_t i = 0; i < x.size(); ++i)
        x_m[i] = x[i];

    std::vector<Array> out = eng.feval(u"mpc_step", 1, std::vector<Array>{x_m});
    TypedArray<double> u_m = out[0];

    std::vector<double> u(u_m.getNumberOfElements());
    for (size_t i = 0; i < u.size(); ++i)
        u[i] = u_m[i];

    return u;
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

    void pushFrame(const std::vector<int16_t>& frame, int64_t timestampUs)
    {
        if (capacity == 0 || channelValues.empty())
            return;

        timestampsUs[writeIndex] = timestampUs;
        const size_t n = std::min(frame.size(), channelValues.size());
        for (size_t ch = 0; ch < n; ++ch)
            channelValues[ch][writeIndex] = static_cast<float>(frame[ch]);

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
};

int main(int argc, char** argv)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    std::printf("MpcPo8eUdpClosedLoop build: %s %s\n", __DATE__, __TIME__);

    // --test-udp mode:
    //   MpcPo8eUdpClosedLoop.exe --test-udp [tdt_host_or_ip] [value] [count] [period_ms]
    // Example:
    //   MpcPo8eUdpClosedLoop.exe --test-udp 10.1.0.1 12345 4 20
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
    //   --constant-output V
    //   --udp-output-count N
    //   --ring-buffer-capacity N
    //   --validate-log path.csv
    // =========================================================================
    const char* tdt_host = (argc >= 2) ? argv[1] : "10.1.0.100"; //"TDT_UDP_28_2869";
    const char* matlab_workdir = (argc >= 3) ? argv[2] : "C:/Users/brets/Documents/MATLAB";
    const size_t mpcInputCount = (argc >= 4) ? static_cast<size_t>(std::max(1, std::atoi(argv[3]))) : 16;
    size_t requestedUdpOutputCount = 0;
    size_t ringBufferCapacity = 65536;
    bool validateLogEnabled = false;
    std::string validateLogPath;
    bool constantOutputEnabled = false;
    float constantOutputValue = 0.0f;
    for (int i = 1; i < argc; ++i)
    {
        const std::string arg = argv[i];
        if (arg == "--constant-output" && (i + 1) < argc)
        {
            constantOutputEnabled = true;
            constantOutputValue = (float)std::atof(argv[i + 1]);
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
        else if (arg == "--ring-buffer-capacity" && (i + 1) < argc)
        {
            ringBufferCapacity = static_cast<size_t>(std::max(1, std::atoi(argv[i + 1])));
            ++i;
        }
    }

    matlab::engine::MATLABEngine* engRaw = nullptr;
    PO8e* card = nullptr;
    SOCKET rzSock = INVALID_SOCKET;
    bool udpReady = false;
    std::ofstream validateLog;

    try
    {
        // =====================================================================
        // SECTION 4: Start MATLAB Engine and set working folder for mpc_step.m
        // ---------------------------------------------------------------------
        // In constant-output mode we skip MATLAB entirely so we can isolate
        // native-library failures from the control/transport path.
        // =====================================================================
        std::unique_ptr<matlab::engine::MATLABEngine> eng;
        if (!constantOutputEnabled)
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
            std::cout << "MATLAB started. mpc_step path set to: " << matlab_workdir << "\n";
        }
        else
        {
            std::printf("Constant-output mode enabled: skipping MATLAB, value=%g\n",
                        (double)constantOutputValue);
        }

        // =====================================================================
        // SECTION 5: Open PO8e stream
        // =====================================================================
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

        if (!card->startCollecting())
        {
            std::printf("startCollecting() failed with: %d\n", card->getLastError());
            return 1;
        }
        std::printf("Card is collecting.\n");

        std::printf("Waiting for stream...\n");
        while (card->samplesReady() == 0)
            compatUSleep(5000);

        const int nCh = card->numChannels();
        std::printf("Streaming. numChannels=%d\n", nCh);
        const size_t udpOutputCount = (requestedUdpOutputCount > 0)
            ? requestedUdpOutputCount
            : (size_t)std::max(nCh, 1);
        std::printf("Output channels per UDP packet=%zu\n", udpOutputCount);

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

        // Optional handshake check; left disabled to avoid blocking if the RZ isn't replying yet.
        // if (!checkRZ(rzSock)) std::printf("Warning: RZ UDP version check failed.\n");

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

        // =====================================================================
        // SECTION 7: Continuous acquisition + 100 Hz control loop
        // ---------------------------------------------------------------------
        // PO8e acquisition runs continuously and appends each sample frame into
        // a per-channel ring buffer. Every 10 ms, the controller:
        // 1) preprocesses the most recent 10 ms window into one scalar per input
        //    channel (mean absolute value placeholder)
        // 2) calls MATLAB mpc_step() once
        // 3) sends one UDP packet containing the output vector
        // =====================================================================
        static const int64_t CONTROL_INTERVAL_US = 10000;
        static const int64_t PREPROCESS_WINDOW_US = 10000;
        static const int POLL_SLEEP_US = 1000;
        int64_t pos = 0;
        int64_t prevOffset = -1;
        int64_t expectedStep = 0;
        uint64_t sentPackets = 0;
        uint64_t controlTicks = 0;
        uint64_t undersampledWindows = 0;
        size_t minWindowSamplesSeen = (size_t)-1;
        size_t nominalWindowSamples = 0;
        const uint64_t printEveryPackets = 500;
        HiResClock clock;
        bool stopped = false;
        std::vector<int16_t> temp((size_t)std::max(nCh, 1));
        SampleRingBuffer ring;
        ring.initialize((size_t)std::max(nCh, 1), ringBufferCapacity);
        int64_t nextControlUs = clock.now_us() + CONTROL_INTERVAL_US;
        std::printf("Entering loop (MPC input size=%zu, UDP output count=%zu, control=100 Hz, ring capacity=%zu).\n",
                    mpcInputCount, udpOutputCount, ringBufferCapacity);

        while (!stopped)
        {
            // Poll buffered sample count directly. In practice this is more stable
            // than repeatedly calling the vendor semaphore wait with very short
            // timeouts inside the 100 Hz scheduler.
            size_t numSamples = card->samplesReady(&stopped);
            if (stopped)
            {
                std::printf("\nExit reason: PO8e stream reported stopped.\n");
                break;
            }

            if (numSamples == 0)
                compatUSleep(POLL_SLEEP_US);

            for (size_t i = 0; i < numSamples; ++i)
            {
                int64_t offsets[1];
                const size_t got = card->readBlock((short*)temp.data(), 1, offsets);
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
                ring.pushFrame(temp, sampleTimeUs);

                card->flushBufferedData(1);
            }

            // The controller runs at a fixed 100 Hz cadence independent of the
            // raw sample acquisition loop.
            int64_t nowUs = clock.now_us();
            while (nowUs >= nextControlUs)
            {
                const int64_t t_in_us = clock.now_us();
                size_t windowSamplesSeen = 0;
                const std::vector<double> features =
                    ring.computeMeanAbsWindow(mpcInputCount, t_in_us, PREPROCESS_WINDOW_US, &windowSamplesSeen);
                const std::vector<double> x = build_mpc_input(features, mpcInputCount, udpOutputCount);
                std::vector<double> u;
                if (constantOutputEnabled)
                    u.assign(udpOutputCount, (double)constantOutputValue);
                else
                    u = call_mpc_step(*engRaw, x);
                const int64_t t_mpc_done_us = clock.now_us();
                const std::vector<float> amps = clamp_amplitudes_f32(u, 0.0f, 100000.0f);
                ++controlTicks;
                minWindowSamplesSeen = std::min(minWindowSamplesSeen, windowSamplesSeen);
                if (windowSamplesSeen > nominalWindowSamples)
                    nominalWindowSamples = windowSamplesSeen;
                else if (nominalWindowSamples > 0 && windowSamplesSeen < nominalWindowSamples)
                    ++undersampledWindows;

                const uint8_t nPackets = (uint8_t)std::min<size_t>(amps.size(), (size_t)MAX_SAMPLES);
                if (nPackets > 0)
                {
                    if (sendUDPPacketWords(rzSock, amps.data(), nPackets) == SOCKET_ERROR)
                        std::printf("Warning: UDP send failed.\n");
                    const int64_t t_udp_send_us = clock.now_us();

                    ++sentPackets;
                    if (validateLogEnabled && validateLog.is_open())
                    {
                        const double mpc_ms = (double)(t_mpc_done_us - t_in_us) / 1000.0;
                        const double total_ms = (double)(t_udp_send_us - t_in_us) / 1000.0;
                        const double x0 = x.empty() ? 0.0 : x[0];
                        const double u0 = u.empty() ? 0.0 : u[0];
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
                            << total_ms << '\n';
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

                nextControlUs += CONTROL_INTERVAL_US;
                nowUs = clock.now_us();
            }
        }

        if (minWindowSamplesSeen == (size_t)-1)
            minWindowSamplesSeen = 0;
        std::printf("\nSummary: packets=%llu controlTicks=%llu finalBuffered=%zu/%zu nominalWindowSamples=%zu minWindowSamples=%zu undersampledWindows=%llu\n",
                    (unsigned long long)sentPackets,
                    (unsigned long long)controlTicks,
                    ring.size,
                    ring.capacity,
                    nominalWindowSamples,
                    minWindowSamplesSeen,
                    (unsigned long long)undersampledWindows);
        std::printf("\nStopping.\n");
    }
    catch (const std::exception& ex)
    {
        // SECTION 8: Exception-safe cleanup path.
        std::cerr << "Fatal error: " << ex.what() << "\n";
        if (card) PO8e::releaseCard(card);
        if (rzSock != INVALID_SOCKET) disconnectRZ(rzSock);
        if (udpReady) udp_cleanup();
        return 1;
    }
    catch (...)
    {
        // SECTION 8: Exception-safe cleanup path.
        std::cerr << "Fatal error: unknown exception\n";
        if (card) PO8e::releaseCard(card);
        if (rzSock != INVALID_SOCKET) disconnectRZ(rzSock);
        if (udpReady) udp_cleanup();
        return 1;
    }

    // SECTION 9: Normal shutdown cleanup.
    if (rzSock != INVALID_SOCKET) disconnectRZ(rzSock);
    if (udpReady) udp_cleanup();
    if (card) PO8e::releaseCard(card);
    return 0;
}
