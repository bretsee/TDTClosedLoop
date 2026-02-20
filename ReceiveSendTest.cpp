#include <cstdlib>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

#include "../Include/PO8e.h"
#include "compat.h"

// =====================
// TDT UDP protocol bits
// =====================
static constexpr uint16_t TDT_MAGIC = 0x55AA;
static constexpr uint8_t  CMD_SEND_DATA        = 0x00;
static constexpr uint8_t  CMD_SET_REMOTE_IP    = 0x02;
// static constexpr uint8_t  CMD_GET_VERSION      = 0x01;
// static constexpr uint8_t  CMD_FORGET_REMOTE_IP = 0x03;

static constexpr uint16_t TDT_UDP_PORT = 22022;

// Builds the 32-bit header the same way MATLAB does:
// hex2dec([MAGIC, CMD, NPACKETS]) -> 0x55AA CC NN
static inline uint32_t make_tdt_header(uint8_t cmd, uint8_t nPackets)
{
    return (uint32_t(TDT_MAGIC) << 16) | (uint32_t(cmd) << 8) | uint32_t(nPackets);
}

// =====================
// UDP socket portability
// =====================
#ifdef WIN32
  #include <winsock2.h>
  #include <ws2tcpip.h>
  #pragma comment(lib, "ws2_32.lib")
  using socklen_t_compat = int;
  static bool udp_init()
  {
      WSADATA wsa;
      return (WSAStartup(MAKEWORD(2,2), &wsa) == 0);
  }
  static void udp_cleanup() { WSACleanup(); }
  static void udp_close(SOCKET s) { closesocket(s); }
#else
  #include <unistd.h>
  #include <arpa/inet.h>
  #include <netdb.h>
  #include <sys/socket.h>
  #include <sys/types.h>
  using SOCKET = int;
  static constexpr int INVALID_SOCKET = -1;
  static bool udp_init() { return true; }
  static void udp_cleanup() {}
  static void udp_close(SOCKET s) { close(s); }
  using socklen_t_compat = socklen_t;
#endif

struct UdpTarget
{
    SOCKET sock = INVALID_SOCKET;
    sockaddr_storage addr {};
    socklen_t_compat addrLen = 0;
};

static bool resolve_udp_target(const char* host, uint16_t port, UdpTarget& out)
{
    addrinfo hints {};
    hints.ai_family   = AF_UNSPEC;   // allow IPv4/IPv6
    hints.ai_socktype = SOCK_DGRAM;
    hints.ai_protocol = IPPROTO_UDP;

    char portStr[16];
    std::snprintf(portStr, sizeof(portStr), "%u", unsigned(port));

    addrinfo* res = nullptr;
    int rc = getaddrinfo(host, portStr, &hints, &res);
    if (rc != 0 || !res) return false;

    SOCKET s = (SOCKET)socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (s == INVALID_SOCKET)
    {
        freeaddrinfo(res);
        return false;
    }

    std::memset(&out, 0, sizeof(out));
    out.sock = s;
    std::memcpy(&out.addr, res->ai_addr, res->ai_addrlen);
    out.addrLen = (socklen_t_compat)res->ai_addrlen;

    freeaddrinfo(res);
    return true;
}

static bool udp_send_i32(UdpTarget& t, const int32_t* data, size_t nWords)
{
    const char* bytes = reinterpret_cast<const char*>(data);
    const int nBytes = (int)(nWords * sizeof(int32_t));
    int sent = (int)sendto(t.sock, bytes, nBytes, 0, (sockaddr*)&t.addr, t.addrLen);
    return (sent == nBytes);
}

// =====================
// Your closed-loop logic
// =====================
// Replace this with your real mapping from acquired samples -> outgoing command/data.
//
// Right now: convert each 16-bit sample into an int32 "packet word" (example scaling).
static inline int32_t processSample(int16_t x)
{
    // Example: pass-through (sign-extended), or scale, clamp, threshold, etc.
    return (int32_t)x;
}

// =====================
// Main
// =====================
int main(int argc, char** argv)
{
    // ---- Configure TDT target hostname/IP (match your TDT_UDP.m) ----
    const char* tdt_host = (argc >= 2) ? argv[1] : "TDT_UDP_22_1012";
    // You can also pass an IP string instead, e.g. "192.168.1.123"

    // ---- PO8e: find and connect ----
    int total = PO8e::cardCount();
    std::printf("Found %d card(s) in the system.\n", total);
    if (total <= 0) return 0;

    std::printf("Connecting to card 0...\n");
    PO8e* card = PO8e::connectToCard(0);
    if (!card)
    {
        std::printf("Connection failed.\n");
        return 1;
    }
    std::printf("Connected: %p\n", (void*)card);

    if (!card->startCollecting())
    {
        std::printf("startCollecting() failed with: %d\n", card->getLastError());
        PO8e::releaseCard(card);
        return 1;
    }
    std::printf("Card is collecting.\n");

    // Wait for stream to start
    std::printf("Waiting for stream...\n");
    while (card->samplesReady() == 0)
        compatUSleep(5000);

    const int nCh = card->numChannels();
    std::printf("Streaming. numChannels=%d\n", nCh);

    // ---- UDP init + target resolve ----
    if (!udp_init())
    {
        std::printf("UDP init failed.\n");
        PO8e::releaseCard(card);
        return 1;
    }

    UdpTarget tdt {};
    if (!resolve_udp_target(tdt_host, TDT_UDP_PORT, tdt))
    {
        std::printf("Failed to resolve UDP target '%s:%u'\n", tdt_host, (unsigned)TDT_UDP_PORT);
        udp_cleanup();
        PO8e::releaseCard(card);
        return 1;
    }
    std::printf("UDP target resolved: %s:%u\n", tdt_host, (unsigned)TDT_UDP_PORT);

    // ---- Send CMD_SET_REMOTE_IP header once (like TDT_UDP.m) ----
    {
        int32_t header = (int32_t)make_tdt_header(CMD_SET_REMOTE_IP, 0);
        if (!udp_send_i32(tdt, &header, 1))
            std::printf("Warning: CMD_SET_REMOTE_IP send failed.\n");
        else
            std::printf("Sent CMD_SET_REMOTE_IP header.\n");
    }

    // ---- Acquisition + send loop ----
    int64_t pos = 0;
    bool stopped = false;

    // Buffer used by PO8e::readBlock when BLOCK_SIZE=1:
    // It returns one sample across all channels into temp[0..nCh-1] (as in PO8eExample.cpp).
    std::vector<int16_t> temp((size_t)std::max(nCh, 1));
    int64_t offset = 0;

    // Outgoing payload: header + N words (we'll send one word per channel per iteration)
    // TDT_UDP.m uses "NPACKETS" as the last byte of header; keep it <= 255.
    const uint8_t NPACKETS = (uint8_t)std::min(nCh, 255);
    std::vector<int32_t> outWords;
    outWords.resize(1 + (size_t)NPACKETS);

    outWords[0] = (int32_t)make_tdt_header(CMD_SEND_DATA, NPACKETS);

    std::printf("Entering loop (sending %u words/iter).\n", (unsigned)NPACKETS);

    while (!stopped)
    {
        if (!card->waitForDataReady())
            break;

        size_t numSamples = card->samplesReady(&stopped);
        if (stopped) break;
        if (numSamples == 0) continue;

        // Drain available samples. For each sample: read one timepoint across all channels, then send.
        for (size_t i = 0; i < numSamples; i++)
        {
            // readBlock(temp, 1, offsets) like the example
            int64_t offsets[1];
            const size_t got = card->readBlock((short*)temp.data(), 1, offsets);
            if (got != 1)
            {
                std::printf("readBlock failed.\n");
                stopped = true;
                break;
            }

            offset = offsets[0];
            if (pos + 1 != offset)
            {
                std::printf("\nSkipping %lld to position %lld\n",
                            (long long)(offset - (pos + 1)),
                            (long long)offset);
                pos = offset;
            }
            else
            {
                pos += 1;
            }

            // Build outgoing data words for first NPACKETS channels
            for (uint8_t ch = 0; ch < NPACKETS; ch++)
                outWords[1 + ch] = processSample(temp[ch]);

            // Send header + payload as int32 words
            if (!udp_send_i32(tdt, outWords.data(), outWords.size()))
                std::printf("Warning: UDP send failed.\n");

            // Discard what we just consumed
            card->flushBufferedData(1);
        }

        // Minimal progress indicator
        std::printf("pos=%lld   ready=%zu\r", (long long)pos, numSamples);
        std::fflush(stdout);
    }

    std::printf("\nStopping.\n");

    // ---- cleanup ----
    udp_close(tdt.sock);
    udp_cleanup();

    PO8e::releaseCard(card);
    return 0;
}
