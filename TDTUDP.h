#pragma once

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif

#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <iphlpapi.h>
#include <cstdint>

#pragma comment(lib, "Ws2_32.lib")
#pragma comment(lib, "Iphlpapi.lib")

#define PROTOCOL_VERSION 1
#define LISTEN_PORT 22022

#define HEADER_0 0x55
#define HEADER_0_RZ2 0x00
#define HEADER_1 0xAA
#define HEADER_2_RZ2 0x00
#define HEADER_2_UDP 0x00
#define HEADER_2_SER 0x01
#define HEADER_BYTES 4
#define COMMAND_OFFSET 2
#define COUNT_OFFSET 3
#define DATA_OFFSET 4

#define DATA_PACKET 0
#define GET_VERSION 1
#define SET_REMOTE_IP 2
#define FORGET_REMOTE_IP 3
#define RESET_TO_DEFAULTS 0xFF

#define MAX_SAMPLES 244
#define BUFFER_SIZE (HEADER_BYTES + MAX_SAMPLES * 4)

#pragma warning(disable : 4310)

#define MAKE_HEADER(cmd, count) { (char)HEADER_0, (char)HEADER_1, cmd, count }
#define DATA_HEADER(count)      MAKE_HEADER(DATA_PACKET, count)
#define COMMAND_HEADER(cmd)     MAKE_HEADER(cmd, 0)

SOCKET openSocket(uint32_t ipAddr);
int sendUDPPacket(SOCKET sock, float floatValue);
int sendUDPPacketWords(SOCKET sock, const float* values, uint8_t count);
bool checkRZ(SOCKET sock);
bool setRemoteIp(SOCKET sock);
void disconnectRZ(SOCKET sock);
int sendPacket(SOCKET sock, float value);
int sendPacketI32Words(SOCKET sock, const int32_t* values, uint8_t count, bool networkByteOrder = false);
