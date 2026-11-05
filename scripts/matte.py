#!/usr/bin/env python3
"""Cut a real person out of footage with Robust Video Matting (PeterL1n, resnet50). Local, free, uses the Mac GPU (MPS)
when there is one, CPU otherwise. Replaces fal's Bria background removal (~$0.14 per second of video).

    python3 scripts/matte.py in.mp4 out.webm                          # transparent VP9 webm (yuva420p)
    python3 scripts/matte.py in.mp4 out.webm --feather 30             # fade alpha at left/right/bottom crop edges
    python3 scripts/matte.py in.mp4 out.webm --pad-width 1080         # centre the cutout on a wider transparent canvas
    python3 scripts/matte.py in.mp4 out.mp4 --green                   # opaque green screen (#00B140) mp4 instead
    python3 scripts/matte.py in.mp4 out.mov --prores                  # ProRes 4444 with alpha, for editors that choke on webm

The audio of in.mp4 is carried through when the output container allows it (webm gets Opus, mp4/mov AAC).

FIRST RUN downloads the model code and weights (~110 MB, from GitHub via torch.hub) into tools/torch_hub/ at the engine
root (gitignored). If a copy already sits in the default torch cache (~/.cache/torch/hub) it is used instead and
nothing is downloaded. Needs torch (see requirements.txt: optional, only this tool and syncnet_qa.py need it).

--feather matters when the person is cropped at the frame edge: without it the cut shoulders end in a hard line.
--downsample (default 0.4) is RVM's internal scale; use ~0.25 for 4K, ~0.6 for small face crops.
"""
import argparse
import pathlib
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = "PeterL1n/RobustVideoMatting"


def hub_dir():
    """tools/torch_hub if it has RVM, else the default torch cache if that has it, else tools/torch_hub (download)."""
    import torch
    local = ROOT / "tools" / "torch_hub"
    default = pathlib.Path(torch.hub.get_dir())
    for d in (local, default):
        if (d / "PeterL1n_RobustVideoMatting_master").exists() and (d / "checkpoints" / "rvm_resnet50.pth").exists():
            return d
    local.mkdir(parents=True, exist_ok=True)
    print(f"first run: downloading Robust Video Matting (~110 MB) into {local}", file=sys.stderr)
    return local


def probe(src, entries):
    return subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                    f"stream={entries}", "-of", "csv=p=0", str(src)]).decode().strip()


def has_audio(src):
    return bool(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                         "stream=index", "-of", "csv=p=0", str(src)]).decode().strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=pathlib.Path)
    ap.add_argument("out", type=pathlib.Path)
    ap.add_argument("--feather", type=int, default=0, help="px of alpha fade at left, right and bottom edges")
    ap.add_argument("--pad-width", type=int, default=0, help="centre on a transparent canvas this wide")
    ap.add_argument("--green", action="store_true", help="opaque green-screen mp4 instead of alpha")
    ap.add_argument("--prores", action="store_true", help="ProRes 4444 .mov with alpha")
    ap.add_argument("--downsample", type=float, default=0.4)
    ap.add_argument("--cpu", action="store_true", help="force CPU")
    a = ap.parse_args()

    import torch
    torch.hub.set_dir(str(hub_dir()))
    dev = "cpu" if a.cpu or not torch.backends.mps.is_available() else "mps"
    if dev == "cpu" and torch.cuda.is_available() and not a.cpu:
        dev = "cuda"
    model = torch.hub.load(REPO, "resnet50", trust_repo=True).eval().to(dev)

    W, H = map(int, probe(a.src, "width,height").split(",")[:2])
    fps = probe(a.src, "r_frame_rate")
    OW = max(W, a.pad_width)
    X0 = (OW - W) // 2
    audio = has_audio(a.src)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(a.src), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    ain = ["-i", str(a.src), "-map", "0:v", "-map", "1:a"] if audio else []
    if a.green:
        venc = ["-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p"] + (["-c:a", "aac", "-b:a", "192k"] if audio else [])
        pix = "rgb24"
    elif a.prores:
        venc = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"] + (["-c:a", "aac"] if audio else [])
        pix = "rgba"
    else:
        venc = ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "22", "-row-mt", "1",
                "-auto-alt-ref", "0"] + (["-c:a", "libopus"] if audio else [])
        pix = "rgba"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", pix, "-s", f"{OW}x{H}",
                            "-r", fps, "-i", "-", *ain, *venc, *(["-shortest"] if audio else []), str(a.out)],
                           stdin=subprocess.PIPE)
    edge = None
    if a.feather:
        x, y = np.arange(W), np.arange(H)
        edge = np.minimum(np.clip(np.minimum(x, W - 1 - x) / a.feather, 0, 1)[None, :],
                          np.clip((H - 1 - y) / a.feather, 0, 1)[:, None])
    green = np.array([0, 177, 64], np.float32)
    rec, n = [None] * 4, 0
    with torch.no_grad():
        while True:
            buf = dec.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                break
            img = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            t = torch.from_numpy(img.copy()).to(dev).permute(2, 0, 1)[None].float() / 255
            fgr, pha, *rec = model(t, *rec, downsample_ratio=a.downsample)
            al = pha[0, 0].clamp(0, 1).cpu().numpy()
            if edge is not None:
                al = al * edge
            if a.green:
                frame = (img * al[..., None] + green * (1 - al[..., None])).astype(np.uint8)
                if OW != W:
                    canvas = np.tile(green.astype(np.uint8), (H, OW, 1)); canvas[:, X0:X0 + W] = frame; frame = canvas
            else:
                frame = np.dstack([img, (al * 255 + 0.5).astype(np.uint8)])
                if OW != W:
                    canvas = np.zeros((H, OW, 4), np.uint8); canvas[:, X0:X0 + W] = frame; frame = canvas
            enc.stdin.write(frame.tobytes())
            n += 1
    enc.stdin.close(); enc.wait(); dec.wait()
    if enc.returncode:
        sys.exit(f"ffmpeg encode failed ({enc.returncode})")
    print(f"matted {n} frames on {dev} -> {a.out}")


if __name__ == "__main__":
    main()
