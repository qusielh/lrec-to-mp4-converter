"""L2M - LREC to MP4 conversion engine (headless).

Pure conversion pipeline extracted verbatim from the original single-file app:
it parses Linktivity .lrec recordings, reconstructs the screen frames and the
TrueSpeech audio, and muxes them into an MP4 with ffmpeg. No GUI code lives
here, so both the desktop UI and the CLI share it.
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

FROZEN = getattr(sys, "frozen", False)
BASE = Path(sys._MEIPASS) if FROZEN else Path(__file__).resolve().parent


def bin_path(name):
    cands = ([BASE / name, BASE / "bin" / name] if FROZEN
             else [BASE / "bin" / name, BASE / name])
    for c in cands:
        if c.exists():
            return str(c)
    return str(cands[-1])


def asset_path(name):
    cands = [BASE / "assets" / name, BASE / name]
    for c in cands:
        if c.exists():
            return str(c)
    return str(cands[0])


FFMPEG = bin_path("ffmpeg.exe")
TS_DECODE = bin_path("tsdecode.exe")

# ---------------------------------------------------------------- lrec format
ENC = bytes([116, 109, 103, 98, 120, 100, 106, 102, 113, 97, 118, 110, 114, 104,
             101, 119, 99, 122, 107, 115, 121, 112, 108, 117, 105, 111])
FLAG_COMPRESSED = 2
FLAG_HEADER_ENCRYPTED = 16
FLAG_BUFFER_ENCRYPTED = 32
MANAGER, CHAT, VOICE, VIEWPORT, SUPERVISOR = 0, 1, 2, 3, 8


class Cancelled(Exception):
    pass


CURRENT = {"proc": None}


def _hidden():
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kw["startupinfo"] = si
    return kw


def parse_lrec(path):
    data = open(path, "rb").read()
    n = len(data)
    pos = 0
    recs = []
    while pos < n:
        ts = struct.unpack_from("<Q", data, pos)[0]
        h = pos + 8
        size = data[h + 2] | (data[h + 3] << 8) | (data[h + 4] << 16)
        ctl = data[h + 5] | (data[h + 6] << 8)
        flg = data[h + 7] | (data[h + 8] << 8)
        buflen = size - 11
        hdr = bytearray(data[h:h + 16])
        buf = bytearray(data[h + 16:h + 16 + buflen])
        if flg & FLAG_HEADER_ENCRYPTED:
            for i in range(5):
                hdr[11 + i] ^= ENC[i]
        if flg & FLAG_BUFFER_ENCRYPTED:
            for i in range(len(buf)):
                buf[i] ^= ENC[(i + 5) % 26]
        payload = bytes(buf)
        if flg & FLAG_COMPRESSED:
            payload = zlib.decompress(payload)
        recs.append((ts, ctl, payload))
        pos += 24 + buflen
    return recs


# ---------------------------------------------------------------- audio
def decode_truespeech(rawpath, wavpath, pcmpath):
    if os.path.exists(TS_DECODE):
        r = subprocess.run([TS_DECODE, rawpath, pcmpath], capture_output=True,
                           **_hidden())
        if r.returncode == 0 and os.path.exists(pcmpath):
            return
    data = open(rawpath, "rb").read()
    fmt = struct.pack("<HHIIHHH", 0x0022, 1, 8000, 1067, 32, 1, 0)
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    chunks += b"data" + struct.pack("<I", len(data)) + data
    open(wavpath, "wb").write(b"RIFF" + struct.pack("<I", 4 + len(chunks)) +
                              b"WAVE" + chunks)
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", wavpath,
                    "-f", "s16le", "-ac", "1", "-ar", "8000", pcmpath],
                   check=True, capture_output=True, **_hidden())


def build_audio(recs, outdir):
    adir = os.path.join(outdir, "audio")
    os.makedirs(adir, exist_ok=True)
    per_sender = {}
    for ts, ctl, pl in recs:
        if ctl != VOICE or len(pl) < 4:
            continue
        typ = pl[0] | (pl[1] << 8)
        if typ != 1:
            continue
        ln = pl[2] | (pl[3] << 8)
        if ln + 16 > len(pl):
            continue
        em = pl[ln:]
        if len(em) < 16:
            continue
        esize = em[2] | (em[3] << 8) | (em[4] << 16)
        b = em[16:16 + esize - 11]
        if len(b) != 261:
            continue
        conn = pl[4:ln].rstrip(b"\x00")
        per_sender.setdefault(conn, []).append((ts, bytes(b[5:261])))
    if not per_sender:
        return None
    SR, SPB = 8000, 1920
    PACKET_MS = 240
    VOICE_GAP_MS = 400
    PRIME = 22
    master_end = 0
    tracks = []
    for idx, (conn, pkts) in enumerate(sorted(per_sender.items(),
                                              key=lambda kv: -len(kv[1]))):
        pkts.sort(key=lambda p: p[0])
        raw = os.path.join(adir, "s%02d.raw" % idx)
        wav = os.path.join(adir, "s%02d.wav" % idx)
        pcm = os.path.join(adir, "s%02d.pcm" % idx)
        open(raw, "wb").write(b"".join(p[1] for p in pkts))
        decode_truespeech(raw, wav, pcm)
        samples = np.frombuffer(open(pcm, "rb").read(), dtype="<i2").astype(np.float32)
        expected = len(pkts) * SPB
        if len(samples) >= PRIME + expected:
            samples = samples[PRIME:PRIME + expected]
        else:
            if len(samples) > PRIME:
                samples = samples[PRIME:]
            if len(samples) < expected:
                samples = np.pad(samples, (0, expected - len(samples)))
            samples = samples[:expected]

        starts = []
        cursor = pkts[0][0]
        prev = pkts[0][0]
        for i, (pts, _) in enumerate(pkts):
            if i and pts - prev >= VOICE_GAP_MS and pts > cursor:
                cursor = pts
            prev = pts
            starts.append(int(round(cursor * SR / 1000.0)))
            cursor += PACKET_MS
        track = np.zeros(max(starts[-1] + SPB, 0), dtype=np.float32)
        for i, off in enumerate(starts):
            end = min(off + SPB, len(track))
            if end > off:
                track[off:end] = samples[i * SPB:i * SPB + (end - off)]
        tracks.append(track)
        master_end = max(master_end, len(track))
    total = master_end + SR // 20
    master = np.zeros(total, dtype=np.float32)
    for track in tracks:
        e = min(len(track), total)
        master[:e] += track[:e]
    master = np.clip(master, -32768, 32767).astype("<i2")
    awav = os.path.join(outdir, "audio_full.wav")
    pcm = master.tobytes()
    fmt = struct.pack("<HHIIHH", 1, 1, SR, SR * 2, 2, 16)
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    chunks += b"data" + struct.pack("<I", len(pcm)) + pcm
    open(awav, "wb").write(b"RIFF" + struct.pack("<I", 4 + len(chunks)) +
                           b"WAVE" + chunks)
    return awav


# ---------------------------------------------------------------- rendering
def _lut():
    lut = np.zeros((256, 3), dtype=np.uint8)
    for i in range(256):
        lut[i] = ((i & 7) * 255 // 7, ((i >> 3) & 7) * 255 // 7, (i >> 6) * 255 // 3)
    return lut


def _rgb_masked(buf, W, H, rm, gm, bm, dt):
    V = np.frombuffer(buf, dtype=dt).astype(np.uint32)

    def ch(mask, default):
        m = mask or default
        sh = (m & -m).bit_length() - 1
        wd = bin(m >> sh).count("1") or 1
        c = ((V & np.uint32(m)) >> np.uint32(sh)) * 255 // ((1 << wd) - 1)
        return c.astype(np.uint8)

    r, g, b = ch(rm, 0x7C00), ch(gm, 0x03E0), ch(bm, 0x001F)
    return np.dstack([r, g, b]).reshape(H, W, 3)



def render_frames(recs, outdir, should_cancel, on_progress):
    frames_dir = os.path.join(outdir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    lut = _lut()
    n_vp = sum(1 for r in recs if r[1] == VIEWPORT)
    W = H = 0
    bpp = 1
    hdr_r = hdr_g = hdr_b = 0
    fb = bytearray()
    entries = []
    prev = None
    done = 0
    for ts, ctl, pl in recs:
        if ctl != VIEWPORT or not pl:
            continue
        done += 1
        if should_cancel():
            raise Cancelled()
        off = 0
        dirty = False
        while off < len(pl):
            t = pl[off]
            if t == 11:
                if off + 33 > len(pl):
                    break
                W, H = struct.unpack_from("<II", pl, off + 1)
                bpp = struct.unpack_from("<I", pl, off + 17)[0] // 8
                hdr_r = struct.unpack_from("<I", pl, off + 21)[0]
                hdr_g = struct.unpack_from("<I", pl, off + 25)[0]
                hdr_b = struct.unpack_from("<I", pl, off + 29)[0]
                fb = bytearray(W * H * bpp)
                prev = None
                off += 33
            elif t == 2:
                if off + 1025 > len(pl):
                    break
                pal = pl[off + 1:off + 1025]
                lut = np.frombuffer(pal, dtype=np.uint8).reshape(256, 4)[:, [2, 1, 0]].copy()
                prev = None
                off += 1025
            elif t == 0:
                if off + 21 > len(pl):
                    break
                x, y, rw, rh, cnt = struct.unpack_from("<5I", pl, off + 1)
                if rw * rh * bpp != cnt or x < 0 or y < 0 or x + rw > W or y + rh > H:
                    break
                s0 = off + 21
                for row in range(rh):
                    s = s0 + row * rw * bpp
                    d = (y + row) * W * bpp + x * bpp
                    fb[d:d + rw * bpp] = pl[s:s + rw * bpp]
                dirty = True
                off += 21 + cnt
            elif t == 33:
                off += 1
            else:
                break
        if dirty:
            cur = bytes(fb)
            if cur != prev:
                prev = cur
                arr = np.frombuffer(cur, dtype=np.uint8)
                if bpp == 1:
                    rgb = lut[arr].reshape(H, W, 3)
                elif bpp == 2:
                    rgb = _rgb_masked(cur, W, H, hdr_r, hdr_g, hdr_b, "<u2")
                elif bpp == 3:
                    rgb = arr.reshape(H, W, 3)[:, :, ::-1]
                else:
                    rgb = arr.reshape(H, W, 4)[:, :3][:, :, ::-1]
                name = "f%06d.png" % len(entries)
                Image.fromarray(rgb).save(os.path.join(frames_dir, name),
                                          compress_level=1)
                entries.append((ts, name))
        if done % 25 == 0:
            on_progress(done / float(max(n_vp, 1)))
    if not entries:
        return None
    end_ts = max(r[0] for r in recs) if recs else entries[-1][0]
    lines = ["ffconcat version 1.0"]
    for i, (ts, name) in enumerate(entries):
        if i + 1 < len(entries):
            dur = (entries[i + 1][0] - ts) / 1000.0
        else:
            dur = (end_ts - ts) / 1000.0
        p = os.path.abspath(os.path.join(frames_dir, name)).replace("\\", "/")
        lines.append("file '%s'" % p)
        lines.append("duration %.3f" % max(dur, 0.001))
    p = os.path.abspath(os.path.join(frames_dir, entries[-1][1])).replace("\\", "/")
    lines.append("file '%s'" % p)
    with open(os.path.join(outdir, "frames.ffconcat"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return dict(w=W, h=H, nframes=len(entries), t0=entries[0][0],
                tlast=end_ts)


def encode_mp4(work, meta, awav, out_path, should_cancel, on_progress):
    total_ms = max(meta["tlast"] - meta["t0"], 1)
    cmd = [FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
           "-i", os.path.join(work, "frames.ffconcat")]
    if awav:
        cmd += ["-i", awav, "-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd += ["-map", "0:v:0"]
    cmd += ["-fps_mode", "vfr",
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
            "-threads", "0"]
    if awav:
        cmd += ["-af", "atrim=start=%.5f,asetpts=PTS-STARTPTS" % (meta["t0"] / 1000.0),
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "1"]
    else:
        cmd += ["-an"]
    cmd += ["-progress", "pipe:1", "-nostats", out_path]

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", errors="replace", **_hidden())
    CURRENT["proc"] = p
    err = []

    def drain():
        for line in p.stderr:
            err.append(line)

    threading.Thread(target=drain, daemon=True).start()
    speed = 0.0
    total_us = float(total_ms) * 1000.0
    for line in p.stdout:
        if should_cancel():
            p.kill()
            raise Cancelled()
        line = line.strip()
        if line.startswith("speed="):
            try:
                speed = float(line.split("=", 1)[1].rstrip("x"))
            except ValueError:
                pass
        elif line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            try:
                us = int(line.split("=", 1)[1])
            except ValueError:
                continue
            if us >= 0:
                on_progress(min(us / total_us, 1.0), speed)
    p.wait()
    CURRENT["proc"] = None
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + "".join(err)[-1200:])
    on_progress(1.0, 0.0)


def convert_one(lrec, out_path, log, should_cancel, on_progress):
    work = tempfile.mkdtemp(prefix="l2m_")
    t0 = time.time()
    st = {"t": 0.0, "frac": 0.0, "phase": t0}
    dur = {"out": 0.0}
    _CURRENT_PART = None

    def emit(remaining, final=False):
        now = time.time()
        elapsed = now - t0
        if final:
            frac, rem = 1.0, 0.0
        else:
            rem = max(1.0, remaining)
            frac = elapsed / (elapsed + rem) if (elapsed + rem) > 0 else 0.0
            frac = min(frac, 0.999)
        if frac < st["frac"]:
            frac = st["frac"]
        st["frac"] = frac
        if final or now - st["t"] >= 0.1:
            st["t"] = now
            on_progress(frac, rem)

    def on_render(f):
        er = time.time() - st["phase"]
        rate = er / f if f > 1e-3 else 0.0
        render_rem = rate * (1 - f) if f > 1e-3 else 0.0
        enc_guess = dur["out"] / 25.0 if dur["out"] else 8.0
        emit(render_rem + enc_guess + 1.5)

    def on_encode(f, speed):
        if speed and speed >= 5:
            st["sp"] = speed if st.get("sp") is None else 0.6 * st["sp"] + 0.4 * speed
        sp = st.get("sp") or 20.0
        sp = max(5.0, min(sp, 150.0))
        emit(max(0.0, dur["out"] * (1.0 - f)) / sp + 0.4)

    try:
        log("Reading %s ..." % os.path.basename(lrec))
        try:
            recs = parse_lrec(lrec)
        except (struct.error, zlib.error, ValueError) as exc:
            raise RuntimeError("This file is not a valid Linktivity recording.") from exc
        if not recs:
            raise RuntimeError("This file is not a valid Linktivity recording.")
        vps = [ts for ts, ctl, pl in recs if ctl == VIEWPORT]
        if vps:
            dur["out"] = max(max(r[0] for r in recs) - vps[0], 1) / 1000.0
        log("Saving screen changes ...")
        st["phase"] = time.time()
        meta = render_frames(recs, work, should_cancel, on_render)
        if not meta:
            raise RuntimeError("No screen frames found in this recording.")
        dur["out"] = max(meta["tlast"] - meta["t0"], 1) / 1000.0
        log("  %d screen changes, %dx%d" % (meta["nframes"], meta["w"], meta["h"]))
        if should_cancel():
            raise Cancelled()
        log("Decoding audio ...")
        emit(dur["out"] / 25.0 + 1.5)
        awav = build_audio(recs, work)
        if should_cancel():
            raise Cancelled()
        log("Writing MP4 ...")
        st["phase"] = time.time()
        part = out_path + ".part.mp4"
        _CURRENT_PART = part
        try:
            if os.path.exists(part):
                try:
                    os.remove(part)
                except OSError:
                    pass
            encode_mp4(work, meta, awav, part, should_cancel, on_encode)
            if os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except OSError:
                    pass
            os.replace(part, out_path)
            _CURRENT_PART = None
            emit(0.0, final=True)
            log("Done: %s (%.1f MB)" %
                (os.path.basename(out_path), os.path.getsize(out_path) / 1048576))
        except Exception:
            try:
                if _CURRENT_PART and os.path.exists(_CURRENT_PART):
                    os.remove(_CURRENT_PART)
            except OSError:
                pass
            raise
    finally:
        try:
            if _CURRENT_PART and os.path.exists(_CURRENT_PART):
                os.remove(_CURRENT_PART)
        except OSError:
            pass
        shutil.rmtree(work, ignore_errors=True)

# ================================================================ filenames
INVALID = set('<>:"/\\|?*')
RESERVED = ({"CON", "PRN", "AUX", "NUL"} |
            {"COM%d" % i for i in range(1, 10)} |
            {"LPT%d" % i for i in range(1, 10)})


def validate_name(new):
    for ch in new:
        if ch in INVALID or ord(ch) < 32:
            return False
    return len(new) <= 120


def sanitize_name(name):
    name = "".join(ch for ch in name if ch not in INVALID and ord(ch) >= 32)
    name = name.strip().rstrip(" .")
    if not name:
        name = "recording"
    if name.upper() in RESERVED:
        name += "_"
    return name[:120]


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--convert":
        convert_one(sys.argv[2], sys.argv[3], print, lambda: False,
                    lambda f, e: None)
