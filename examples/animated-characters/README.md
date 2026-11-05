# Worked example: Chuy and Beto (animated two-hander)

Two invented flat 2D stick-figure men on a building site: Chuy asks how to use
AI, Beto shows him. Read `docs/65-format-animated-characters.md` first; this
folder is the material it refers to.

| File | What |
|---|---|
| `sheets/twoshot.jpg` | The approved two-shot: both men, full body, job site. Start frame for silent wides. |
| `sheets/chuy.jpg`, `sheets/beto.jpg` | One single per man, edited off the two-shot. Start frames for their speaker takes. |
| `sheets/chuy_cab.jpg`, `sheets/beto_cab.jpg` | Singles in the truck cab, for the `cab_driver` and `cab_passenger` settings in `prompts.py`. |
| `voices/chuy_approved_take.mp3`, `voices/beto_approved_take.mp3` | The audio of the approved speaker takes: the target sound for every new take. |
| `prompts.py` | The fixed prompt blocks (ACCENT, ENERGY, LOCK, LOOK), the settings and the example lines. |
| `generate.py` | One Seedance 2.5 take on Replicate. Dry run by default; `--go` spends. |
| `slice_lines.py` | Cuts a speaker take into one clip per line with clean fades. |
| `voice_ab.py` | Puts an approved voice and a new take back to back for the operator to judge. |
| `script.md` | The example episode's dialogue in edit order, with its generation plan. |

To make your own cast: draw the two-shot in your own style, edit the singles
off it, copy `prompts.py` and rewrite CHARACTERS, ACCENT and LOOK. Keep the
structure: one take per speaker, image mode, the blocks unchanged between
episodes.

The characters, the voices and the dialogue are invented. The approved takes
mention ChatGPT and Claude by name, because the episode is about using them.
