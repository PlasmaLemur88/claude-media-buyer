#!/usr/bin/env python3
"""Check that a voice read says the script, word for word, before anyone listens to it or pays to lip-sync it.

    python3 scripts/readcheck.py read.wav --script script.txt
    python3 scripts/readcheck.py read.wav --script script.txt --words words.json          # reuse an existing transcript
    python3 scripts/readcheck.py read.wav --script script.txt --save-words words.json     # keep Whisper's word timings
    python3 scripts/readcheck.py read.wav --script script.txt --alt "twelve thousand|two thousand"
    python3 scripts/readcheck.py take1.wav take2.wav take3.wav --script script.txt       # rank takes, best first

What it does:
  1. Whisper word-level transcript of the read (openai-whisper, --model small by default; local, free).
     --words takes a list of {"w","s","e"} (the timings.py format) instead and skips Whisper.
  2. Normalises both sides so transcription artefacts are not reported: case, punctuation, hyphens, "A.I." -> "ai",
     apostrophes, and NUMBERS BY VALUE ("$12,480", "12 ,480 dollars" and "twelve thousand four hundred eighty
     dollars" all compare equal; Whisper writes "250 ,000" and "100 %").
  3. Diffs script against heard and prints every MISSING, EXTRA and CHANGED run with its time in the read.
     A run that touches a number is flagged NUMBER: those are the slips that cost money ("two thousand" said
     where the script has "twelve thousand").
  4. --alt "A|B|C": A must appear in the script (case-insensitive, as written there). The sentence holding it is
     located in the read, clipped, and Whisper scores how likely the audio is to say that sentence with A, with B,
     with C (teacher-forced log-probability; higher = more likely what was said). Use it when the transcript alone is
     ambiguous about a word that matters. Repeat --alt for several words.
  --say-as brands/x/say_as.json: the same {"Spelling": "SaidAs"} map voice.py used; both spellings are accepted.
  --ignore word [word ...]: names Whisper spells its own way; differences on them are not counted.

Prints the match ratio, speech end and words per minute. Exit code = number of flagged runs (capped at 99) for the
first file, so it drops into a shell loop. With several files, it ranks them (fewest flags, then best ratio).
"""
import argparse
import difflib
import json
import pathlib
import re
import sys

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
NUMWORDS = set(ONES + TENS + ["hundred", "thousand", "million", "billion", "percent", "dollars", "point"])


def spell(n):
    """int -> words, no 'and' (so 'five hundred seventy')."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + spell(n % 100))
    for size, name in ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= size:
            return spell(n // size) + " " + name + ("" if n % size == 0 else " " + spell(n % size))


def norm_text(s, say_as=None):
    s = s.lower()
    for spelled, said in (say_as or {}).items():
        s = re.sub(rf"\b{re.escape(said.lower())}\b", spelled.lower(), s)
    s = s.replace("a.i.", "ai").replace("’", "'")
    s = re.sub(r"(\d)\s*,\s*(\d{3})\b", r"\1\2", s)          # "12 ,480" and "12,480" -> 12480
    s = re.sub(r"(\d)\s*,\s*(\d{3})\b", r"\1\2", s)          # twice for millions
    s = re.sub(r"(\d)\s+%", r"\1%", s)

    def money(m):
        num = m.group(1)
        mult = {"k": " thousand", "m": " million", "b": " billion"}.get((m.group(2) or "").lower(), "")
        return f" {num}{mult} dollars "
    s = re.sub(r"\$\s*(\d+(?:\.\d+)?)\s*([kmb])?\b", money, s)
    s = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1 percent", s)

    def digits(m):
        t = m.group(0)
        if "." in t:
            a, b = t.split(".", 1)
            return f" {spell(int(a))} point {' '.join(ONES[int(c)] for c in b)} "
        return f" {spell(int(t))} "
    s = re.sub(r"\d+(?:\.\d+)?", digits, s)
    s = re.sub(r"\b(hundred|thousand|million|billion) and\b", r"\1", s)   # "five hundred and seventy"
    s = s.replace("-", " ").replace("'", "")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return s.split()


SCALE = {"hundred", "thousand", "million", "billion"}


def token_pass(toks, owner=None):
    """Rules that span words, applied after per-word normalisation so the heard side gets them too:
    "a hundred" == "one hundred", "five hundred and seventy" == "five hundred seventy"."""
    owner = owner if owner is not None else list(range(len(toks)))
    out, own = [], []
    for i, t in enumerate(toks):
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        if t == "a" and nxt in SCALE:
            t = "one"
        if t == "and" and out and out[-1] in SCALE and nxt in NUMWORDS:
            continue
        out.append(t); own.append(owner[i])
    return out, own


def transcribe(path, model_name):
    import whisper
    m = whisper.load_model(model_name)
    r = m.transcribe(str(path), word_timestamps=True, language="en", fp16=False)
    words = [{"w": w["word"].strip(), "s": round(float(w["start"]), 3), "e": round(float(w["end"]), 3)}
             for seg in r["segments"] for w in seg.get("words", [])]
    return words, m


def merge_split_numbers(words):
    """Whisper splits "250,000" into "250" + ",000", "100%" into "100" + "%", "$250" into "$" + "250". Glue them back."""
    out = []
    for w in words:
        t = w["w"].strip()
        if out and (re.fullmatch(r",?\d{3}[.,!?]?", t) and re.search(r"\d,?$", out[-1]["w"]) and t.startswith(",")
                    or re.fullmatch(r"%[.,!?]?", t) or re.fullmatch(r"\$", out[-1]["w"].strip())):
            out[-1] = {"w": out[-1]["w"].strip() + t, "s": out[-1]["s"], "e": w["e"]}
        else:
            out.append(dict(w, w=t))
    return out


def heard_tokens(words, say_as):
    toks, owner = [], []
    for i, w in enumerate(words):
        for t in norm_text(w["w"], say_as):
            toks.append(t); owner.append(i)
    return toks, owner


def check(path, script, a, say_as, model=None):
    if a.words and len(a.reads) == 1:
        words = json.loads(pathlib.Path(a.words).read_text())
    else:
        words, model = transcribe(path, a.model)
    words = merge_split_numbers(words)
    if a.save_words and len(a.reads) == 1:
        pathlib.Path(a.save_words).write_text(json.dumps(words, indent=1))
    ref, _ = token_pass(norm_text(script, say_as))
    hyp, owner = token_pass(*heard_tokens(words, say_as))
    ignore = {t for w in (a.ignore or []) for t in norm_text(w)}
    sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
    flags = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        r, h = ref[i1:i2], hyp[j1:j2]
        if ignore and set(r + h) <= ignore:
            continue
        if j1 < len(owner):
            t = words[owner[min(j1, len(owner) - 1)]]["s"]
        else:
            t = words[-1]["e"] if words else 0.0
        kind = {"delete": "MISSING", "insert": "EXTRA", "replace": "CHANGED"}[op]
        num = any(x in NUMWORDS for x in r + h)
        flags.append({"kind": kind, "number": num, "t": round(t, 2), "script": " ".join(r), "heard": " ".join(h)})
    end = words[-1]["e"] if words else 0.0
    start = words[0]["s"] if words else 0.0
    res = {"file": str(path), "ratio": round(sm.ratio(), 4), "flags": flags, "speech_start": start, "speech_end": end,
           "wpm": round(len(words) / max(end - start, 0.01) * 60), "heard": " ".join(w["w"] for w in words)}
    if a.alt:
        res["alts"] = [score_alt(path, script, spec, words, ref, hyp, owner, model, a) for spec in a.alt]
    return res, model


def score_alt(path, script, spec, words, ref, hyp, owner, model, a):
    import numpy as np
    import torch
    import whisper
    from whisper.tokenizer import get_tokenizer
    alts = [x.strip() for x in spec.split("|") if x.strip()]
    first = alts[0]
    sents = re.split(r"(?<=[.?!])\s+", script.strip())
    sent = next((s for s in sents if first.lower() in s.lower()), None)
    if sent is None:
        return {"alt": spec, "error": f"'{first}' is not in the script as written"}
    # where the sentence sits in the normalised script
    k = sents.index(sent)
    before = len(token_pass(norm_text(" ".join(sents[:k])))[0]) if k else 0
    n = len(token_pass(norm_text(sent))[0])
    sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
    js = [b.b + (i - b.a) for b in sm.get_matching_blocks() for i in range(b.a, b.a + b.size) if before <= i < before + n]
    if js:
        t0 = max(0.0, words[owner[min(js)]]["s"] - 0.3)
        t1 = words[owner[max(js)]]["e"] + 0.4
    else:
        t0, t1 = 0.0, words[-1]["e"] if words else 30.0
    if t1 - t0 > 30:
        return {"alt": spec, "error": f"sentence spans {t1 - t0:.1f}s; Whisper scores 30 s at most"}
    model = model or whisper.load_model(a.model)
    audio = whisper.load_audio(str(path))[int(t0 * 16000):int(t1 * 16000)]
    mel = whisper.log_mel_spectrogram(whisper.pad_or_trim(audio), n_mels=model.dims.n_mels).to(model.device)
    tok = get_tokenizer(model.is_multilingual, num_languages=model.num_languages, language="en", task="transcribe")
    with torch.no_grad():
        feats = model.embed_audio(mel[None])
        out = []
        for alt in alts:
            text = re.sub(re.escape(first), alt, sent, count=1, flags=re.I)
            prefix = list(tok.sot_sequence_including_notimestamps)
            body = tok.encode(" " + text.strip()) + [tok.eot]
            seq = torch.tensor([prefix + body[:-1]], device=model.device)
            lp = torch.log_softmax(model.logits(seq, feats)[0].float(), dim=-1)
            tgt = body
            scores = [lp[len(prefix) - 1 + i, t].item() for i, t in enumerate(tgt)]
            out.append({"wording": alt, "logprob": round(float(np.sum(scores)), 3), "per_token": round(float(np.mean(scores)), 3)})
    out.sort(key=lambda x: -x["logprob"])
    margin = out[0]["logprob"] - out[1]["logprob"] if len(out) > 1 else None
    return {"alt": spec, "sentence": sent, "window": [round(t0, 2), round(t1, 2)], "ranked": out,
            "best": out[0]["wording"], "margin": round(margin, 3) if margin is not None else None,
            "script_wording_wins": out[0]["wording"] == first}


def report(res):
    print(f"\n=== {res['file']}")
    print(f"heard: {res['heard']}")
    print(f"match {res['ratio']:.3f} · speech {res['speech_start']:.2f}-{res['speech_end']:.2f}s · {res['wpm']} wpm · "
          f"{len(res['flags'])} flag(s)")
    for f in res["flags"]:
        tag = f"{f['kind']}{' NUMBER' if f['number'] else ''}"
        print(f"  {f['t']:7.2f}s  {tag:15s} script: {f['script'] or '-':30s} heard: {f['heard'] or '-'}")
    for al in res.get("alts", []):
        if "error" in al:
            print(f"  ALT {al['alt']}: {al['error']}"); continue
        verdict = "OK, the script wording scores best" if al["script_wording_wins"] else f"SLIP? audio scores closer to '{al['best']}'"
        print(f"  ALT {al['alt']}  window {al['window'][0]}-{al['window'][1]}s  -> {verdict} (margin {al['margin']})")
        for r in al["ranked"]:
            print(f"      {r['logprob']:9.3f}  {r['wording']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reads", nargs="+", type=pathlib.Path, help="wav/mp3/mp4 read(s) to check")
    ap.add_argument("--script", required=True, type=pathlib.Path, help="the text the read should say")
    ap.add_argument("--words", help="existing word timings JSON [{w,s,e}] (single read only); skips Whisper")
    ap.add_argument("--save-words", help="write Whisper's word timings here (single read only)")
    ap.add_argument("--model", default="small", help="whisper model (tiny, base, small, medium...)")
    ap.add_argument("--alt", action="append", help='"script wording|alternative|..." to score against the audio')
    ap.add_argument("--say-as", help="the pronunciation map given to voice.py")
    ap.add_argument("--ignore", nargs="*", help="words whose spelling differences are not counted")
    ap.add_argument("--json", help="write the full result(s) here")
    a = ap.parse_args()
    script = a.script.read_text()
    say_as = json.loads(pathlib.Path(a.say_as).read_text()) if a.say_as else None
    results, model = [], None
    for p in a.reads:
        res, model = check(p, script, a, say_as, model)
        report(res)
        results.append(res)
    if len(results) > 1:
        rank = sorted(results, key=lambda r: (len(r["flags"]), -r["ratio"]))
        print("\nRANK (fewest flags, then best match):")
        for i, r in enumerate(rank, 1):
            print(f"  {i}. {r['file']}  flags {len(r['flags'])}  match {r['ratio']:.3f}  {r['wpm']} wpm")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(results if len(results) > 1 else results[0], indent=1))
    sys.exit(min(len(results[0]["flags"]), 99))


if __name__ == "__main__":
    main()
