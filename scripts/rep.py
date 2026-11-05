#!/usr/bin/env python3
"""Minimal Replicate runner: create a prediction, poll, return output URLs.

Usage:
  python3 rep.py <owner/model> '<json input>' [outfile]

Reads REPLICATE_API_TOKEN from the environment first, falling back to .env at
the repo root. The env var lets a per-client project scope its own billing.
"""
import json
import os
import sys
import time
import urllib.request

API = "https://api.replicate.com/v1"


def token():
    tok = os.environ.get("REPLICATE_API_TOKEN")
    if tok:
        return tok.strip()
    env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    with open(env) as f:
        for line in f:
            if line.startswith("REPLICATE_API_TOKEN="):
                val = line.split("=", 1)[1].strip()
                if val:
                    return val
    sys.exit("REPLICATE_API_TOKEN not set in the environment or .env at the repo root")


def call(url, tok, data=None):
    req = urllib.request.Request(url, method="POST" if data else "GET")
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Content-Type", "application/json")
    # Cloudflare returns error 1010 to urllib's default user-agent on this host.
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
    body = json.dumps(data).encode() if data else None
    with urllib.request.urlopen(req, body) as r:
        return json.load(r)


def run(model, payload):
    tok = token()
    pred = call(f"{API}/models/{model}/predictions", tok, {"input": payload})
    pid = pred["id"]
    print(f"prediction {pid} ...", file=sys.stderr)
    while pred["status"] not in ("succeeded", "failed", "canceled"):
        time.sleep(3)
        pred = call(f"{API}/predictions/{pid}", tok)
        print(f"  {pred['status']}", file=sys.stderr)
    if pred["status"] != "succeeded":
        sys.exit(f"FAILED: {pred.get('error')}")
    return pred


def main():
    model, payload = sys.argv[1], json.loads(sys.argv[2])
    pred = run(model, payload)
    out = pred["output"]
    urls = [out] if isinstance(out, str) else out
    for u in urls:
        print(u)
    if len(sys.argv) > 3:
        urllib.request.urlretrieve(urls[0], sys.argv[3])
        print(f"saved {sys.argv[3]}", file=sys.stderr)
    m = pred.get("metrics", {})
    if m:
        print(f"time {m.get('predict_time'):.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
