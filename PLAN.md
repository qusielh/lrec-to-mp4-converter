# L2M audio plan (deferred)

Status: **not implementing yet.** This file records the deferred audio
improvement so it can be picked up later. When the user asks about a plan for
L2M or the audio, mention this plan.

## Current state

- `l2m_engine.py` uses `VOICE_GAP_MS = 400`.
- The comparison is `>= 400 ms`, matching the player's `gap < m_voiceGap` rule.
- Gaps under 400 ms are joined; gaps of 400 ms or more are preserved.
- No voice packets are dropped or duplicated.
- The engine source is updated and the free `dist/L2M.exe` was rebuilt.
- Current behavior is the recorder-compatible mode.

## Deferred idea: packet-type-aware gap classification

The 261-byte voice frame has a one-byte type at `b[0]` that the engine
currently ignores:

- Type `1`: 6,643 packets.
- Type `4`: 162 packets.

Type `4` carries real speech. **156 of the 162 type-4 packets occur immediately
after a gap of 400 ms or more.** This is strong evidence that type `4` marks
the start of a new talk spurt (first packet after silence), but it is not yet
proven.

At 17:40:

- 3,119 ms gap -> type-4 packet, RMS 2,015 (speech onset).
- 942 ms gap -> type-1 packet, RMS 3,717 (speech).
- Then continuous type-1 speech.

The 3,119 ms gap looks like a natural boundary. The 942 ms gap is inside a
talk spurt with voiced audio on both sides.

## Rule to test

```
gap < 400 ms                  -> join
next packet is type 4         -> preserve the gap (new talk spurt)
next packet is type 1
  and both sides are voiced   -> join with a 5-10 ms crossfade
otherwise                     -> preserve the gap
```

This is not a fixed-threshold guess. It uses the packet metadata plus decoded
audio energy. It does not invent speech; it concatenates existing packets and
crossfades the boundary.

Session counts:

- 6,131 gaps under 400 ms: join.
- 156 gaps before type 4: likely natural boundaries, preserve.
- 377 type-1 gaps >= 400 ms with voiced audio on both sides: join candidates.
- 140 type-1 gaps >= 400 ms with silence on one side: preserve.

## Validation before implementation

Build a **gap lab**, not a production change:

1. Select 10 type-1 voiced gaps, including the 942 ms gap at 17:40.
2. Select 10 type-4 gaps.
3. For each candidate, produce two clips: original gap vs joined with crossfade.
4. Listen and label each "continuous" or "should pause."
5. If the labels agree with the type rule, implement it in the engine.
6. If not, adjust the rule before touching the engine.

## Why not join everything

The session has 6,805 voice packets. Joining every gap gives roughly
`6805 * 240 ms = 27:13` of audio versus about 36:30 of video. That is over nine
minutes shorter and cannot stay in sync with the existing video.

Preserved type-4 gaps anchor the timeline, so the proposed rule keeps the
overall duration and does not require retiming the video.

## References

- `l2m_engine.py:146` -- `VOICE_GAP_MS = 400`
- `l2m_engine.py:173` -- gap comparison
- `AUDIO.md` -- full audio pipeline
- `lrec-analysis/src/linktivity/MessageRecorder.java:681` -- player gap/limit logic
- Packet-type audit and gap-count scripts are kept outside the repository for
  the listening-test phase.
