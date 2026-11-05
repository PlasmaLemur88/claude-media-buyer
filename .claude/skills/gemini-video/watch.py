#!/usr/bin/env python3
"""Ask Gemini to watch a whole video and answer a question about it.

Usage:
  watch.py SOURCE [--prompt TEXT] [--model NAME] [--start 00:10:00] [--end 00:20:00]
           [--fps N] [--low-res] [--keep] [--json]

SOURCE is one of:
  - a local video file
  - a public YouTube URL (sent to Gemini as-is; nothing is downloaded)
  - any other video URL yt-dlp can fetch (Instagram, X, Vimeo...): downloaded, then uploaded
  - a Gemini file name like files/abc123 from an earlier run (skips the upload)

Only the standard library is used. The API key comes from GEMINI_API_KEY, then the
engine's .env, then the `export GEMINI_API_KEY=` line in ~/.bash_profile.
"""
import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com"
DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_PROMPT = (
    "Watch the whole video. Return, with timestamps as HH:MM:SS: "
    "1) a section-by-section breakdown, 2) the strongest moments and why, "
    "3) any on-screen text or graphics worth noting, 4) notable quotes verbatim."
)
YT_RE = re.compile(r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/")


def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    # the engine's own .env, three levels up from .claude/skills/gemini-video/watch.py
    env = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env")
    if os.path.exists(env):
        for line in open(env):
            m = re.match(r"\s*GEMINI_API_KEY=[\"']?([^\"'\s]+)", line)
            if m:
                return m.group(1)
    prof = os.path.expanduser("~/.bash_profile")
    if os.path.exists(prof):
        for line in open(prof):
            m = re.match(r"\s*export\s+GEMINI_API_KEY=[\"']?([^\"'\s]+)", line)
            if m:
                return m.group(1)
    die("GEMINI_API_KEY is not set and was not found in ~/.bash_profile")


def request(method, url, key, body=None, headers=None, timeout=600):
    hdrs = {"x-goog-api-key": key}
    hdrs.update(headers or {})
    data = body
    if isinstance(body, (dict, list)):
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}, r.headers
    except urllib.error.HTTPError as e:
        die(f"{method} {url.split('?')[0]} -> HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")


def hms_to_seconds(s):
    parts = [int(p) for p in s.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, sec = parts
    return h * 3600 + m * 60 + sec


def download(url, workdir):
    out = os.path.join(workdir, "video.%(ext)s")
    cmd = ["yt-dlp", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--merge-output-format", "mp4",
           "-o", out, "--no-playlist", "--quiet", "--no-warnings", url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"yt-dlp failed: {r.stderr.strip()[-600:]}")
    files = [os.path.join(workdir, f) for f in os.listdir(workdir) if f.startswith("video.")]
    if not files:
        die("yt-dlp reported success but wrote no file")
    return files[0]


def upload(path, key):
    size = os.path.getsize(path)
    mime = mimetypes.guess_type(path)[0] or "video/mp4"
    name = os.path.basename(path)
    _, hdrs = request(
        "POST", f"{API}/upload/v1beta/files", key,
        body={"file": {"display_name": name}},
        headers={
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(size),
            "X-Goog-Upload-Header-Content-Type": mime,
        },
    )
    upload_url = hdrs.get("X-Goog-Upload-URL")
    if not upload_url:
        die("upload start returned no X-Goog-Upload-URL")
    print(f"uploading {name} ({size/1e6:.1f} MB)...", file=sys.stderr)
    with open(path, "rb") as fh:
        info, _ = request(
            "POST", upload_url, key, body=fh,
            headers={
                "Content-Length": str(size),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
            },
            timeout=3600,
        )
    f = info.get("file", {})
    fname = f.get("name")
    if not fname:
        die(f"upload finalize returned no file name: {json.dumps(info)[:400]}")
    # Gemini transcodes after upload; wait for ACTIVE.
    waited = 0
    while f.get("state") in (None, "PROCESSING"):
        time.sleep(3)
        waited += 3
        f, _ = request("GET", f"{API}/v1beta/{fname}", key)
        if waited > 1800:
            die(f"{fname} still {f.get('state')} after 30 minutes")
    if f.get("state") != "ACTIVE":
        die(f"{fname} ended in state {f.get('state')}: {json.dumps(f)[:400]}")
    print(f"ready: {fname} (processed in {waited}s)", file=sys.stderr)
    return f["uri"], f.get("mimeType", mime), fname


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--prompt", "-p", default=DEFAULT_PROMPT)
    ap.add_argument("--model", "-m", default=DEFAULT_MODEL)
    ap.add_argument("--start", help="HH:MM:SS, only watch from here")
    ap.add_argument("--end", help="HH:MM:SS, stop watching here")
    ap.add_argument("--fps", type=float, help="frames per second Gemini samples (default 1)")
    ap.add_argument("--low-res", action="store_true", help="cut video tokens ~3x, fine for talking heads")
    ap.add_argument("--keep", action="store_true", help="keep the uploaded file on Gemini (48h) and print its name for follow-ups")
    ap.add_argument("--json", action="store_true", help="print the raw API response")
    a = ap.parse_args()

    key = api_key()
    src = a.source
    tmp = None
    file_name = None

    if src.startswith("files/"):
        f, _ = request("GET", f"{API}/v1beta/{src}", key)
        if f.get("state") != "ACTIVE":
            die(f"{src} is {f.get('state')}; re-upload it")
        file_uri, mime = f["uri"], f.get("mimeType", "video/mp4")
    elif YT_RE.match(src):
        file_uri, mime = src, None
    elif re.match(r"^https?://", src):
        tmp = tempfile.mkdtemp(prefix="gemini-video-")
        print(f"downloading with yt-dlp...", file=sys.stderr)
        file_uri, mime, file_name = upload(download(src, tmp), key)
    else:
        if not os.path.isfile(src):
            die(f"no such file: {src}")
        file_uri, mime, file_name = upload(os.path.abspath(src), key)

    file_part = {"file_data": {"file_uri": file_uri}}
    if mime:
        file_part["file_data"]["mime_type"] = mime
    meta = {}
    if a.start:
        meta["start_offset"] = f"{hms_to_seconds(a.start)}s"
    if a.end:
        meta["end_offset"] = f"{hms_to_seconds(a.end)}s"
    if a.fps:
        meta["fps"] = a.fps
    if meta:
        file_part["video_metadata"] = meta

    body = {"contents": [{"parts": [file_part, {"text": a.prompt}]}]}
    if a.low_res:
        body["generationConfig"] = {"mediaResolution": "MEDIA_RESOLUTION_LOW"}

    t0 = time.time()
    resp, _ = request("POST", f"{API}/v1beta/models/{a.model}:generateContent", key, body=body, timeout=1800)
    dt = time.time() - t0

    if a.json:
        print(json.dumps(resp, indent=2))
    else:
        cands = resp.get("candidates") or []
        if not cands:
            die(f"no candidates in response: {json.dumps(resp)[:800]}")
        text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))
        print(text)
    u = resp.get("usageMetadata", {})
    print(
        f"\n[{a.model} | {dt:.0f}s | tokens in {u.get('promptTokenCount', '?')} "
        f"out {u.get('candidatesTokenCount', '?')} total {u.get('totalTokenCount', '?')}]",
        file=sys.stderr,
    )

    if file_name:
        if a.keep:
            print(f"[kept on Gemini for 48h: {file_name}  (pass it as SOURCE to ask more)]", file=sys.stderr)
        else:
            try:
                request("DELETE", f"{API}/v1beta/{file_name}", key)
            except SystemExit:
                pass
    if tmp:
        subprocess.run(["rm", "-rf", tmp])


if __name__ == "__main__":
    main()
