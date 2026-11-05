# "Who showed you that?" (example episode, about 55 s)

Chuy asks how to use AI. Beto shows him the one job he uses it for every day.
Nobody laughs. Short Spanish words only, never a full Spanish sentence.

## Dialogue, in edit order

CHUY: Ey, Beto. Can I ask you something without you laughing at me, güey?
BETO: Nel. Go.
CHUY: This AI thing. ChatGPT, Claude, all that. How do you use it? I asked it if my troca sounds bad.
BETO: ...You asked it.
CHUY: I typed the noise, güey. Chk-chk-chk-chk. It said see a mechanic.
BETO: Órale. Mira. This is how I use it.
        [WIDE: Beto holds the phone up, Chuy leans in]
BETO: Customer texts me what he wants. I paste it in Claude. It writes the quote, my prices, my words. Then I tell it, send it. It sends the email right from the chat.
        [INSERT: thumb presses Send]
CHUY: No manches. Who showed you that?
BETO: [YOUR OFFER LINE: who taught him, said the way Beto would say it]
CHUY: Simón. Send me the link.
BETO: I already sent it. Tuesday.
CHUY: (long beat) ...I thought that was spam.
BETO: Órale.
        [END CARD in the brand's style]

## Generation plan

| Take | Start frame | Length | Audio | Lines |
|---|---|---|---|---|
| CH_CHUY | `sheets/chuy.jpg` | 25 s | on | all of Chuy's lines (`prompts.EXAMPLE["chuy"]`) |
| CH_BETO | `sheets/beto.jpg` | 25 s | on | Beto's lines (`prompts.EXAMPLE["beto"]`) |
| CH_BETO2 | `sheets/beto.jpg` | up to 20 s | on | the offer line, if Beto's part runs past 30 s |
| W1 | `sheets/twoshot.jpg` | 6 s | off | wide under Chuy's first line |
| W2 | `sheets/twoshot.jpg` | 6 s | off | Beto holds the phone up, Chuy leans in |
| IN | a phone-screen frame you make | 5 s | off | thumb presses Send (the screen is a green placeholder; corner-pin a real screenshot in post) |
| W3 | an evening version of the two-shot | 6 s | off | wide under "Send me the link" |

Build CH_CHUY first, slice it, cut it with W1, and get the operator to watch
and listen before generating the rest.
