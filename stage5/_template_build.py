"""Stage 5 builder template. Copy per run to stage5/<brand>/build_<date>.py and fill it from research.txt.

One entry per creator in the handoff: the verdict, why, and (for anything not rejected or held) a
specific observation about their content for the first-touch draft. The engine supplies the facts;
this file holds the judgment. Nothing is sent: the output is a note and a draft per creator in crm/.

Verdicts: advance | human-review | hold (no draft until the open checks are done) | reject.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from engine import stage5  # noqa: E402

BRAND, RUN_DATE = "TODO_slug", "TODO_YYYY-MM-DD"

# The draft follows the operator's own first-approach structure. Run their voice skill before
# writing these lines, and keep the two {{...}} placeholders until the operator fills them.
L = dict(
    hi="Hey {n},", hi_anon="Hey there,",
    intro="I'm {{OPERATOR_NAME}} from TODO_COMPANY's creator partnerships team.",
    bridge="Have you heard of TODO_COMPANY: TODO_DOMAIN?",
    vp="TODO - the product in one line.",
    why="Why I'm reaching out: I'm curious to explore scoping a paid collab with you - something that could fit naturally into {c}.",
    rate="Happy to share some ideas, possible scope, possible rate - but I just wanted to get this on your radar first.",
    exclusivity="One practical question: I saw your work with {b}. If there's an exclusivity in place, just tell me until when and I'll come back then.",
    close="No rush either way - just let me know. :)",
    ps="PS - A possible starting point: {{CREATOR_TRIAL_GRANT}}, no strings attached.",
    subj="{h} x TODO_COMPANY || Paid Partnership",
    dm_ask="I'd be curious to explore a paid collab that fits naturally into {c}. Open to me sending a few ideas over?",
    dm_close="No rush either way :)",
    unfilled="{{OPERATOR_NAME}}, {{CREATOR_TRIAL_GRANT}}",
)
# Problem framing per audience type: (the moment the buyer feels the problem, how the product closes it)
PAIN = {
    "default": ("TODO - the moment this creator's audience runs into the problem.", "TODO - that is exactly the gap the product closes."),
}
C = [
    # dict(handle="creator_handle", verdict="advance", first="Name or None", niche="...", persona="...",
    #      why="One or two sentences a colleague could act on.",
    #      geo="Where the creator and audience are, and how you know",
    #      cfit="their <kind of> videos", pain="default",
    #      obs="A specific read of the entry post, and a second post when there is a clearly relevant one.",
    #      entry=["https://www.youtube.com/watch?v=VIDEOID - what it is, date, views"],
    #      flags=["CHECK FIRST: anything a human must confirm before sending"],
    #      ask_exclusivity=None),   # set to a competitor's name to add the exclusivity question
    # dict(handle="rejected_handle", verdict="reject", niche="...", geo="...", why="...", flags=[]),
]

if __name__ == "__main__":
    d, missing, skipped = stage5.write_all(BRAND, RUN_DATE, L, PAIN, C)
    print("notes ->", d, "| handoff creators without a verdict:", missing, "| no longer in the handoff:", skipped)
