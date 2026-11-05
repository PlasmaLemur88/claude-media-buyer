"""Prompt blocks for an animated two-hander (worked example: Chuy and Beto).

These blocks are copied from the generation the operator approved. Keep the
ACCENT, ENERGY, LOCK and LOOK blocks word for word between episodes, so the
characters keep their voices; change only the setting sentence and the lines.
See docs/65-format-animated-characters.md for why each block exists.

To make your own characters, copy this file, rewrite CHARACTERS, ACCENT and
LOOK for your style, and keep the structure.
"""

# Who each character is, as the model sees him in the frame. Name the
# distinguishing clothing only: the start image carries the rest of the look.
CHARACTERS = {
    "chuy": {
        "who": "the shorter man in the green work shirt and dark cap,",
        "voice": "",
    },
    "beto": {
        "who": "the taller man in the orange hi-vis vest,",
        "voice": " He has a DEEPER, rougher voice than a younger man.",
    },
}

# The accent written as a DIALECT, with its sound features named. Writing it as
# a nationality ("a Mexican man speaking English") gave a learner's accent that
# the operator rejected; writing it as where he grew up plus how the dialect
# sounds gave the take that shipped.
ACCENT = (
    "HE IS CHICANO, born and raised in East Los Angeles, Boyle Heights. He is a native English "
    "speaker who speaks CHICANO ENGLISH, the East LA dialect: a sing-song rise-and-fall melody on "
    "every sentence, stress that lands late, long drawn-out vowels, 'ch' where an Anglo says 'sh', "
    "dropped final consonants, tags like 'ey', 'right?' and 'you know?', and Spanish words dropped "
    "into the middle of English sentences with no pause and full Spanish pronunciation. He sounds "
    "like a vato from Boyle Heights. He does NOT sound like a newscaster, and he does NOT sound like "
    "a Mexican national learning English. "
)

# Energy at full strength. "Flat", "dry" or "unhurried" gave a depressing read.
ENERGY = (
    "He is HAPPY and LOUD and having fun. He talks FAST, about 190 words per minute, starts on the "
    "very first frame with no pause, grins the whole time, gestures with his hands. High energy, "
    "playful, warm, funny. Between lines he listens for a short beat to a friend just off camera, "
    "then goes again. He finishes on his last word with a grin and a closed mouth, and holds still. "
)

LOCK = "CRITICAL: he says ONLY these lines, in this order, word for word, nothing else, and stops after the last one.\n"


def LOOK(bg):
    return (
        "Flat 2D vector animation exactly as in the start image: hard black outlines, solid grey "
        "circular head, small dot eyes, thin stick limbs, no shading, no gradients, no 3D. "
        f"The painted {bg} background stays completely still. Camera pushes in very slowly. "
        "Dialogue only, no music, no laugh track, no other voices."
    )


# Settings: (the sentence that places him, the background word for LOOK).
SETTINGS = {
    "job": ("on the dirt of a job site.", "job-site"),
    "cab_driver": ("sitting in the driver's seat of a pickup truck cab on his lunch break.", "truck-cab"),
    "cab_passenger": ("sitting in the passenger seat of a pickup truck cab on his lunch break.", "truck-cab"),
}


def lines_block(lines):
    """lines: list of (direction, text). Direction is the emotion and one
    gesture, never a voice type."""
    return "".join(f'{i}. {d}: "{t}"\n' for i, (d, t) in enumerate(lines, 1))


def speaker_prompt(character, setting, lines):
    c = CHARACTERS[character]
    place, bg = SETTINGS[setting]
    return (
        "A single flat 2D cartoon stick figure man alone in the frame, "
        + c["who"] + " " + place + c["voice"] + " "
        + ACCENT + ENERGY + LOCK + lines_block(lines) + LOOK(bg)
    )


def cutaway_prompt(action, bg):
    """A silent shot to lay under dialogue (wides, inserts)."""
    return (
        "CHUY is the shorter man in the green work shirt and dark baseball cap. BETO is the taller "
        "man in the orange high-visibility vest. Keep both men exactly as they appear in the input "
        "frame: same heights, same positions in frame, same clothing. ACTION: " + action + " "
        "Flat 2D vector animation: hard black outlines, solid grey circular heads, small dot eyes, "
        "thin stick limbs, no shading, no gradients, no 3D. The painted " + bg + " background stays "
        "completely still. The camera pushes in very slowly. NO dialogue, NO speech, NO music, silent."
    )


# The example episode's lines, one list per generation (one generation per speaker).
EXAMPLE = {
    "chuy": [
        ("Curious, grinning", "Ey, Beto. Can I ask you something without you laughing at me, güey?"),
        ("Confused, one hand up", "This AI thing. ChatGPT, Claude, all that. How do you use it? I asked it if my troca sounds bad."),
        ("Proud of himself, then deflated", "I typed the noise, güey. Chk-chk-chk-chk. It said see a mechanic."),
        ("Amazed, leaning in", "No manches. Who showed you that?"),
        ("Quick and decided", "Simón. Send me the link."),
        ("After a long still beat, sheepish", "...I thought that was spam."),
    ],
    "beto": [
        ("Easy and warm, quick", "Nel. Go."),
        ("Deadpan, holding back a smile", "...You asked it."),
        ("Upbeat, warming up to show off", "Órale. Mira. This is how I use it."),
        ("Fast and matter-of-fact, counting on his fingers", "Customer texts me what he wants. I paste it in Claude. It writes the quote, my prices, my words. Then I tell it, send it. It sends the email right from the chat."),
        ("Plain, a small shrug", "I already sent it. Tuesday."),
        ("Resigned, one slow nod", "Órale."),
    ],
}
