#!/usr/bin/env python3
"""Lip-sync real footage of a person to a new read with sync.so Lipsync v2 Pro on fal.

ALWAYS sync.so (fal-ai/sync-lipsync/v2/pro). Never LatentSync: its mouths drift and never close on p/b/m.

    python3 scripts/lipsync.py --video phone_take.mov --audio read.wav --out synced.mp4
    python3 scripts/lipsync.py --video take.mov --audio read.wav --start 124.8 --crop 1238:2200:101:0 --out synced.mp4
    python3 scripts/lipsync.py --video take.mov --audio read.wav --out synced.mp4 --dry-run     # pre-encode only, no upload

Steps:
  1. pre-encode: from --start, cut (read length + --lead + --tail) seconds of the footage, optional --crop W:H:X:Y,
     scale to --size (1080x1920), --fps (25; sync.so consumes frames one-for-one at 25, see guide/LIPSYNC.md), libx264 crf 21, no audio. A raw phone file is too big and the upload
     times out; this keeps it to a few MB.
  2. pad the read: --lead seconds of silence in front (the mouth needs a beat to start), padded to the clip length.
  3. upload both, run sync.so with sync_mode cut_off, poll, and DOWNLOAD IMMEDIATELY (fal result URLs expire).
  4. remux: the synced picture at --size/--fps, crf 16, with the padded read as AAC 48 kHz.

Rules that came from shipped ads:
  - Pick the stretch of footage (--start) where the face is steady and frontal; the whole clip is one continuous
    stretch, never looped or ping-ponged (a looped nodding stretch was rejected on sight).
  - Feed HD footage. Do not upscale a low-res crop into sync.so.
  - After: syncnet_qa.py for timing, matte.py for a cutout.

Cost: about $5 per minute of output on sync.so v2 pro. Reads FAL_KEY (env, then .env at the engine root).
"""
import argparse
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

EP = "fal-ai/sync-lipsync/v2/pro"


def sh(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(p)]).decode().strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=pathlib.Path, help="real footage of the person talking to camera")
    ap.add_argument("--audio", required=True, type=pathlib.Path, help="the new read (wav)")
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--start", type=float, default=0.0, help="seconds into --video where the usable face stretch starts")
    ap.add_argument("--crop", help="ffmpeg crop W:H:X:Y applied before scaling, e.g. 1238:2200:101:0")
    ap.add_argument("--size", default="1080x1920", help="WxH of the upload and the output")
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--crf", type=int, default=21, help="pre-encode quality (21 keeps the upload small)")
    ap.add_argument("--lead", type=float, default=0.15, help="seconds of silence before the read")
    ap.add_argument("--tail", type=float, default=0.5, help="extra seconds of picture after the read")
    ap.add_argument("--sync-mode", default="cut_off", help="sync.so sync_mode (cut_off, loop, bounce...). cut_off is the proven one")
    ap.add_argument("--work", type=pathlib.Path, help="folder for intermediates (default: next to --out)")
    ap.add_argument("--dry-run", action="store_true", help="pre-encode and pad only; no upload, no spend")
    a = ap.parse_args()

    W, H = a.size.lower().split("x")
    work = a.work or a.out.parent / (a.out.stem + "_work")
    work.mkdir(parents=True, exist_ok=True)
    secs = round(dur(a.audio) + a.lead + a.tail, 2)
    have = dur(a.video) - a.start
    if have < secs:
        sys.exit(f"footage from {a.start}s has {have:.1f}s but the read needs {secs:.1f}s. "
                 "Pick an earlier --start, get a longer take, or shorten the script. Never loop footage.")

    base = work / "base.mp4"
    vf = ([f"crop={a.crop}"] if a.crop else []) + [f"scale={W}:{H}:flags=lanczos", f"fps={a.fps}"]
    sh("ffmpeg", "-y", "-v", "error", "-ss", a.start, "-i", a.video, "-t", secs, "-an", "-vf", ",".join(vf),
       "-c:v", "libx264", "-crf", a.crf, "-pix_fmt", "yuv420p", base)
    pad = work / "read_padded.wav"
    sh("ffmpeg", "-y", "-v", "error", "-i", a.audio, "-af", f"adelay={int(a.lead * 1000)}:all=1,apad", "-t", secs,
       "-ar", "48000", pad)
    mb = base.stat().st_size / 1e6
    print(f"pre-encoded {base} ({mb:.1f} MB, {secs}s) and {pad}")
    payload = {"video_url": "<upload base.mp4>", "audio_url": "<upload read_padded.wav>", "sync_mode": a.sync_mode}
    if a.dry_run:
        print(json.dumps({"endpoint": EP, "payload": payload, "est_cost_usd": round(secs / 60 * 5, 2)}, indent=1))
        return

    import fal
    tok = fal.token()
    payload.update(video_url=fal.upload(base, tok), audio_url=fal.upload(pad, tok))
    out = fal.run(EP, payload, tok, timeout=3600)
    v = out.get("video")
    url = v.get("url") if isinstance(v, dict) else (v or (fal.urls(out) or [None])[0])
    if not url:
        sys.exit(f"no video url in response: {json.dumps(out)[:300]}")
    raw = work / "sync_raw.mp4"
    fal.download(url, raw)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    sh("ffmpeg", "-y", "-v", "error", "-i", raw, "-i", pad, "-vf", f"scale={W}:{H},fps={a.fps}", "-map", "0:v", "-map", "1:a",
       "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-shortest", a.out)
    print(f"{a.out}  {dur(a.out):.2f}s  (raw sync.so file kept at {raw})")
    print("next: syncnet_qa.py for timing, then matte.py for a cutout")


if __name__ == "__main__":
    main()
