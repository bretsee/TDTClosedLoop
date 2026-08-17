#ifndef _SAMPLE_SOURCE_H_
#define _SAMPLE_SOURCE_H_

// ============================================================================
// SampleSource: acquisition source abstraction for the closed-loop engine.
// ----------------------------------------------------------------------------
// The 100 Hz control loop only needs a small, fixed subset of the PO8e card
// API to acquire samples. ISampleSource captures exactly that subset so the
// loop, ring buffer, feature extraction, controller dispatch, and UDP path are
// shared byte-for-byte between the live path and a hardware-free simulation
// path.
//
//   Po8eSampleSource : thin pass-through over a live PO8e* card.
//   SimSampleSource  : generates or replays frames with no hardware attached,
//                      paced in real wall-clock time so the 10 ms window and
//                      100 Hz cadence see realistic per-window sample counts.
//
// The engine selects one implementation at startup (--sim-input ...) and then
// talks only to ISampleSource. Nothing downstream of acquisition changes.
// ============================================================================

#include <cstdint>
#include <cstdio>
#include <cmath>
#include <string>
#include <vector>
#include <chrono>
#include <fstream>

#include "PO8e.h"

// ----------------------------------------------------------------------------
// Interface
// ----------------------------------------------------------------------------
// Method signatures mirror the PO8e calls used by the acquisition loop:
//   startCollecting(), samplesReady(bool*), numChannels(),
//   readBlock(void*, int, int64_t*), flushBufferedData(int), getLastError().
class ISampleSource
{
public:
    virtual ~ISampleSource() {}

    // Begin streaming. Returns false on failure.
    virtual bool startCollecting() = 0;

    // Number of sample frames (per channel) currently available to read.
    // Sets *stopped (if non-null) true when the stream has stopped flowing.
    virtual size_t samplesReady(bool* stopped) = 0;

    // Channels in the current stream (>0), or <0 on error.
    virtual int numChannels() = 0;

    // Bytes per sample in the stream. The PO8e delivers whatever format the
    // Synapse gizmo is set to: 2 = int16, 4 = float32. The caller MUST size
    // readBlock buffers as nSamples * numChannels() * sampleSizeBytes() --
    // assuming 2 while the card streams float32 is a heap overrun on every
    // read (found the hard way 2026-08-15, caught by PageHeap inside
    // PO8eStreaming.dll).
    virtual int sampleSizeBytes() { return 2; }

    // Read nSamples frames into buffer as interleaved samples of
    // sampleSizeBytes() each (frame-major: all channels of frame 0, then
    // frame 1, ...). offsets[i] (if non-null) receives the monotonic stream
    // position of frame i. Returns frames read.
    virtual int readBlock(void* buffer, int nSamples, int64_t* offsets) = 0;

    // Release numSamples frames from the underlying buffer.
    virtual void flushBufferedData(int numSamples) = 0;

    // Most recent error code (0 == none).
    virtual int getLastError() { return 0; }

    // Short human-readable source name for logging.
    virtual const char* name() const = 0;
};

// ----------------------------------------------------------------------------
// Live PO8e pass-through (non-owning: the card is released by the engine)
// ----------------------------------------------------------------------------
class Po8eSampleSource : public ISampleSource
{
public:
    explicit Po8eSampleSource(PO8e* card) : card_(card) {}

    bool startCollecting() override { return card_->startCollecting(); }
    size_t samplesReady(bool* stopped) override { return card_->samplesReady(stopped); }
    int numChannels() override { return card_->numChannels(); }
    int sampleSizeBytes() override { return card_->dataSampleSize(); }
    int readBlock(void* buffer, int nSamples, int64_t* offsets) override
    {
        return card_->readBlock(buffer, nSamples, offsets);
    }
    void flushBufferedData(int numSamples) override { card_->flushBufferedData(numSamples); }
    int getLastError() override { return card_->getLastError(); }
    const char* name() const override { return "PO8e"; }

private:
    PO8e* card_;
};

// ----------------------------------------------------------------------------
// Hardware-free simulation / replay source
// ----------------------------------------------------------------------------
class SimSampleSource : public ISampleSource
{
public:
    enum Mode { SINE, NOISE, FILE };

    // channels: emulated stream width.
    // fs      : emulated per-channel sample rate (Hz); paces samplesReady().
    // mode    : SINE / NOISE / FILE. For FILE, filePath is a raw int16 file of
    //           frame-major interleaved samples (channels values per frame),
    //           e.g. MATLAB: fwrite(fid, int16(X), 'int16') with X = [channels x frames].
    SimSampleSource(int channels, double fs, Mode mode,
                    const std::string& filePath = std::string(),
                    double sineHz = 10.0, double amplitude = 1000.0)
        : channels_(channels > 0 ? channels : 1),
          fs_(fs > 0.0 ? fs : 1.0),
          mode_(mode),
          sineHz_(sineHz),
          amplitude_(amplitude)
    {
        if (mode_ == FILE)
            loadFile(filePath);
    }

    bool startCollecting() override
    {
        start_ = std::chrono::steady_clock::now();
        consumedFrames_ = 0;
        started_ = true;
        std::printf("Sim source: mode=%s channels=%d fs=%.4f Hz%s\n",
                    modeName(), channels_, fs_,
                    (mode_ == FILE) ? fileSummary().c_str() : "");
        return true;
    }

    size_t samplesReady(bool* stopped) override
    {
        if (stopped)
            *stopped = false;
        if (!started_)
            return 0;
        const double elapsedS =
            std::chrono::duration<double>(std::chrono::steady_clock::now() - start_).count();
        int64_t due = (int64_t)(elapsedS * fs_);
        int64_t avail = due - consumedFrames_;
        if (avail < 0)
            avail = 0;
        // Cap the batch so a long stall can't request a giant read at once;
        // the loop simply catches up over subsequent passes (same as live).
        const int64_t kMaxBatch = 8192;
        if (avail > kMaxBatch)
            avail = kMaxBatch;
        return (size_t)avail;
    }

    int numChannels() override { return channels_; }

    // PO8e read/flush contract, mirrored exactly (this used to differ, which made
    // sim validation of the discard paths vacuous -- flush-without-read discarded
    // nothing while backlogFramesDropped still counted it):
    //   readBlock returns the OLDEST buffered frame(s) and does NOT consume them;
    //   flushBufferedData(n) discards the oldest n frames.
    // The loop's read-then-flush(1) pattern therefore advances one frame per
    // pair of calls, and a flush with no read genuinely skips data, both here
    // and on hardware.
    int readBlock(void* buffer, int nSamples, int64_t* offsets) override
    {
        if (nSamples <= 0)
            return 0;
        short* out = static_cast<short*>(buffer);
        for (int s = 0; s < nSamples; ++s)
        {
            const int64_t frameIndex = consumedFrames_ + s;
            for (int ch = 0; ch < channels_; ++ch)
                out[(size_t)s * channels_ + ch] = genSample(ch, frameIndex);
            if (offsets)
                offsets[s] = frameIndex;
        }
        return nSamples;
    }

    void flushBufferedData(int numSamples) override
    {
        if (numSamples > 0)
            consumedFrames_ += numSamples;
    }

    const char* name() const override { return "sim"; }

private:
    const char* modeName() const
    {
        switch (mode_)
        {
        case SINE:  return "sine";
        case NOISE: return "noise";
        case FILE:  return "file";
        }
        return "sine";
    }

    std::string fileSummary() const
    {
        char buf[128];
        std::snprintf(buf, sizeof(buf), " fileFrames=%lld", (long long)fileFrames_);
        return std::string(buf);
    }

    void loadFile(const std::string& path)
    {
        std::ifstream in(path.c_str(), std::ios::binary | std::ios::ate);
        if (!in)
        {
            std::printf("Sim source: WARNING could not open file '%s'; falling back to sine.\n",
                        path.c_str());
            mode_ = SINE;
            return;
        }
        const std::streamsize bytes = in.tellg();
        in.seekg(0, std::ios::beg);
        const size_t count = (size_t)(bytes / (std::streamsize)sizeof(int16_t));
        fileData_.resize(count);
        if (count > 0)
            in.read(reinterpret_cast<char*>(fileData_.data()), (std::streamsize)(count * sizeof(int16_t)));
        fileFrames_ = (int64_t)(count / (size_t)channels_);
        if (fileFrames_ <= 0)
        {
            std::printf("Sim source: WARNING file '%s' has < 1 full frame for %d channels; "
                        "falling back to sine.\n", path.c_str(), channels_);
            mode_ = SINE;
            fileData_.clear();
        }
    }

    short genSample(int ch, int64_t frameIndex)
    {
        switch (mode_)
        {
        case SINE:
        {
            const double t = (double)frameIndex / fs_;
            // Per-channel phase so channels are not identical.
            const double phase = 0.19 * (double)ch;
            double v = amplitude_ * std::sin(2.0 * 3.14159265358979323846 * sineHz_ * t + phase);
            return clampToShort(v);
        }
        case NOISE:
        {
            return clampToShort(amplitude_ * nextNoise());
        }
        case FILE:
        {
            if (fileFrames_ <= 0)
                return 0;
            const int64_t f = frameIndex % fileFrames_;   // loop the record
            const size_t idx = (size_t)f * (size_t)channels_ + (size_t)ch;
            return (idx < fileData_.size()) ? fileData_[idx] : (short)0;
        }
        }
        return 0;
    }

    // Deterministic [-1, 1) white noise via xorshift64 (reproducible runs).
    double nextNoise()
    {
        rng_ ^= rng_ << 13;
        rng_ ^= rng_ >> 7;
        rng_ ^= rng_ << 17;
        // Map top 53 bits to [0,1) then to [-1,1).
        const double u = (double)(rng_ >> 11) / 9007199254740992.0;
        return 2.0 * u - 1.0;
    }

    static short clampToShort(double v)
    {
        if (v > 32767.0)  v = 32767.0;
        if (v < -32768.0) v = -32768.0;
        return (short)std::lround(v);
    }

    int channels_;
    double fs_;
    Mode mode_;
    double sineHz_;
    double amplitude_;

    bool started_ = false;
    std::chrono::steady_clock::time_point start_;
    int64_t consumedFrames_ = 0;   // frames discarded via flushBufferedData

    std::vector<int16_t> fileData_;
    int64_t fileFrames_ = 0;

    uint64_t rng_ = 0x9E3779B97F4A7C15ULL;
};

#endif // _SAMPLE_SOURCE_H_
