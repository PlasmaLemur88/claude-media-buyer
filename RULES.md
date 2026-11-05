# Craft rules

Read this every session, before any script, voice or render. Each rule is one
line of what to do, why (the failure that taught it), and how to apply it. They
hold for any brand. Brand facts and brand bans live with the active brand, in
`brands/<slug>/BRAND-GUIDE.md` and `brands/<slug>/brand.json`. Depth lives in
`guide/LIPSYNC.md`, `docs/70-playbook-and-failures.md` and `lib/director.md`.
Where this file and `lib/director.md` disagree about a generation prompt,
`lib/director.md` wins.

## 0. Before any spend

- **Change one variable per round.** Why: a run that moved several settings at once could not isolate a cause and the whole stage restarted. How: name the one thing you are testing before you submit.
- **Take one shot all the way through before batching.** Why: twelve broken clips cost twelve times as much to discover as one. How: generate one, assemble, grade, and get a human to watch it, then batch.
- **Write the stop-loss down first.** Why: sunk cost is easy halfway through a run. How: put the credit or dollar ceiling in the project brief and stop there to ask.
- **Never resubmit because a job looks stuck.** Why: status APIs lag by up to 14 minutes and balances are cached; a model swap was nearly wasted on a phantom hang. How: poll every 5+ minutes; download results as soon as they land (URLs expire in 24 h).
- **"Exhausted balance" or "TOP_UP" means top up, not a bad key.** How: tell the operator; after a top-up retry once a minute or two later, never re-bill finished steps.

## 1. Script and copy

- **Hooks are statements, never questions.** Why: a question reads as low authority and was rejected every time. How: open with a declarative that names the reader's problem. Negation ("Stop...", "Don't...") is fine.
- **Problem, then solution, then product.** Why: copy aimed at product-aware readers undersold to problem-aware ones. How: every opening and bullet names the problem first. Hand over two or three variants for testing, not one polished draft.
- **Headlines are literal.** Why: payoff lines and clever turns ("one afternoon fixes that") were called AI slop. How: a headline names the product, the tool, the time or the price. Cut any line whose only job is a turn of phrase.
- **Plain inventory over persuasion.** Why: "romantic" and clever copy was rejected; buyers need to know exactly what they get. How: list the deliverables in plain words. Pair any platform name with what it is ("our private community, hosted on <platform>"), since viewers do not know the platform by name.
- **Use the operator's exact phrasing.** Why: paraphrasing approved lines made them ask twice. How: copy their words verbatim; change them only if factually wrong, and say so.
- **Keep spoken asides, cut narrator signposts.** Why: a de-AI pass that stripped "But real quick..." made copy worse. How: keep what a person says mid-conversation; cut lines that announce structure ("Here is the week:").
- **No time-relative words.** Why: "today's session" shipped in an ad that runs for months. How: ban "today", "tonight", "this week" unless the ad has an end date.
- **No em dashes, anywhere.** Why: they read as generated. How: grep every script, caption and copy sheet for U+2014 and U+2013 (`grep -nP '\x{2014}|\x{2013}'`) before delivery.
- **Check the script against the approved version before generating a voice.** Why: a rewrite silently dropped three sentences and invented a line, and three takes were vetted before anyone compared words. How: diff the new script against the last approved body; re-run the brand ban list after every rewrite, since rewrites are where banned words come back.
- **Every claim needs a source you can name.** Why: a false offer claim (a wrong item count and term) was copied forward into 46 files. How: numbers come from the brand's source files, never from memory or an older ad; flag anything unsourced in the copy sheet.
- **Write social captions from the transcript, not the title.** Why: captions swapped who asked and who answered, and named things the video never says. How: transcribe per speaker, pull frames where the setting matters, check every number and schedule is true on the publish date.

## 2. Voice

- **One call reads the whole script; cut it by Whisper word timestamps.** Why: per-line calls drift in energy and the ear hears it. How: generate one take with pause markers, cut at the pauses by word timings, keep 70 ms of air at every cut.
- **Routes that work.** Gemini TTS prebuilt voices (pace is set by a style prompt), MiniMax Speech on fal (speed 0.5-2.0), ByteDance Seed Audio voice clone on fal (with consent), Chatterbox locally (stochastic, several takes per line), Seedance text-to-video used for its audio only. ElevenLabs v3 on fal ignores its speed flag (about 2 words/s). How: check `.env` keys with a free call before planning around one; dead keys are common.
- **Seedance voices cap at about 30 s and mint a new voice per clip.** Why: a 110-word script cannot be stitched from two clips. How: Seedance for scripts that fit one clip; a one-call TTS for longer reads. Seedance fills its clip whatever you ask, so pace comes from a speed-up afterwards.
- **Pronunciation fixes go in the TTS text only.** Why: names and brands get misread ("open eyes" for OpenAI, "Anthromic" for Anthropic). How: keep a substitution map (e.g. "Open A.I.", "S-Q-L", or a founder's surname respelled the way they say it) applied to the text sent to the voice; captions and on-screen text keep the real spelling.
- **Never mention a word in a prompt that the line does not contain.** Why: a pronunciation note for an absent word got spoken, and a reference page image got read aloud. How: pronunciation hints only for words in the line; use a plain image as the visual reference.
- **Spell numbers as spoken.** Why: engines misread large dollar figures and course codes like "101". How: write "twelve thousand four hundred eighty dollars" and "one-oh-one" in the TTS text.
- **Pace: speed voice and picture together.** Why: a speed-up on one track alone breaks sync. How: atempo + setpts together. Narrator reads land best around 150-160 wpm; a person talking to camera around 2.9-3.5 words/s as played. Re-measure word timings on the sped audio; do not divide old timings.
- **Trim pauses from audio energy, not Whisper timings.** Why: Whisper's word timings stretch across silence. How: cut interior pauses over 0.45 s to about 0.25 s by measuring room tone vs speech level.
- **Check sentence ends for uptalk.** Why: rising pitch on statements killed several takes. How: run a sentence-final pitch check and listen at every full stop.
- **Save numbered takes; never overwrite.** Why: a good take was destroyed by rolling on top of it. How: `take_01.wav`, `take_02.wav`, and a note of which one was picked and why.
- **Never ship audio no human has heard.** Why: every unheard version failed. Metrics diagnose, they do not clear. How: the operator listens to the final mix end to end before delivery. The one exception is the autopilot exception at the end of this file.

## 3. People on camera

- **A real recording beats any clone.** Why: synthetic presenters were rejected for nodding, flat voice and slow delivery even at normal wpm. How: ask for a phone recording of the script first. Use cloning only with the person's written consent, and show them the exact files before anything runs. Some people refuse any AI version of themselves, voice or face; ask before you plan around one.
- **Lip-sync: sync.so Lipsync v2 Pro only** (`fal-ai/sync-lipsync/v2/pro`, `sync_mode: cut_off`). **Never LatentSync, not even as a fallback.** Why: LatentSync redraws a generic mouth and looked fake on every real face; it only "won" a test on a blurry 304 px tile. How: follow `guide/LIPSYNC.md` for the pipeline.
- **Feed the lip-sync HD, 25 fps, one continuous talking take.** Why: 30 fps made the mouth run behind the head; blurry tiles gave a waxy mouth; stitched clips made the person look like someone else. How: crop around the face, resample to 25 fps, convert to 30 only at the end. Source must be the person TALKING, not listening.
- **Never loop a short clip to fill a read.** Why: a listening clip played forward and back read as nodding over and over. How: find a continuous stretch as long as the voice plus 1.5 s, or get a new recording.
- **Matte locally.** Why: paid video background removal costs about $0.14 per second. How: Robust Video Matting on the local GPU; send to a paid remover only for short clips, and it caps at 30 s per call.
- **Presenter at one size, in a lower corner, on screen from frame 0 to the end.** Why: every departure was sent back (big centred opening, facecam bubble, slow zooms, cut-aways, frame holds). How: about 38-40% of frame width, clear of the Reels action rail; a passing hand is better than a cut or a freeze.
- **End a talking opening 0.25 s after the last word.** Why: silent tails made the presenter visibly shake. How: trim to speech end plus 0.25 s.
- **Never enlarge a tiny meeting tile.** Why: upscaled 150 px tiles read blurry and the platform's name label sits over the mouth. How: crop the tile's full height and cover the recorded name label with your own; never crop through a face.
- **Real attendees get privacy.** Why: customers appear in recordings of live sessions. How: replace their faces with invented ones and put "Attendees' faces and names changed for privacy." on screen. Blurring was rejected.

## 4. Generation

- **A talking generated character is one Seedance text-to-video take per speaker, with the era look in the prompt.** Why: Kling's native audio ran mouths 250-500 ms off and no lip-sync pass saved them. How: voice and mouth from one model, one take.
- **An animated (cartoon) talking character is one Seedance 2.5 image-mode take per speaker, off his approved character sheet, audio on.** Why: Seedance refuses a start frame and a voice reference together, and reference mode swapped the characters' sides, sizes and clothes; Kling's voices failed the accent. How: `docs/65-format-animated-characters.md`, with the prompt blocks copied word for word between episodes.
- **Kling is for silent B-roll.** How: cap a Kling generation at about 3 shots (more garbles dialogue and ignores the shot plan). For single-character shots use the scene still as `first_image`; never feed a location sheet to Omni (it renders the sheet as a shot).
- **fal refuses real faces in Seedance.** Why: image-to-video and reference/edit tasks return `content_policy_violation` on real likenesses, whatever consent exists. How: Seedance only for invented people or voice-only; real people go through a real recording or sync.so.
- **Reference-consistency image work goes to Kling's image models.** Why: Gemini image models silently reject "same person" prompts. How: Kling image (omni) for identity; GPT Image for precision instructions; Gemini for scenes and plates.
- **Face sheet only when the face is visible.** Why: a face sheet on a from-behind shot produced a duplicate person or a shadow figure. How: for from-behind framings drop the sheet; let wardrobe carry identity.
- **Never let a model render UI or text.** Why: garbled letters. How: render a green placeholder and corner-pin the real screenshot in post.
- **Edit the reference frame, do not recreate it.** Why: six recreations drifted the pose and physics; one edit held it. How: image-edit the actual frame, swapping face, wardrobe and room.
- **Step the reference frame by frame before building.** Why: three physics errors survived rounds of prompt tweaks and were obvious at 0.1 s steps. How: `ffmpeg -vf fps=10` into a strip sheet first.
- **Check generated plates at the edges.** Why: models draw frames and borders into plates (a double border shipped twice). How: strip-sheet the outer 130 px of every plate.
- **Grade in code.** Why: clean output is the AI tell; flat wash, lifted blacks and 3-8% grain was the biggest realism win. How: `scripts/grade.py`.

## 5. Editing and layout

- **Join clips with the concat filter, never stream copy.** Why: stream-copy concat of separately encoded clips drifted audio a few frames per join, which read as bad lip-sync. How: `-filter_complex concat`; measured drift stays under 5 ms.
- **ffmpeg traps.** `-loop 1` on still overlays or the fade never shows; re-encode hybrids (stream-copy mux of mismatched streams runs away); cap segments with an output-side `-t`. Do not frame-blend 25 to 30 fps on faces (it doubled nostrils); repeat frames instead.
- **Keep text out of the platform's overlay.** Why: Meta Reels covers the top ~14%, the bottom ~35% and the right icon column. How: on 1080x1920 keep text inside y 290-1240, x 60-940; captions never in the bottom fifth. Captions sit above media so they never cover a face or a slide.
- **No widows.** Why: one word alone on a last line is the first thing a reviewer notices. How: `text-wrap: balance` on HTML text, a widow check after render, and a by-eye check on anything drawn in PIL. Kinetic lines arrive whole on a character budget and never end on a small word.
- **Build every ratio natively.** Why: a 9:16 cropped to 4:5 was "very crowded" and crops decapitate. How: 9:16 for Reels and Stories, 4:5 at 1080x1350 for feed; check the 4:5 on its own.
- **Something readable at frame 0.** Why: most viewers are muted and scrolling. How: the hook text and brand are on screen at frame 0; motion adds, it does not reveal.
- **Mix to a measured target, no dynamic loudnorm over a bed.** Why: loudnorm rode the music back up in every gap. How: sidechain-duck the bed under the voice, static gain to about -14 LUFS, true peak under -1 dBTP, limiter with `level=false`. Judge by rendering stems solo and measuring speech windows.
- **Music: composed or generated beds only.** Why: found tracks carry licensing exposure. How: use `bed.py` or a generated bed; record where it came from and whether its commercial terms were checked.

## 6. Stills and creative direction

- **No typeset-card templates.** Why: clean type on a brand-colour card, and invented app screens, were rejected as "very AI". How: pictures with a world in them: a real screenshot, a photographed object, real session footage, a hand-drawn chart.
- **Start from the winning file.** Why: invented variants were "not variants of what we made". How: open the actual winning ad's pixels, name the persona in the ad, and show original vs variant with what was kept and changed.
- **A competitor port keeps the reference's structure.** Why: ports dropped onto the house card template "look nothing like that"; a near-clone of their colours and wordmark was also rejected. How: put the reference beside the draft and check its three or four defining visual moves are all present. Swap people, facts and accents, never the composition.
- **Show the full competitor set before making versions.** How: gallery first, the operator picks, then build one at a time.
- **Meta groups lookalikes.** Why: headline or colour swaps on one layout scored 0.89-0.91 similar and get spent as one ad. How: real diversity changes layout, footage, type treatment, accent colour and cover.
- **Deliver one version per concept.** Why: side-by-side variants were "too hard to follow". How: one version unless a test is asked for.
- **Stamp contact sheets.** Why: a grid of alternatives read as a storyboard and nearly got a film approved that was never proposed. How: label options as OPTIONS and sequences as CLIP N START; never mix them.
- **Covers from real, unedited frames.** How: platform-native text on the cover, one expression per hook, the big line is what is said first.

## 7. QA (before anyone sees it)

- **Whisper-check every take and every finished mp4 against the script.** Why: takes hallucinate whole sentences and swap words; a rebuild once kept an old outro because a config pointed at a stale file. How: transcribe the raw take, the cut clips and the final render. Use a larger Whisper model on prices and numbers ("forty cents" came back "$40"). Glue split numbers before diffing. Probe music-only spans separately; Whisper loops phrases over instrumentals.
- **Judge lip-sync by frame strips at plosives.** Why: Gemini's verdicts contradicted each other on the same footage. How: crops at every p/b/m onset from Whisper (lips must close) and at open vowels; check the returned clip's last word, since lip-sync outputs can come back shorter than the audio.
- **Report only what is measurable.** Duration, frame count, resolution, transcript, loudness, sync offset. Never say a clip or a performance works; that verdict is the operator's.
- **Never fabricate placeholder values.** Why: invented ad names sat next to live numbers in a client page and survived the switch to real data. How: filler must be obviously fake (`EXAMPLE_1`) and labelled where it renders, at the moment it is written. At the sample-to-real switch, re-audit every value on the surface.
- **Attribute only what was said.** Why: an invented reason got quoted back to the operator as his own. How: in handoffs and copy sheets, mark your inference as yours.
- **Check the delivered file, not the local one.** How: after any upload, verify by exact name and byte size. Never trust an upload overlay or progress UI.

## 8. Delivery

- **Name every file to the pattern.** `<PREFIX>_<num>_<Persona>_<Format>_<Concept>_<HookStyle>_<FREE|PAID>_<Ratio>.<ext>`. An alternate goes inside the concept token (`Concept-A-Static`). No spaces, no "Copy of".
- **Claim a number before using it.** Why: two sessions shipped the same concept number. How: check the repo folder AND the delivery folder, and claim by creating the folder first.
- **A delivered ad is three things under one stem:** the mp4 (per ratio), `_THUMB.jpg` (per ratio), `_COPY.txt` (primary text, headline, description, CTA, destination URL with UTMs, and any open claim or hold).
- **Re-encode for the destination.** The ad account gets the full-quality render. For a size-capped upload, `-crf 22 -maxrate 2800k` keeps a 25 s video under 10 MB; `-crf 24 -maxrate 4M -bufsize 8M` for about 25 MB.
- **Big files into a web drive: fetch from a host inside the drive tab.** How: put the files on a static host that sends CORS headers, then in the open folder tab run JS that fetches each URL, wraps it in `new File([blob], name, {type})`, and drops them in one DataTransfer on a file row. No size cap, names set at drop. Traps: a same-name file opens a silent replace dialog (trash the old one first); an empty folder has no row to drop on (create a placeholder file first); if the first row is a subfolder the drop lands inside it. Run it fire-and-forget and check "uploads complete" before leaving the page.
- **Everything in the ad account is created PAUSED.** Exception: when Claude runs the account itself from `ads/` and the operator types "turn it on" or "do it" in the chat, that is the approval to set the named campaign, ad set or ads ACTIVE. Why: whoever runs the ad account activates, not us. How: new ad sets are duplicated from a live one with ads excluded and status PAUSED; one creative carries both ratios with placement rules; upload covers as named images and pass them per video by URL; read the creative back to confirm.
- **Summaries to the team are one message.** Why: a post of 68 files across four threads was pulled as unorganised. How: one message, a contact sheet of covers, and the operator posts it unless told otherwise.

## 9. Presenter-led ads over captures, documents and demos

Learned on a set of talking-presenter news ads (a founder on camera over news cards, stills, a product demo and a closing card). The tools are in `toolbox/`.

### Script and claims

- **A news hook reaches the product in one stated step.** Why: a script built on a policy story was sent back because the news never connected to the product; it was rewritten as a chain where each line causes the next. How: read the script as "because X, Y, so Z"; any line that needs the viewer to supply the link gets a bridge line or is cut.
- **Political and time-bound claims carry an expiry date and a named sign-off.** Why: two scripts leaned on a bill and a ballot vote; one stops being true on the vote date and both needed the client's approval as political. How: write the expiry in the copy sheet next to the claim, set a reminder to pull the ad, and do not render the final until the sign-off is in writing.
- **News coverage is not the primary source for a legal or regulatory claim.** Why: a line saying a local government had approved a rule change shipped sourced only to press coverage and was flagged as unverified against the local code. How: open the statute, code page or official record and cite it; if you cannot, soften the line or label it "according to <outlet>".
- **Third-party names and outlet names in a hook need sign-off.** Why: hooks naming a large company and a magazine were held for the client's approval. How: list every third-party brand on screen or in the voice in the copy sheet as an open hold.
- **No broadcast or show footage without a licence.** Why: the presenter's own TV appearances were left out for copyright. How: ask the rights holder or the presenter's team for licensed clips or press stills; otherwise mention it in words only.

### Presenter, voice and matte

- **A script longer than the take minus 1.5 s splits into two lip-sync windows, joined where the presenter is off screen.** Why: a 68 s read against a 70 s take could not be synced in one window, and looping or stitching on camera reads as nodding or a different person. How: `toolbox/split_lipsync.py` with `--hidden` set to a full-screen insert; the split must land on a word gap inside it.
- **Keep a real-voice cut ready as the fallback.** Why: a cloned-voice, lip-synced version was rejected as "a different person"; the clean fallback was the presenter's own recorded lines with his face shown only where the footage really has him talking. How: `toolbox/vocals.py lines` for the audio, `toolbox/matte_coverage.py` for the on-camera spans, and the news cards carry the rest.
- **Measure the bed before cloning from produced footage.** Why: a reel's audio showed no silence at -55 dB anywhere because a music bed ran under it; after separation it had 15 real pauses and made a clean reference. How: `toolbox/vocals.py separate` and read the leftover-music level and pause count before cutting a reference.
- **A matte can take a phone, laptop or object as the person; check coverage before choosing windows.** Why: a fallback cut showed a phone screen as "the presenter" because the background remover kept the phone; an alpha-coverage map separated them (person about 0.35 of frame, phone about 0.62). How: `toolbox/matte_coverage.py cutout.webm`; show the cutout only inside the clean spans it prints.
- **The presenter leaves the frame for full-screen inserts.** Why: the approved cut hid him on the demo, site screens and closing card and kept him everywhere else (the recorded reason is only the client's approval; mine: he covered the UI being shown). How: inserts and the close hide the presenter by default in `compose_shots.py`; `~` hides him on any other shot.

### Shots and pictures

- **One literal shot per phrase, cut on the word that names it.** Why: an earlier version cut backgrounds every ~1.3 s regardless of the words; the version that shipped used one literal shot per phrase, and list items were cut on their own words. How: in a shot list, one token per phrase and `token@word` where a phrase names two things.
- **Use a still at most twice per ad.** Why: the approved system capped stills at two uses per ad and kept alternates on hand (the reason was not recorded). How: keep alternates ready; count uses per token before render.
- **Draw graphic overlays yourself; never trust a video model to keep them.** Why: a still with a dotted outline drawn on the ground came back from Veo with the outline gone. How: generate the plain scene and draw lines, outlines, labels and arrows in the renderer, where the locked camera keeps them in place.
- **Check a generated loop for a cut-away before looping it.** Why: a Veo "static" street loop jumped to another scene at 1-2 s. How: frame strip at 0.25 s steps; keep only the clean stretch (it was 3.0-7.9 s).
- **Veo image-to-video rejects `personGeneration`.** Why: sending `dont_allow` failed the job. How: omit the parameter; keep people out through the prompt and still choice (`toolbox/motion_runner.py` never sends it).
- **A real site demo, full screen, beats a screen composited into a photo.** Why: a laptop-screen composite was rejected as looking bad and hard to composite. How: `toolbox/record_interaction.py` and show a stretch of the demo full screen.

### Captures, documents and demos

- **Pages behind a consent wall become your own quote card with the exact words.** Why: a news site's consent wall blocked every screenshot and another site's pop-up covered its headline. How: `toolbox/quote_card.py` with the headline and quote copied word for word, the outlet as plain text (never its logo), the URL and access date in the copy sheet. Decline consent banners; never accept them to get a clean shot.
- **Never show a real customer's document unredacted.** Why: the sample report used in the ads carried a person's name, address, a record number and street names, and its body text was specific to another state. How: `toolbox/redact.py` with every identifier listed, replacement words where a blank would look odd (a neutral phrase such as "Your address"), region-specific text turned into grey placeholder lines; it re-reads the pages with OCR and fails on a leak.
- **A generic "official records" mark names no agency.** Why: the report sweep used a seal to say the data came from official records and it was deliberately built generic, with no municipality (mine: a real agency's arms would imply an endorsement). How: generic wording and an invented emblem, no place names, no real crests.
- **Choose where a recorded demo starts so the autocomplete shows nothing off-message.** Why: the first letters of a typed address listed places in other states before the local rows appeared. How: start the demo after those prefixes, or type more before the first shown frame.
- **Blur strangers' data in a demo by default.** Why: autocomplete rows showed other people's addresses and the typed address was a real one. How: record them with `--private` and build with `--blur`; unblur only on the owner's explicit call (one client allowed its typed address unblurred).
- **Time-fit a document sweep only between 0.8x and 1.3x.** Why: the approved renderer clamped the sweep to that range (reason not recorded; mine: beyond it the camera moves read as sped up or dragging). How: `fit: rate` clamps; if the span is further off, re-cut the sweep with `doc_sweep.py --hold` or fewer highlights.

### Text on screen

- **Typing on a closing card finishes inside the seconds actually shown.** Why: a closing card rendered at 7.5 s was cut to 5.5 s after a demo and ended mid-word ("allowe"). How: `toolbox/type_overlay.py --shown <seconds>` speeds the typing so the final phrase completes 0.9 s before the cut, then holds with a blinking caret.
- **Captions are phrase chunks that look ahead.** Why: the first cuts used fixed three-word chunks; the approved version switched to phrase chunks with look-ahead so no last word is orphaned. How: break at sentence ends, or at about seven words or 40 characters but never after a weak word and never one word before a closing one; balanced two-line wraps (`compose_shots.py` does this).
- **Captions step aside for the content.** Why: captions covered number screens, the demo field and the presenter's face. How: no captions on number screens; bottom band with a blurred scrim on page cards, demos and documents; everywhere else above the presenter, and the render fails if any text touches his visible pixels.
- **Size count-up numbers on their widest digits.** Why: a count-up changes width as digits change, so a font fitted to the final value can cross the action rail mid-count. How: fit the font to the value with every digit replaced by 8, then draw the live value in that size.
- **Pad a short page card with its own colour, never black.** Why: a short news card showed a black band under the page. How: fill with the page's edge colour; push the page down when its headline sits near the top (`compose_shots.py` does both).
- **No sound effects unless the brand asks for them.** Why: whooshes, thuds, key clicks and risers were cut after the client said they hated them. How: voice and a ducked bed only; record the brand's choice in its BRAND-GUIDE.md.

## The autopilot exception (the ads part only)

The operator can choose autopilot when `ads/BUILD.md` builds a campaign, after its Step 4b
spelled out the risk in their own numbers and they typed "I accept the autopilot
risk". `ads/CAMPAIGN.md` then says `mode: autopilot` and `autopilot_accepted`, and
those lines are their standing yes for these actions,
inside the limits in `ads/CHECKIN.md` STEP 7, and for nothing else:
- pause ads, change the daily budget once a day, add one copy variant a day;
- build the next queued brief (`ads/briefs/`, status `briefed`) through
  `ads/PRODUCTION.md`, one a day, within `autopilot_credit_limit_per_day` (the
  limit is the yes to spend; the brief is the approved script);
- only if `autopilot_video: launch`, and only after the video-reviewer agent writes
  PASS, upload and switch that ad on without a human seeing or hearing it. With `autopilot_video: hold` (the default) the ad is built
  and waits for the operator to look and say "launch it".
Every other rule here still holds. "Autopilot off" in any chat ends it.
