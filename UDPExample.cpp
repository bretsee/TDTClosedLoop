#include <stdlib.h>
#include <stdio.h>
#include <math.h>

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "Ws2_32.lib")  //allows linking against the winsock2 library

#include "TDTUDP.h"

#define RZ_IP "10.1.0.100"

int main(int argc, char **argv)
{

	WSADATA wsaData;
	int result = WSAStartup(MAKEWORD(2, 2), &wsaData);

	if (result != 0) {
		printf("WSAStartup failed with error %d\n", result);
		return 1;
	}

	//ULONG currentRes;
	//NtSetTimerResolution(5000, TRUE, &currentRes);

	//open the socket
	fprintf(stdout, "Setting up a UDP Socket...");
	SOCKET sock = INVALID_SOCKET;
	sock = openSocket(inet_addr(RZ_IP));
	if (sock == INVALID_SOCKET)
	{
		fprintf(stdout, "Could not open the socket: %d\n", WSAGetLastError());
		return -1;
	}
	else
		fprintf(stdout, "OK.\n");

	//check that the RZ is on the network and communicating via UDP
	if (checkRZ(sock))
		fprintf(stdout, "Found an RZ at IP: %s.\n", RZ_IP);
	else
	{
		fprintf(stdout, "No RZ found at IP: %s.\n", RZ_IP);
		return -1;
	}

	// point the RZ to this computer so we can start receiving
	if (setRemoteIp(sock))
	{
		fprintf(stdout, "Succeeded in pointing the RZ to this IP.\n");
	}
	else
	{
		fprintf(stdout, "Attempt to point the RZ to this IP failed.\n");
		return -1;
	}

	float amp = 1000.0f;// +random() * 10.0f;
	printf("UDP: %d \n", sendPacket(sock, amp));

	disconnectRZ(sock);
	WSACleanup();
    return 0;
}
