#include <stdlib.h>
#include <stdio.h>
#include <string>
#include <cstring>
#include "TDTUDP.h"

/*
class UDPSender {
private:
    SOCKET sock;
    std::string adapterIP;

public:
    bool initialize(const std::string& ipPrefix) {
        adapterIP = ipPrefix;

        // Create socket
        sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if (sock == INVALID_SOCKET) {
            std::cerr << "Failed to create socket\n";
            return false;
        }

        // Get adapter info
        IP_ADAPTER_INFO AdapterInfo[16 * 1024];
        DWORD dwBufLen = sizeof(AdapterInfo);

        DWORD ret = GetAdaptersInfo(AdapterInfo, &dwBufLen);
        if (ret != ERROR_SUCCESS) {
            std::cerr << "Failed to get adapter info\n";
            closesocket(sock);
            return false;
        }

        // Find adapter with matching IP prefix
        IP_ADAPTER_INFO* adapter = AdapterInfo;
        while (adapter) {
            if (adapter->Type == MIB_IF_TYPE_ETHERNET) {
                std::string ip = adapter->IpAddressList.IpAddress.String;
                if (ip.find(ipPrefix) == 0) {
                    break;
                }
            }
            adapter = adapter->Next;
        }

        if (!adapter) {
            std::cerr << "Could not find adapter with IP starting with: " << ipPrefix << "\n";
            closesocket(sock);
            return false;
        }

        // Bind to adapter's IP address
        sockaddr_in addr;
        addr.sin_family = AF_INET;
        addr.sin_port = htons(0); // System chooses available port
        inet_pton(AF_INET, adapter->IpAddressList.IpAddress.String, &(addr.sin_addr));

        if (bind(sock, (SOCKADDR*)&addr, sizeof(addr)) == SOCKET_ERROR) {
            std::cerr << "Failed to bind to adapter\n";
            closesocket(sock);
            return false;
        }

        return true;
    }

    bool sendPacket(const char* data, int length, const std::string& destIP, unsigned short destPort) {
        sockaddr_in destAddr;
        destAddr.sin_family = AF_INET;
        destAddr.sin_port = htons(destPort);
        inet_pton(AF_INET, destIP.c_str(), &(destAddr.sin_addr));

        int bytesSent = sendto(sock, data, length, 0, (SOCKADDR*)&destAddr, sizeof(destAddr));
        if (bytesSent == SOCKET_ERROR) {
            std::cerr << "Failed to send packet\n";
            return false;
        }

        std::cout << "Sent " << bytesSent << " bytes through adapter with IP: " << adapterIP << "\n";
        return true;
    }

    ~UDPSender() {
        if (sock != INVALID_SOCKET) {
            closesocket(sock);
        }
    }
};
*/

// set up a windows socket to listen for UDP
SOCKET openSocket(uint32_t ipAddr)
{
    //std::string ipPrefix = "10.1.0";

    sockaddr_in sin;
    SOCKET sock = INVALID_SOCKET;

    // prepare the SIN to send to
    memset(&sin, 0, sizeof(sockaddr_in));

    sin.sin_family = AF_INET;
    sin.sin_addr.S_un.S_addr = ipAddr; //inet_addr("tdt_udp_0000000");
    sin.sin_port = htons(LISTEN_PORT);

    sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock == INVALID_SOCKET)
    {
        fprintf(stdout, "Failed to create the UDP socket: %d\n", WSAGetLastError());
        return sock;
    }
    else if (connect(sock, (struct sockaddr*)&sin, sizeof(sockaddr_in)) != 0)
    {
        closesocket(sock);
        sock = INVALID_SOCKET;
        fprintf(stdout, "Failed to connect the UDP socket: %d\n", WSAGetLastError());
        return sock;
    }

    /*
    // Get adapter info
    DWORD dwBufLen = sizeof(IP_ADAPTER_INFO);
    IP_ADAPTER_INFO* AdapterInfo = (IP_ADAPTER_INFO*)malloc(dwBufLen);
    if (!AdapterInfo) {
        fprintf(stderr, "Failed to allocate memory\n");
        closesocket(sock);
        return false;
    }

    DWORD ret = GetAdaptersInfo(AdapterInfo, &dwBufLen);
    if (ret == ERROR_BUFFER_OVERFLOW) {
        free(AdapterInfo);
        AdapterInfo = (IP_ADAPTER_INFO*)malloc(dwBufLen);
        if (!AdapterInfo) {
            fprintf(stderr, "Failed to allocate memory\n");
            closesocket(sock);
            return false;
        }
        ret = GetAdaptersInfo(AdapterInfo, &dwBufLen);
    }

    if (ret != ERROR_SUCCESS) {
        fprintf(stderr, "Failed to get adapter info\n");
        free(AdapterInfo);
        closesocket(sock);
        return false;
    }

    // Find adapter with matching IP prefix
    IP_ADAPTER_INFO* adapter = AdapterInfo;
    while (adapter) {
        if (adapter->Type == MIB_IF_TYPE_ETHERNET) {
            std::string ip = adapter->IpAddressList.IpAddress.String;
            if (ip.find(ipPrefix) == 0) {
                break;
            }
        }
        adapter = adapter->Next;
    }

    free(AdapterInfo);

    if (!adapter) {
        fprintf(stderr, "Could not find adapter with IP starting with: %s\n", ipPrefix.c_str());
        closesocket(sock);
        return false;
    }

    // Bind to adapter's IP address
    sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = LISTEN_PORT; // System chooses available port
    inet_pton(AF_INET, adapter->IpAddressList.IpAddress.String, &(addr.sin_addr));

    if (bind(sock, (SOCKADDR*)&addr, sizeof(addr)) == SOCKET_ERROR) {
        fprintf(stderr, "Failed to bind to adapter\n");
        closesocket(sock);
    }
    */

    return sock;
}


// Function to send UDP packet with header and float value
int sendUDPPacket(SOCKET sock, float floatValue)
{
    char nValues = 1;
    char header[4] = { (char)0x55, (char)0xAA, (char)0x00, (char)nValues };

    // Create buffer for header and float value
    char buffer[sizeof(header) + sizeof(float)];

    // Copy header bytes
    memcpy(buffer, header, sizeof(header));

    // Convert float to network byte order
    uint32_t intVal;
    memcpy(&intVal, &floatValue, sizeof(float));  // Convert float to integer representation
    uint32_t networkInt = htonl(intVal);          // Convert to network byte order

    // Copy the network-order integer to buffer
    memcpy(buffer + sizeof(header), &networkInt, sizeof(float));

    // Send the packet
    int bytesSent = send(sock, buffer, sizeof(buffer), 0);

    if (bytesSent == SOCKET_ERROR) {
        printf("send failed with error: %d\n", WSAGetLastError());
        return SOCKET_ERROR;
    }

    return bytesSent;
}

//contact the RZ to make sure it is talking UDP, and that it has a matching protocol version
bool checkRZ(SOCKET sock)
{

    //make a large buffer to hold the response, and create the header for get_version
    const int bufsize = 1024;
    char req[HEADER_BYTES] = COMMAND_HEADER(GET_VERSION), resp[bufsize];

    //send the command packet to the RZ
    if (send(sock, req, HEADER_BYTES, 0) != HEADER_BYTES)
    {
        fprintf(stdout, "Failed to send GET_VERSION packet: %d\n", WSAGetLastError());
        return false;
    }

    fprintf(stdout, "here waiting\n");

    const int socket_flags = 0;
    //get the response from the rz and check validity
    if (recv(sock, resp, bufsize, socket_flags) != HEADER_BYTES ||    //make sure response is the correct size
        memcmp(req, resp, HEADER_BYTES - 1) != 0 ||                     //responses must echo first three bytes back, as an ACK
        resp[COUNT_OFFSET] != PROTOCOL_VERSION)                       //ensure correct protocol version (sent back in the count field)
    {
        fprintf(stdout, "Failed to receive a proper acknowledgement packet.");
        return false;
    }

    fprintf(stdout, "done\n");

    return true;
}

//tell the RZ to start piping data to my IP address
bool setRemoteIp(SOCKET sock)
{
    //create the header for set_remote_ip
    char req[HEADER_BYTES] = COMMAND_HEADER(SET_REMOTE_IP);

    //send the command packet to the RZ
    if (send(sock, req, HEADER_BYTES, 0) != HEADER_BYTES)
    {
        fprintf(stdout, "Failed to send \"start sending\" packet: %d\n", WSAGetLastError());
        return false;
    }

    //the RZ sends no response to this command, so return true
    return true;
}

//tell the RZ to stop piping data to my IP address
void disconnectRZ(SOCKET sock)
{
    if (sock != INVALID_SOCKET)
    {
        char packet[HEADER_BYTES] = COMMAND_HEADER(FORGET_REMOTE_IP);
        if (send(sock, packet, HEADER_BYTES, 0) != HEADER_BYTES)
            fprintf(stderr, "Failed to send \"stop sending\" packet: %d\n", WSAGetLastError());

        closesocket(sock);
        sock = INVALID_SOCKET;
    }
}

int sendPacket(SOCKET sock, float value)
{
    char nValues = 1;

    // send up to 16 32-bit values (4*16=64)

    // 1 32-bit value = 4 bytes
    char packet[HEADER_BYTES + 4] = { (char)0x00 };
    packet[0] = (char)0x55;
    packet[1] = (char)0xAA;
    packet[3] = nValues;

    //char packet[HEADER_BYTES + 64] = DATA_HEADER(nValues);
    unsigned int y = 0;

    // add loop here if you want more than one value in packet
    unsigned int temp = *reinterpret_cast<unsigned int*>(&value);
    //unsigned int temp;
    //(float*)&temp = value;
    memcpy(packet + HEADER_BYTES, &temp, 4);

    // put it in network order
    //uint32_t* data = (uint32_t*)(packet + HEADER_BYTES);
    //data[0] = htonl(data[0]);
    
    printf("Packet: %d %d %d %d ", packet[0], packet[1], packet[2], packet[3]);
    printf("%d %d %d %d\n", packet[4], packet[5], packet[6], packet[7]);

    return send(sock, packet, HEADER_BYTES + nValues * 4, 0);
}

int sendPacketI32Words(SOCKET sock, const int32_t* values, uint8_t count, bool networkByteOrder)
{
    // Build one TDT UDP data packet:
    // [0]=0x55 [1]=0xAA [2]=DATA_PACKET [3]=count, followed by count int32 words.
    // By default payload words are sent in host order to match sendPacket()/UDPExample behavior.
    // Set networkByteOrder=true to force htonl() conversion for A/B testing.
    if (sock == INVALID_SOCKET || values == NULL || count == 0)
        return SOCKET_ERROR;

    if (count > MAX_SAMPLES)
        count = MAX_SAMPLES;

    char packet[BUFFER_SIZE] = { 0 };
    packet[0] = (char)HEADER_0;
    packet[1] = (char)HEADER_1;
    packet[2] = (char)DATA_PACKET;
    packet[3] = (char)count;

    for (uint8_t i = 0; i < count; ++i)
    {
        uint32_t word = (uint32_t)values[i];
        if (networkByteOrder)
            word = htonl(word);
        memcpy(packet + HEADER_BYTES + (i * 4), &word, 4);
    }

    const int nBytes = HEADER_BYTES + (int)count * 4;
    const int sent = send(sock, packet, nBytes, 0);
    if (sent == SOCKET_ERROR)
        fprintf(stdout, "send data packet failed: %d\n", WSAGetLastError());

    return sent;
}
