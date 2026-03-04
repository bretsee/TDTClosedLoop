#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif

#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>

#pragma comment(lib, "ws2_32.lib")

static constexpr uint16_t LISTEN_PORT = 22022;
static constexpr uint8_t HEADER_0 = 0x55;
static constexpr uint8_t HEADER_1 = 0xAA;

static constexpr uint8_t DATA_PACKET = 0x00;
static constexpr uint8_t GET_VERSION = 0x01;
static constexpr uint8_t SET_REMOTE_IP = 0x02;
static constexpr uint8_t FORGET_REMOTE_IP = 0x03;

static constexpr uint8_t PROTOCOL_VERSION = 1;
static constexpr int HEADER_BYTES = 4;
static constexpr uint8_t MAX_SAMPLES = 244;

static bool wsa_init()
{
    WSADATA wsa {};
    return (WSAStartup(MAKEWORD(2, 2), &wsa) == 0);
}

static void wsa_cleanup()
{
    WSACleanup();
}

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

static SOCKET open_socket(uint32_t ipAddr)
{
    sockaddr_in sin {};
    sin.sin_family = AF_INET;
    sin.sin_addr.S_un.S_addr = ipAddr;
    sin.sin_port = htons(LISTEN_PORT);

    SOCKET sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock == INVALID_SOCKET)
    {
        std::printf("socket() failed: %d\n", WSAGetLastError());
        return INVALID_SOCKET;
    }

    if (connect(sock, reinterpret_cast<sockaddr*>(&sin), sizeof(sin)) != 0)
    {
        std::printf("connect() failed: %d\n", WSAGetLastError());
        closesocket(sock);
        return INVALID_SOCKET;
    }

    return sock;
}

static bool send_command(SOCKET sock, uint8_t cmd)
{
    char packet[HEADER_BYTES] = { (char)HEADER_0, (char)HEADER_1, (char)cmd, 0 };
    const int sent = send(sock, packet, HEADER_BYTES, 0);
    return (sent == HEADER_BYTES);
}

static bool get_version(SOCKET sock, uint8_t& outVersion, int timeoutMs)
{
    if (!send_command(sock, GET_VERSION))
    {
        std::printf("GET_VERSION send failed: %d\n", WSAGetLastError());
        return false;
    }

    DWORD tv = (DWORD)timeoutMs;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&tv), sizeof(tv));

    char resp[HEADER_BYTES] = { 0 };
    const int got = recv(sock, resp, HEADER_BYTES, 0);
    if (got != HEADER_BYTES)
    {
        std::printf("GET_VERSION recv failed/timeout: %d\n", WSAGetLastError());
        return false;
    }

    if ((uint8_t)resp[0] != HEADER_0 || (uint8_t)resp[1] != HEADER_1 || (uint8_t)resp[2] != GET_VERSION)
    {
        std::printf("GET_VERSION bad ACK bytes: [%u %u %u %u]\n",
                    (unsigned)(uint8_t)resp[0], (unsigned)(uint8_t)resp[1],
                    (unsigned)(uint8_t)resp[2], (unsigned)(uint8_t)resp[3]);
        return false;
    }

    outVersion = (uint8_t)resp[3];
    return true;
}

static bool send_data_i32(SOCKET sock, const int32_t* data, uint8_t count)
{
    if (!data || count == 0)
        return false;
    if (count > MAX_SAMPLES)
        count = MAX_SAMPLES;

    std::vector<char> packet((size_t)HEADER_BYTES + (size_t)count * 4, 0);
    packet[0] = (char)HEADER_0;
    packet[1] = (char)HEADER_1;
    packet[2] = (char)DATA_PACKET;
    packet[3] = (char)count;

    for (uint8_t i = 0; i < count; ++i)
    {
        const uint32_t net = htonl((uint32_t)data[i]);
        std::memcpy(packet.data() + HEADER_BYTES + (size_t)i * 4, &net, 4);
    }

    const int sent = send(sock, packet.data(), (int)packet.size(), 0);
    if (sent != (int)packet.size())
    {
        std::printf("DATA send failed: %d\n", WSAGetLastError());
        return false;
    }
    return true;
}

int main(int argc, char** argv)
{
    const char* host = (argc >= 2) ? argv[1] : "10.1.0.1";
    const int32_t baseValue = (argc >= 3) ? (int32_t)std::atoi(argv[2]) : 12345;
    int count = (argc >= 4) ? std::atoi(argv[3]) : 1;
    int periodMs = (argc >= 5) ? std::atoi(argv[4]) : 20;
    int loops = (argc >= 6) ? std::atoi(argv[5]) : 1000;

    if (count < 1) count = 1;
    if (count > MAX_SAMPLES) count = MAX_SAMPLES;
    if (periodMs < 1) periodMs = 1;
    if (loops < 1) loops = 1;

    if (!wsa_init())
    {
        std::printf("WSAStartup failed.\n");
        return 1;
    }

    const uint32_t ip = resolve_ipv4_addr(host);
    if (ip == INADDR_NONE)
    {
        std::printf("Failed to resolve host: %s\n", host);
        wsa_cleanup();
        return 1;
    }

    SOCKET sock = open_socket(ip);
    if (sock == INVALID_SOCKET)
    {
        wsa_cleanup();
        return 1;
    }

    std::printf("Connected UDP to %s:%u\n", host, (unsigned)LISTEN_PORT);

    uint8_t version = 0;
    if (get_version(sock, version, 1000))
        std::printf("GET_VERSION OK. RZ protocol version = %u\n", (unsigned)version);
    else
        std::printf("GET_VERSION failed (continuing to data send test).\n");

    if (!send_command(sock, SET_REMOTE_IP))
        std::printf("SET_REMOTE_IP failed: %d\n", WSAGetLastError());
    else
        std::printf("SET_REMOTE_IP sent.\n");

    std::vector<int32_t> payload((size_t)count, baseValue);
    std::printf("Sending %d packets: count=%d words, period=%d ms\n", loops, count, periodMs);

    for (int n = 0; n < loops; ++n)
    {
        for (int i = 0; i < count; ++i)
            payload[(size_t)i] = baseValue + n + i;

        if (!send_data_i32(sock, payload.data(), (uint8_t)count))
            break;

        if ((n % 50) == 0)
            std::printf("sent packet %d, firstWord=%ld\n", n, (long)payload[0]);

        Sleep((DWORD)periodMs);
    }

    send_command(sock, FORGET_REMOTE_IP);
    closesocket(sock);
    wsa_cleanup();
    std::printf("Done.\n");
    return 0;
}

