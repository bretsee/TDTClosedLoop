// wire.hpp -- the localhost controller UDP protocol.
//
// BYTE-COMPATIBLE with matlab_controller_server.m. That compatibility is the
// whole design: this server is a drop-in replacement for the MATLAB one, so the
// benchmarked MpcPo8eUdpClosedLoop.exe needs no change and no rebuild, and the
// two controller implementations can be A/B compared on the identical path.
//
// Request  (C++ loop -> controller):  [seq u32 BE][featureCount u32 BE][f32 BE x N]
// Response (controller -> C++ loop):  [seq u32 BE][valueCount   u32 BE][f32 BE x M]
//
// Both sides are big-endian on the wire regardless of host order; see
// matlab_controller_server.m's unpack_u32_be / unpack_f32_be_vec / pack_response.
#pragma once

#include <cstdint>
#include <cstring>
#include <vector>

namespace ctl {

inline uint32_t load_u32_be(const unsigned char* p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8)  |  (uint32_t)p[3];
}

inline void store_u32_be(unsigned char* p, uint32_t v) {
    p[0] = (unsigned char)((v >> 24) & 0xFF);
    p[1] = (unsigned char)((v >> 16) & 0xFF);
    p[2] = (unsigned char)((v >> 8)  & 0xFF);
    p[3] = (unsigned char)( v        & 0xFF);
}

inline float load_f32_be(const unsigned char* p) {
    const uint32_t bits = load_u32_be(p);
    float f;
    std::memcpy(&f, &bits, sizeof f);   // type-punning via memcpy, not a cast
    return f;
}

inline void store_f32_be(unsigned char* p, float f) {
    uint32_t bits;
    std::memcpy(&bits, &f, sizeof bits);
    store_u32_be(p, bits);
}

struct Request {
    uint32_t seq = 0;
    std::vector<double> features;
};

// Returns false if the datagram is too short or truncated -- matching the MATLAB
// server, which logs and ignores such packets rather than replying to them. A
// silent drop is correct here: the C++ loop already has a timeout fail-safe, and
// replying with garbage would be worse than not replying at all.
inline bool parse_request(const unsigned char* buf, int len, Request& out) {
    if (len < 8) return false;
    out.seq = load_u32_be(buf);
    const uint32_t count = load_u32_be(buf + 4);
    const long long needed = 8LL + (long long)count * 4LL;
    if ((long long)len < needed) return false;
    out.features.resize(count);
    for (uint32_t i = 0; i < count; ++i)
        out.features[i] = (double)load_f32_be(buf + 8 + (size_t)i * 4);
    return true;
}

inline int build_response(uint32_t seq, const std::vector<double>& values,
                          unsigned char* buf, int cap) {
    const int needed = 8 + (int)values.size() * 4;
    if (needed > cap) return -1;
    store_u32_be(buf, seq);
    store_u32_be(buf + 4, (uint32_t)values.size());
    for (size_t i = 0; i < values.size(); ++i)
        store_f32_be(buf + 8 + i * 4, (float)values[i]);
    return needed;
}

}  // namespace ctl
