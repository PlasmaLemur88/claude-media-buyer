# Voice and music

Everything that makes sound in a motion-graphics ad: which voice route to use,
how to write a script so the voice reads it right, the checks that catch a bad
take before anyone listens, how a take gets into a render, and the music bed.

The one-line versions of these rules are in `RULES.md` sections 2 and 5. This
file is the depth behind them. For a real person talking to camera with
lip-sync, read `guide/LIPSYNC.md` instead; this file covers the read itself.

---

## 0. The rule that outranks everything else

**No audio ships that a human has not listened to, end to end, on headphones.**

Not "the transcript matched". Not "the checks passed". Every unheard version
that was ever delivered failed: mismatched voices, robotic delivery, homemade
synth music. In one early session six of eight takes had a defect that would
otherwise have shipped: phantom repeated phrases, dropped words, an inserted
contraction that reversed a line's meaning, and rising terminals on statements.

The checks in section 4 exist so the human listens to fewer takes, not so they
listen to none. They throw out the provably broken takes, which leaves ears one
question no script can answer: does this sound like a person?

---

## 1. Pick a route

**Route zero: reuse an existing read.** Free, and always the first choice for a
format test. If you are testing a new format against an old ad, the new cut
must play the *same audio file* as the old one, not a re-roll of the same words.
Two rolls of one script are not the same take, and the test stops being a test.

Otherwise, `scripts/voice.py` reads the whole script in one call on any of
five hosted routes, and Chatterbox runs locally.

| Route | Command | Pace control | Use it for | Watch out for |
|---|---|---|---|---|
| Gemini TTS | `voice.py gemini --voice Fenrir --style "..."` | style prompt; `--speed` is applied locally with atempo | the default narrator; prebuilt voices (Fenrir, Charon, Puck, Zephyr...) | no native speed; say the pace in the style prompt ("brisk, natural, no pauses") |
| MiniMax Speech on fal | `voice.py minimax --voice <voice_id> --speed 1.1` | native, 0.5-2.0 | a stock voice with reliable speed | pick the voice by listening to a sample first |
| ElevenLabs v3 on fal | `voice.py elevenlabs --voice Charlie` | the flag exists but was measured as ignored (about 2 words/s) | stock ElevenLabs voices without an ElevenLabs account | speed it up afterwards if it drags |
| Seed Audio clone on fal | `voice.py seed-clone --ref 30s.wav`, then `voice.py seed --voice <speaker_id>` | native | a specific person's voice, **with their written consent** | pace varies run to run at the same speed: draw 3-6 takes and keep the cleanest |
| Seedance, audio only | `voice.py seedance --voice "An American man in his thirties, calm"` | none; speed up afterwards | the most natural-sounding read, for scripts that fit one clip | caps at about 30 s, mints a new voice per clip (so a long script cannot be stitched from two), priced as video; with `--ref-image` use a text-free image, a take once read a reference page aloud |
| Chatterbox, local | not wrapped by the engine; a normal `pip install chatterbox-tts` | `cfg_weight` (see 2.3) | free, offline, cloning from a short reference clip | stochastic, every roll differs; the model takes about a minute to load, so generate several takes per load |

Before planning around any route, confirm its key works with one free or
cheapest call (`--dry-run` prints the payload and spends nothing; `python3
scripts/doctor.py` checks the keys). Dead keys and empty balances are common.
All fal routes read `FAL_KEY`; Gemini reads `GEMINI_API_KEY`; both come from
the environment first, then `.env` at the engine root.

**Real people.** A real phone recording of the person reading the script beats
any clone, every time. Clone a voice only with the person's written consent and
after they have heard the exact files. Some people refuse any AI version of
themselves, voice or face; the active brand's `BRAND-GUIDE.md`
(`brands/<slug>/`) says who. Ask before planning around a clone.

`voice.py` output is always a 48 kHz mono wav, loudness-normalised to -16 LUFS
(`--loudness` to change it, `--trim` strips leading and trailing silence,
`--raw` keeps the provider's file beside it).

---

## 2. Writing a script the voice will read right

This is the most transferable part of the voice layer. Every rule below came
from a take that sounded wrong while every word was correct.

### 2.1 One call, the whole script

Never generate line by line. Energy and pitch drift between calls and the ear
hears the seams. Read the whole script once with pause markers, then cut it at
the pauses using Whisper word timestamps, keeping about 70 ms of air at every
cut.

### 2.2 Punctuation is a prosody control, not typography

- **A hard stop makes a sentence land.** The terminal falls, which is what makes
  a statement sound sure of itself.
- **An ellipsis between two sentences breaks that.** The model treats the pair
  as one continuing utterance and the first sentence never lands. That caused a
  measured +35 Hz rise on a statement in one take. The fix is a hard stop.
- **An ellipsis inside a sentence, for a beat, is fine.** That is what they are
  for. "You already know... you're the bottleneck."
- **A comma versus a full stop is a real choice.** "You're a founder, and you
  already know" and "You're a founder. And you already know" are two different
  deliveries. Do not merge near-identical scripts that differ only in
  punctuation; the difference was tuned on purpose.
- **Ellipses are pacing marks for the model, not text the viewer sees.** In the
  word-by-word formats the display reads from Whisper timings, so the beat an
  ellipsis creates in the audio is what spaces the words on screen.

### 2.3 Tuning knobs (Chatterbox) and why each moves the way it does

Chatterbox has two knobs. Every value that shipped came out of a measured
failure:

- **`exaggeration`**: pitch and emphasis range. **Lower is flatter and less prone
  to rising terminals.**
- **`cfg_weight`**: guidance. **Lower is slower and more deliberate**, but too
  low and the read drifts.

| Setting | What it did |
|---|---|
| 0.50 / 0.25 (the default feel) | audible uptalk on statement endings: +20.9 Hz and +35.1 Hz on two sentence-final words in one take, and uptalk on the pain line ("...short on hands.") that must never sound unsure |
| 0.35 / 0.25 | slowed the read to 155 wpm and started dropping words |
| 0.40 / 0.25 | the only setting that produced a take with every sentence falling, in one wave; but once also produced a rushed 213 wpm read against 187 in the other bodies |
| 0.32 / 0.36-0.40 | the safe setting for calm reads: flat enough that terminals fall, enough guidance to stay deliberate |

Two consequences:

- **Set both knobs per script, never as a global default.** A silent fallback to
  0.5 is a fallback to the setting measured to cause uptalk.
- **Write down why each script is tuned the way it is**, next to the script. The
  reason is what the next person needs when a take fails.

The hosted routes have their own equivalents: a style prompt for Gemini, speed
for MiniMax and Seed. The same law holds: less drama means fewer rising
endings.

### 2.4 Words the voice gets wrong

- **Spell numbers as spoken.** "Two hundred fifty thousand", not "250,000"; "one
  hundred percent", not "100%"; "one-oh-one", not "101". Engines misread digits,
  and Whisper splits "250,000" into "250" + ",000" and "100%" into "100" + "%".
  Spelling them out keeps both the read and the transcript clean.
- **Pronunciation fixes go in the text sent to the voice only.** `voice.py
  --say-as brands/<slug>/say_as.json` applies a flat `{"Spelling": "SaidAs"}`
  map, whole-word, to the TTS text; captions and on-screen text keep the real
  spelling. Typical entries: "Open A.I.", "S-Q-L", "one-oh-one", or a
  surname respelled the way its owner says it. Check the active brand's guide
  for names the voices misread.
- **Never mention a word in a prompt or style note that the line does not
  contain.** A pronunciation hint for an absent word got spoken aloud.
- **Watch for contractions the model inserts.** "Then you already paid for the
  AI" came back as "you're already paid", which means *you have been
  compensated*. The fix was rewording so no pronoun sits directly before
  "already": "Then the AI is already paid for."
- **Short soft words after a sentence break get eaten.** "Want to go faster?"
  came back "want to wear faster" and "120 faster". "Move" carries more than
  "go", and an ellipsis before it buys room.
- **Jargon abbreviations are risky.** "prior auth" came back "prior rules" and
  "Pryoroth"; the full "prior authorizations" survived.
- **Some sequences repeat themselves.** One brand line ended on
  "...and what to ignore." followed by a brand name that began "How to", and
  four separate takes produced a phantom "how to ignore". When a phrase does this once, expect it again and check every
  take for it.

### 2.5 Pace

- Narrator reads land best around **150-160 wpm**. A person talking to camera
  lands at **2.9-3.5 words/s as played**, with 7 or more real pauses a minute.
  `scripts/pace.py check read.wav words.json` reports both; `pace.py pad`
  lengthens pauses that are too short (0.55 s after a full stop, 0.30 s after a
  comma) without touching the words.
- **Trim long pauses from audio energy, not Whisper timings**, because Whisper
  stretches word timings across silence. Cut interior pauses over about 0.45 s
  down to about 0.25 s.
- **A speed-up applies to voice and picture together** (atempo plus setpts) or
  sync breaks. Re-measure word timings on the sped audio; never divide the old
  ones.

### 2.6 Hook variants: change one thing

When you write a new hook for an existing ad, **only the hook changes**. Every
following sentence stays byte-identical, so the hook is the single variable
under test. Check it **before** generating anything:

```python
import difflib
a, b = open("approved.txt").read().split(), open("new.txt").read().split()
print(round(difflib.SequenceMatcher(None, a, b).ratio(), 3))
for op in difflib.SequenceMatcher(None, a, b).get_opcodes():
    if op[0] != "equal": print(op, " ".join(a[op[1]:op[2]]), "->", " ".join(b[op[3]:op[4]]))
```

A hook rewrite should score above about **0.94**, and the only differences
should be the hook plus any clause that only existed to serve it (a question hook
carries "if the answer is no"; that clause cannot survive when the question does
not). The first time this was skipped, a "new hook" scored 0.573: three body
sentences had been dropped and a line invented, and three takes were generated
and checked for prosody before anyone compared the words.

Also re-run the brand's ban list after every rewrite. Rewrites are where banned
words come back.

---

## 3. Takes

- **Save numbered takes; never overwrite.** `read_t01.wav`, `read_t02.wav`, and
  a note of which one was picked and why. Stochastic models fail on different
  lines each roll: a take that fixes uptalk on one line can add a phantom phrase
  on another, and a good take was once lost by rolling on top of it.
- **Roll three** for any stochastic route (Chatterbox, Seed Audio), rank them
  with `readcheck.py`, then listen to the best one or two.
- **If a take fails, do not fix it in post. Re-roll**, and keep the failed take.
  The exception is a clean interior cut of a phantom repeat, done by hand at
  sample level; if you do it, record the cut points next to the take.
- Take files are usually gitignored because they are large. Back up the picked
  take with the project.

---

## 4. The check chain

Run in this order. Skipping any of them has already cost real work.

```
  script diff (2.6)     before generating anything, for any variant
        |
  voice.py              one call, numbered takes
        |
  readcheck.py          does the read say the script, word for word?
        |
  timings.py            word timings for the render; read the printed transcript
        |
  prosody.py            zero uptalk, no long gaps, no stretched words
        |
  a human listens       outranks everything above
```

### 4.1 `scripts/readcheck.py`: does it say the script?

```bash
python3 scripts/readcheck.py read_t01.wav read_t02.wav read_t03.wav --script script.txt
```

Local Whisper word-level transcript diffed against the script. It normalises
case, punctuation, hyphens and "A.I.", and compares **numbers by value**, so
"$4,250" and "four thousand two hundred fifty dollars" match. It prints
every MISSING, EXTRA and CHANGED run with its time in the read, and flags any run
that touches a number as NUMBER (those are the slips that cost money: "two
thousand" said where the script has "twelve thousand"). With several files it
ranks them, best first. Exit code is the flag count.

- `--alt "twelve thousand|two thousand"` scores which wording the audio
  actually says, for a word that matters and a transcript that is ambiguous.
- `--say-as` takes the same map `voice.py` used, so either spelling passes.
- `--save-words words.json` keeps the word timings.

**When two Whisper model sizes disagree on a word, the audio is bad, not the
transcription.** Use a larger model on prices and numbers ("forty cents"
once came back "$40").

### 4.2 `scripts/timings.py`: word timings for the render

```bash
python3 scripts/timings.py /abs/path/read.wav /abs/path/brands/<slug>/assets/words/<number>.json
```

Writes `[{"w","s","e"}, ...]` and prints the transcript and the last word's
end. Pass absolute paths: relative ones resolve against `scripts/`. **Read the
printed transcript every time.** Whisper mishears brand names ("Mapleworks" as
"Maple works"); the compositions glue split numbers back together, but a misheard
word has to be caught here.

The last word's `e` is what the configs build `voEnd` from (section 5). Re-cut a
read and you must re-run `timings.py` and update `voEnd`.

### 4.3 `scripts/prosody.py`: the uptalk detector

```bash
python3 scripts/prosody.py /abs/path/read.wav /abs/path/words.json
```

This turns "it sounds off but every word is right" into a number. For every
sentence-final word it measures whether pitch rises or falls across the word
(pYIN pitch tracking). A statement should fall. **A rising terminal on a
statement is uptalk**: the line sounds uncertain or like a question, and it is
the most common way a take sounds wrong while the transcript is perfect.
Questions are skipped, since they should rise.

- **Threshold: more than +6 Hz across a sentence-final word is audible uptalk**
  (`UPTALK_HZ = 6.0`).
- It also flags gaps over 0.9 s and words delivered much faster or slower than
  the take's own average, which is how dropped or rushed phrases show up.
- **The fix, both halves together:** regenerate with less drama (lower
  `exaggeration`, a calmer style prompt), **and** replace any ellipsis before
  the offending sentence with a hard stop.

What passing looks like: the callout lines fall clearly, e.g. `you.` -23.2 Hz,
`hands.` -12.8, `bottleneck.` -10.0. What failing looked like: `for.` +20.9 Hz
and `it.` +35.1 Hz on two statements in the same take.

### 4.4 The gate

**Zero uptalk flags, the transcript matches the script word for word, and the
operator has listened to the take. All three.** Then check the finished mp4 the
same way: transcribe the render, not only the take, because a config pointing at
a stale file once shipped an old outro.

---

## 5. Getting a take into a render

The Remotion formats read a brand's audio from `brands/<slug>/assets/audio/` and
its word timings from `brands/<slug>/assets/words/` (served as `brand-active/`).
Copy the picked take there under a clear name and point the ad's entry in
`brands/<slug>/configs.mjs` at it:

```js
vo: "brand-active/audio/vo_101.mp3", // the picked take
bed: "audio/bed_phrygian.wav",    // the music bed
voEnd: 25.1,                      // from timings.py, never guessed
```

**`voEnd`** is where all speech stops, and the end card starts there. Take the
last word's end from `timings.py` and add a little padding (0.16-0.35 s has
been used; paid cuts with an appended outro use exactly last word end + 0.22).
Too low and the end card cuts into the read; too high and the ad ends on silence.
Nothing checks that a re-cut take still matches its `voEnd`, so re-read it every
time the audio changes.

**One shared outro, appended, never rewritten per ad.** When several ads end on
the same offer line (a paid close, say), generate the outro once and append it
to each body in code:

- insert a gap of about **0.55 s** between body and outro so the turn is audible;
- shift the outro's word timings by `body_duration + gap` and append them to the
  body's timings, so captions land without re-running Whisper on the joined file;
- set `bodyEnd` (where the outro starts) and `voEnd` from the merged timings;
- keep the end card length (about 3.2-3.6 s, `endCardSeconds`) identical to the
  composition's.

To change the offer, edit the one outro, regenerate, re-run the joins and
re-render every ad that uses it. Never edit one ad's closing line. Keep the outro
short: it is appended to every ad, so each second costs that many seconds of
runtime. Offer wording comes from the brand files, never from an older ad.

Build and render with `motion-graphics/build.sh` (see the format docs). After
the render, transcribe the mp4 and check it against the script.

---

## 6. Music

### 6.1 Composed beds only

Use a bed you composed or generated with known terms. **Never substitute a track
someone found or supplied.** A paid ad on someone else's music is a liability,
and it is not a one-file fix: when a whole wave used three supplied tracks with
no clearance evidence, every one of those cuts would have needed a re-score.

For AI music services, commercial rights usually depend on the plan that was
active **at the moment of generation**, so "we used service X" is not an answer.
Record the account, plan and date for every generated bed, or do not use it on
a paid ad. Record the source of every bed in the project either way.

### 6.2 `scripts/bed.py`: the composed bed

```bash
python3 scripts/bed.py     # writes motion-graphics/public/audio/bed_phrygian.wav
```

A 10-second cinematic drone in **C Phrygian**, 48 kHz stereo: no percussion, no
melody, a sustained pad over a C pedal. Because it has no downbeat, it loops
under a read of any length and the wrap is inaudible. That property is the
point; keep it if you edit the script. The file is not kept in git: `setup.sh`
and `build.sh` make it when it is missing.

Method worth reusing:

- **The harmony was measured, not guessed.** A per-second FFT of the reference
  ad's audio over 45-400 Hz gave the chord sequence i, bII, III, i, bII. The
  flat second (the Neapolitan bII) gives it unease without a minor-key cliche;
  do not "correct" it.
- **Three detuned voices** (-6, 0, +6 cents) with mild sawtooth harmonics give
  width without buzz; a very low filtered-noise layer gives the pad some breath.
- **Move the filter by crossfading a fixed ladder, never by redesigning it per
  block.** Redesigning a Butterworth filter block by block clicks at every block
  edge (a ~23 Hz ratchet, heard as buzz). Nine fixed cutoffs from 900 to 3200 Hz,
  geometrically spaced, blended with smooth triangular weights, gives movement
  with no discontinuity.
- **The output is normalised, then multiplied by 0.72.** That headroom is for the
  voice and any clip ambience. Do not "fix" the level.

To score to a different reference, redo the FFT on that reference and change the
chord list; the rest of the script stands.

### 6.3 Fitting a bed to a cut

A bed must cover the whole video. Render it at `duration + 0.5 s`; loop it with
`-stream_loop` if it is shorter; fade in 0.8 s and out 0.4 s (short enough that
nothing dies under the end card, long enough to avoid a click):

```bash
DUR=28.3; NEED=$(echo "$DUR + 0.5" | bc)     # video length, and what to render
ffmpeg -y -stream_loop 3 -i bed.wav -t "$NEED" \
  -af "afade=t=in:st=0:d=0.8,afade=t=out:st=$(echo "$DUR-0.4"|bc):d=0.4,loudnorm=I=-19:TP=-2:LRA=9" \
  -c:a libmp3lame -b:a 192k bed_fit.mp3
```

In Remotion the formats loop the bed themselves (`<Audio loop>`), which is safe
only because the beds are drones with no downbeat. If a bed is a little short
for one test arm, loop it; do not borrow a longer track from another ad, because
that adds a second variable to a test whose point is that only one thing moved.

### 6.4 Mixing

**The bed ducks under the voice and lifts for the end card.** Held flat under
speech, it vanishes the moment the voice stops (a measured 12 dB drop), and the
end card plays in near silence. The formats do this with a volume curve keyed
to `voEnd`:

```ts
// motion-graphics/src/AdCaptions.tsx: 0.16 under the read, ramp to 0.55 over 0.6 s
volume={(f) => { const tt = f / fps;
  return tt < c.voEnd ? 0.16 : Math.min(0.55, 0.16 + ((tt - c.voEnd) / 0.6) * 0.39); }}
```

`AdAerialKinetic.tsx` uses the same shape with a per-ad `bedVolume` (default
0.12) ramping to 0.4 over 0.8 s. The word-by-word format (`AdRsvp.tsx`) sits a
little lower; its levels are the `bedUnderVoice` and `bedUnderCard` knobs in
the active brand's `brand.json`. **Verify the lift on the delivered mp4 with `astats`, not on the bed
file**: the bed is flat by construction and the ramp only exists after render.

When ffmpeg does the mix instead of Remotion, duck with a sidechain:

```
[1:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[vo1][vo2];
[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.55[bg];
[bg][vo1]sidechaincompress=threshold=0.04:ratio=9:attack=8:release=380[duck];
[duck][vo2]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95:level=false[a]
```

For a bed over a clip's own ambience with no voice, `amix` the two with
`duration=shortest` so a fixed-length cut ends cleanly.

**Final loudness:** static gain to about **-14 LUFS**, true peak under **-1
dBTP**, limiter with `level=false`. **Never run dynamic `loudnorm` over a finished
mix with a bed**: it rides the music back up in every gap between sentences.
Judge the mix by rendering the voice and bed stems solo and measuring the speech
windows, then listen to the whole thing.
