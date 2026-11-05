# The playbook and the failure log

**Read this before any generation spend.** Every line below is a bill somebody
already paid. None of it is theory.

The model-specific rules live with their formats:
`50-generation-replicate.md` for Replicate and image routing,
`60-format-kling-dialogue.md` for Kling. The one-line versions of all of
these are in `RULES.md` at the engine root. This file is the cross-cutting
part: process, audio, post, and the traps that are not about any one model.

---

## Process: the rules that would have saved the most money

**1. Change one variable per round.**

The single most expensive failure in this project was a run where multiple
config variables moved per round. Nothing failed in a way that isolated a cause,
so a whole batch of output became unusable and the entire stage had to be
restarted from the top of the playbook. Whatever you are testing, move one
thing.

**2. Checkpoint one shot end to end before batching.**

Generate one. Take it all the way through assembly, grade, and a human's ears.
Report spend at the checkpoint. Only then batch. A batch of twelve broken clips
costs twelve times as much to discover as one.

**3. Decide the stop-loss in advance.**

Before the first paid call, write down the number of credits or dollars at
which you stop and go back to the operator. Sunk-cost reasoning is very easy
once a run is half done.

**4. Do not diagnose a hang from a status API.**

Measured repeatedly: a finished job reported QUEUING for around eight minutes
after completing in 106 seconds, and a 58-second job reported RUNNING for
fourteen minutes. Credit balances are cached too and did not move across a real
charge. Poll on five-minute-plus intervals, expect long lag, and **never switch
models or resubmit because a job looks stuck.** A model swap was nearly wasted
on a phantom hang.

**5. Download results immediately.** Result URLs expire 24 hours after finish.

**6. Contact sheets of alternatives read as storyboards to a client.**

Stamp options as OPTIONS and sequences as CLIP N START. Never mix the two in one
strip. A client shown a grid of alternatives will read it as a sequence and
approve a film you did not propose.

**7. Study the reference frame by frame before building anything.**

An 0.1-second-step ffmpeg extraction settles in minutes what prompt wording will
never fix. Three physics errors survived multiple rounds of prompt tweaking and
were obvious the moment someone actually stepped the reference.

---

## Grammar of a generated dialogue film

1. **Build from singles.** One readable face per frame, performance aimed just
   off-lens. Two-shots only when the faces are small, such as wides and
   reversals. This is engineering, not style. It is why reference films read as
   film.
2. **One location plate plus an ABCD location sheet anchors every angle.**
   Generate the location sheet *from* a still that has people in it. Models
   render empty rooms unconvincingly.
3. **Character sheets** at front, three-quarter and profile on white, referenced
   in every generation. Demand "PHOTOGRAPH, not illustration" explicitly. Some
   models return drawings for male subjects otherwise.
4. **Face sheet only when the face is visible in the shot.** Passing a character
   sheet while demanding a from-behind framing makes the model resolve the
   contradiction by rendering the face *somewhere*: a duplicate second person,
   or a shadow-figure on the wall. Three rolls failed this way before anyone
   worked out why. For from-behind shots, drop the sheet and let wardrobe carry
   identity.

---

## Audio: the failures that cost the most

**1. Never ship audio no human has heard.**

Every unheard version failed: mismatched voices, robotic delivery, homemade
synth music. Metrics diagnose. They do not clear. This is the single rule most
worth keeping.

**2. Pasted text-to-speech reads as dubbed.**

Measured against a reference: reverb index 0.93 versus 0.56, spectral centroid
597 versus 860 Hz. The fix is native generation, plus per-clip room convolution
at roughly RT60 350ms, plus a high-shelf cut above 3.8 kHz. That closes most of
the gap.

**3. J-cuts and L-cuts plus one continuous room bed make a scene.** Without
them you have a slideshow with sound on it.

**4. Whisper hallucinates on music-only spans.** It will loop a phrase over an
instrumental passage. Probe specific regions. Do not trust a full-pass
transcript across music.

**5. Music licensing.** Found tracks with no clearance evidence ended up under
a whole wave of shipped ads and became an open liability. Anything built with
`scripts/bed.py` is composed in code and has no such exposure. Do not substitute
a track someone found, and record where every bed came from.

---

## Post

**1. Grade in code, not in prompts.**

Flat single wash, lifted blacks, grain. This was the single biggest realism win
of the entire project. AI video is mathematically clean, and clean is the tell.
Real sensors add grain and real lenses do not deliver sculpted contrast.
`scripts/grade.py` does it in one ffmpeg pass.

**2. Grain at 3 to 8 percent.** Most model output already carries some texture,
so stacking more reads as noise rather than as film. The default sits at the low
end for that reason.

**3. Shiny close-ups.** Pull saturation out of the reds and yellows, which is
where skin highlights live. That is what `grade.py --strong` does. It is a blunt
whole-frame stand-in for an eyedropper HSL secondary, so use it only on tight
faces where the shine actually reads.

---

## ffmpeg traps

- **`-loop 1` on still overlays.** Without it the fade sees no timeline and the
  overlay never appears at all.
- **Re-encode hybrids.** A stream-copy mux with mismatched streams produces a
  runaway render.
- **Cap segments with an output-side `-t`.** Input-side trimming will not bound
  the output the way you expect.
- **Join clips with the concat filter, never stream-copy concat.** Stream copy
  of separately encoded clips drifted the audio a few frames per join, which
  read as bad lip-sync. The filter keeps drift under 5 ms.

---

## What still needs a human, and always will

Everything above is mechanisable. These two are not:

1. **Is the performance believable?** No metric answers this.
2. **Does the read sound right?** Word-for-word correctness, scripted pauses,
   and register drops can all be measured. Whether it sounds like a person
   cannot.

Both gates belong to the operator, not to Claude. Every failure in the log
happened when somebody let a green check stand in for one of them.
