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

// Build MPC input vector from one PO8e sample-time across channels.
// If mpcInputCount > channel count, remaining entries are zero-padded.
static std::vector<double> build_mpc_input(const std::vector<int16_t>& sampleByChannel,
                                           size_t mpcInputCount)
{
    std::vector<double> x(mpcInputCount, 0.0);
    const size_t n = std::min(mpcInputCount, sampleByChannel.size());
    for (size_t i = 0; i < n; ++i)
        x[i] = static_cast<double>(sampleByChannel[i]);
    return x;
}

int main(int argc, char** argv)
{
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

    // =========================================================================
    // SECTION 3: Runtime arguments
    // -------------------------------------------------------------------------
    // argv[1]: RZ target host/IP
    // argv[2]: MATLAB working directory containing mpc_step.m
    // argv[3]: MPC input vector size
    // =========================================================================
    const char* tdt_host = (argc >= 2) ? argv[1] : "10.1.0.100"; //"TDT_UDP_28_2869";
    const char* matlab_workdir = (argc >= 3) ? argv[2] : "C:/Users/brets/Documents/MATLAB";
    const size_t mpcInputCount = (argc >= 4) ? static_cast<size_t>(std::max(1, std::atoi(argv[3]))) : 16;

    matlab::engine::MATLABEngine* engRaw = nullptr;
    PO8e* card = nullptr;
    SOCKET rzSock = INVALID_SOCKET;
    bool udpReady = false;

    try
    {
        // =====================================================================
        // SECTION 4: Start MATLAB Engine and set working folder for mpc_step.m
        // =====================================================================
        auto eng = matlab::engine::startMATLAB();
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

        // =====================================================================
        // SECTION 7: Closed-loop processing loop
        // ---------------------------------------------------------------------
        // For each available PO8e sample:
        // 1) read one timepoint across channels
        // 2) build MPC input vector
        // 3) call MATLAB mpc_step()
        // 4) quantize outputs to int32
        // 5) send packed int32 words via TDT UDP format
        // =====================================================================
        int64_t pos = 0;
        int64_t prevOffset = -1;
        int64_t expectedStep = 0;
        uint64_t sentPackets = 0;
        const uint64_t printEveryPackets = 100;
        HiResClock clock;
        bool stopped = false;
        std::vector<int16_t> temp((size_t)std::max(nCh, 1));
        std::printf("Entering loop (MPC input size=%zu).\n", mpcInputCount);

        while (!stopped)
        {
            if (!card->waitForDataReady())
                break;

            size_t numSamples = card->samplesReady(&stopped);
            if (stopped) break;
            if (numSamples == 0) continue;

            for (size_t i = 0; i < numSamples; ++i)
            {
                int64_t offsets[1];
                const size_t got = card->readBlock((short*)temp.data(), 1, offsets);
                if (got != 1)
                {
                    std::printf("readBlock failed.\n");
                    stopped = true;
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

                // Convert current sample-frame into MPC control outputs.
                const int64_t t_in_us = clock.now_us();       // right after readBlock
                const std::vector<double> x = build_mpc_input(temp, mpcInputCount);
                const std::vector<double> u = call_mpc_step(*engRaw, x);
                const int64_t t_mpc_done_us = clock.now_us(); // right after mpc_step
                const std::vector<int32_t> amps = quantize_amplitudes(u, 1.0, 0, 100000);

                // TDT protocol limit from TDTUDP.h.
                const uint8_t nPackets = (uint8_t)std::min<size_t>(amps.size(), (size_t)MAX_SAMPLES);
                if (nPackets > 0)
                {
                    // Use host-order payload to mirror known-working UDPExample behavior.
                    if (sendPacketI32Words(rzSock, amps.data(), nPackets, false) == SOCKET_ERROR)
                        std::printf("Warning: UDP send failed.\n");
                    const int64_t t_udp_send_us = clock.now_us(); // right after UDP send returns

                    ++sentPackets;
                    if ((sentPackets % printEveryPackets) == 0)
                    {
                        const double mpc_ms = (double)(t_mpc_done_us - t_in_us) / 1000.0;
                        const double total_ms = (double)(t_udp_send_us - t_in_us) / 1000.0;
                        std::printf("\nLatency: mpc=%.3f ms, in->udp=%.3f ms (packet=%llu)\n",
                                    mpc_ms, total_ms, (unsigned long long)sentPackets);
                    }
                }

                card->flushBufferedData(1);
            }

            std::printf("pos=%lld ready=%zu\r", (long long)pos, numSamples);
            std::fflush(stdout);
        }

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
