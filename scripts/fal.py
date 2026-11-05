#!/usr/bin/env python3
"""Minimal fal.ai runner: submit to the queue, poll, return output URLs.

Usage:
  python3 fal.py <endpoint-id> '<json input>' [outfile]

e.g. python3 fal.py fal-ai/kling-video/v3/standard/text-to-video '{"prompt":"..."}'

Reads FAL_KEY from the environment first, falling back to .env at the repo root.
Mirrors rep.py so callers can swap providers without changing shape.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

QUEUE = "https://queue.fal.run"


def token():
    tok = os.environ.get("FAL_KEY")
    if tok:
        return tok.strip()
    env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env):
        with open(env) as f:
            for line in f:
                if line.startswith("FAL_KEY="):
                    val = line.split("=", 1)[1].strip()
                    if val:
                        return val
    sys.exit("FAL_KEY not set in the environment or .env at the repo root")


def call(url, tok, data=None):
    req = urllib.request.Request(url, method="POST" if data is not None else "GET")
    req.add_header("Authorization", f"Key {tok}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
    body = json.dumps(data).encode() if data is not None else None
    try:
        with urllib.request.urlopen(req, body) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"fal {e.code}: {e.read().decode()[:400]}")


def run(endpoint, payload, tok, timeout=900):
    sub = call(f"{QUEUE}/{endpoint}", tok, payload)
    rid = sub.get("request_id")
    if not rid:
        sys.exit(f"no request_id in response: {json.dumps(sub)[:300]}")
    # the status/response paths drop any sub-path after the model root
    print(f"  request_id {rid}", file=sys.stderr)
    base = "/".join(endpoint.split("/")[:2])
    status_url = sub.get("status_url") or f"{QUEUE}/{base}/requests/{rid}/status"
    response_url = sub.get("response_url") or f"{QUEUE}/{base}/requests/{rid}"

    deadline = time.time() + timeout
    while time.time() < deadline:
        st = call(status_url, tok)
        state = st.get("status")
        if state == "COMPLETED":
            return call(response_url, tok)
        if state in ("FAILED", "CANCELLED", "ERROR"):
            sys.exit(f"fal job {state}: {json.dumps(st)[:400]}")
        print(f"  {state or '...'}", file=sys.stderr)
        time.sleep(5)
    sys.exit(f"timed out after {timeout}s (request {rid})")


def upload(path, tok=None, allow_data_uri=False):
    """Upload a local file to fal's CDN and return its URL.

    Large videos time out on upload, so pre-encode them first (lipsync.py does).
    allow_data_uri=True falls back to an inline data: URI for small files
    (< 10 MB) if the CDN upload fails; never for video.
    """
    import base64, mimetypes, pathlib
    tok = tok or token()
    p = pathlib.Path(path)
    mt = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    try:
        req = urllib.request.Request(
            "https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3",
            data=json.dumps({"content_type": mt, "file_name": p.name}).encode(),
            headers={"Authorization": f"Key {tok}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            init = json.load(r)
        put = urllib.request.Request(init["upload_url"], data=p.read_bytes(), method="PUT",
                                     headers={"Content-Type": mt})
        urllib.request.urlopen(put, timeout=900).close()
        return init["file_url"]
    except Exception as e:
        if allow_data_uri and p.stat().st_size < 10_000_000:
            return f"data:{mt};base64," + base64.b64encode(p.read_bytes()).decode()
        sys.exit(f"fal upload failed for {p.name}: {type(e).__name__}: {str(e)[:200]}")


def download(url, out):
    """Fetch a result URL to disk. fal result URLs expire: call this right after the job completes."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=600) as r, open(out, "wb") as f:
        f.write(r.read())
    return out


def urls(out):
    """Pull any media URLs out of fal's varied response shapes."""
    found = []
    def walk(o):
        if isinstance(o, dict):
            if "url" in o and isinstance(o["url"], str):
                found.append(o["url"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(out)
    return found


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    endpoint, payload = sys.argv[1], json.loads(sys.argv[2])
    out = run(endpoint, payload, token())
    got = urls(out)
    if len(sys.argv) > 3 and got:
        req = urllib.request.Request(got[0])
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req) as r, open(sys.argv[3], "wb") as f:
            f.write(r.read())
        print(sys.argv[3])
    for u in got:
        print(u)
    if not got:
        print(json.dumps(out)[:500])


if __name__ == "__main__":
    main()
