# Audio handling in L2M

This document describes how `l2m_engine.py` turns the audio inside a Linktivity
`.lrec` recording into the audio track of the exported MP4.

## 1. What is read from the `.lrec`

The `.lrec` is a sequence of records with a timestamp, a control type and a
payload. Audio is carried in records whose control type is `VOICE` (2).

For each voice record the engine:

1. Keeps only voice payloads with subtype `1`.
2. Reads the sender/connection identifier from the payload.
3. Extracts the 256-byte TrueSpeech frame.
4. Groups the frames by sender and sorts each group by timestamp.

Each sender is decoded and placed as its own mono track. The tracks are summed
at the end, so simultaneous speakers are mixed rather than dropped.

## 2. Decoding

The preferred decoder is the bundled `bin/tsdecode.exe`. If it is unavailable
or fails, the engine falls back to a raw TrueSpeech WAV header plus `ffmpeg`.

The decoder output is converted to:

- 8000 Hz
- mono
- signed 16-bit little-endian PCM

The decoder emits 22 leading samples that are not part of the first voice
packet; the engine removes them (`PRIME = 22`). Each packet is expected to
produce 1920 samples:

```
1920 samples / 8000 Hz = 240 ms per packet
```

If the decoder returns fewer samples, the engine zero-pads to the expected
length. If it returns more, the extra samples are discarded.

## 3. Timeline and the 400 ms gap rule

Voice packets are not placed at every raw timestamp. The recorder suppresses
very short waits between packets so that continuous speech does not acquire a
click or a tiny silence at every packet boundary.

The engine uses the same rule:

```
VOICE_GAP_MS = 400
PACKET_MS = 240

cursor = timestamp of first packet
previous = timestamp of first packet

for each packet:
    if not first and (packet.timestamp - previous) >= VOICE_GAP_MS:
        cursor = packet.timestamp
    place packet at cursor
    cursor += PACKET_MS
    previous = packet.timestamp
```

In words:

- A gap **shorter than 400 ms** is ignored. The next packet starts 240 ms after
  the previous packet, so the speech stays continuous.
- A gap **of 400 ms or more** is preserved. The next packet starts at its real
  archive timestamp, leaving silence for the missing time.
- No voice packet is dropped and no packet is duplicated.
- The first packet starts at its real timestamp. Any silence before it remains
  in the track; the MP4 mux later trims the audio at the first video frame.

The comparison is `>=`, not `>`. This matches the player's condition:

```java
// MessageRecorder.java, voice playback path
var8 = ... (timestamp - lastVoiceTimestamp < m_voiceGap);
```

`var8 == true` means the player skips the wait; therefore a gap exactly equal
to `m_voiceGap` is **not** skipped.

## 4. Recorder parity

The reference behavior was measured with the real Linktivity player and clean
loopback captures (other audio sessions muted).

Measured gap handling:

| Gap between voice packets | Recorder result |
| --- | --- |
| 0-360 ms | joined into continuous speech |
| 480 ms | gap preserved |
| 942 ms | gap preserved |
| 1000 ms | gap preserved |
| 1100 ms | gap preserved |

The threshold is therefore **400 ms**. It is not 1000 ms.

For the source session this means the 942 ms interval around 17:40 is a real
recorder gap. The original MP4's approximately 0.68 s hole at that point is
expected: the previous packet is 240 ms long, then the remaining time is
silence until the next packet's timestamp.

A temporary build used `VOICE_GAP_MS = 1000`. That joined the 942 ms gap and
moved the word earlier. It is not recorder parity and should not be restored.

### `m_voiceLimit`

The player also has an `m_voiceLimit` counter that limits how many consecutive
voice packets may skip their timestamps; when the limit is reached the player
waits once and resets the counter. This can produce periodic stutters in the
player. The L2M engine currently models the gap rule (`m_voiceGap`) but not
`m_voiceLimit`. The measured full-session comparison matched without it. If a
future comparison shows periodic drift or extra waits, measure `m_voiceLimit`
before changing the engine.

## 5. Mixing and output

For each sender:

1. Build a float track using the placement rule above.
2. Track the end of the longest sender track.
3. Add 50 ms of tail silence (`SR / 20`).
4. Sum all sender tracks.
5. Clip to the signed 16-bit range and write `audio_full.wav`
   (8000 Hz, mono, 16-bit PCM).

The MP4 mux then:

- trims the audio at the first video timestamp
  (`atrim=start=t0, asetpts=PTS-STARTPTS`);
- encodes AAC at 128 kbit/s;
- resamples to 48000 Hz;
- keeps it mono.

The audio is not enhanced, denoised, or normalized. It is the recording's own
TrueSpeech audio, decoded and placed on the recorder's timeline.

## 6. Known limits

- TrueSpeech is an 8 kHz codec; the 48 kHz AAC track does not add detail.
- Missing or short decoder output is zero-padded, not reconstructed.
- Multiple speakers are summed; loud overlapping speech can clip.
- `m_voiceLimit` is not modeled (see above).
- `extract.py` in `lrec-analysis` is an analysis tool, not the production
  engine. It uses the same 400 ms rule but a different implementation.

## 7. Code map

| Location | Responsibility |
| --- | --- |
| `l2m_engine.py:103` | TrueSpeech decode and PCM normalization |
| `l2m_engine.py:120` | Voice grouping, placement, mixing, WAV output |
| `l2m_engine.py:146` | `VOICE_GAP_MS = 400` |
| `l2m_engine.py:173` | Gap comparison (`>= 400 ms`) |
| `l2m_engine.py:322` | MP4 mux and AAC settings |
| `lrec-analysis/src/linktivity/MessageRecorder.java:681` | Player's `m_voiceGap` / `m_voiceLimit` logic |
