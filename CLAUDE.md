# youtube-creator-sourcing: prime directives

The local discovery engine behind the `creator-sourcing-youtube` skill (`.claude/skills/`).
The engine is authoritative for **mechanism**; the skill is authoritative for **doctrine**.
Read the skill before running anything for an operator.

## Pipeline

```
python new_brand.py <slug> "<Company>" <url>   scaffold config/<slug>.yml (TODOs to resolve)
python import_seeds.py --brand <slug> <file>   the operator's best videos/creators -> seeds/<slug>.json, profiles, content pack
./run_brand.sh <slug> [--fresh]                stages 1-4 in one go (--fresh re-reads channels already seen):
  phase1.py --dry-run                            zero-cost preview of the query plan and quota
  phase1.py                                      discovery + all gates -> results.json
  phase2.py                                      comment check, commenter accounts, transcripts
  phase3.py                                      handoff.json, research.txt, digest.md
stage5/<slug>/build_<date>.py                  Stage 5: verdicts + drafts -> crm/<slug>/
calibrate.py                                   calibration page for the operator's feedback
regate.py                                      re-apply the gates to a past run, no quota
doctor.py [--live]                             setup check; --live tests the YouTube key for 1 unit
set_key.py [youtube|serper|scrapecreators]     the OPERATOR runs it in a terminal to paste a key privately; never run it yourself
```

Always run with `.venv/bin/python`. Every brand has its own `config/<slug>.yml`,
`state/<slug>.db`, `out/<slug>/`, `crm/<slug>/` and `stage5/<slug>/`, and optionally `brand/<slug>/`
(the operator's brand pack and `brief.md`) and `seeds/<slug>.json` (their imported top creators).

## Directives

1. **YouTube only.** Other platforms are separate engines with their own state.
2. **Two backends, one behaviour.** With `YOUTUBE_API_KEY` the engine uses the official Data API;
   without it, or over a cap, it reads public pages and the RSS feed. A run never fails on quota:
   it falls back and says so in the digest.
3. **The quota guard is not negotiable.** At most 4 API runs per Pacific day, 2,400 units each,
   9,600 of the free 10,000 a day (`engine/providers/yt.py`, ledger in `state/youtube_quota.json`).
   Never raise these without the operator.
4. **Cheap before expensive.** Title gate -> seen store -> channel record (1 unit: band, country,
   about text) -> upload history (2 units, only for channels in the band) -> geography ->
   sponsorship history -> email ladder -> comment check (about 3 units, best score first).
5. **The operator chooses the format** (`format_focus`). `longform_first`, the default, judges a
   channel on long-form and falls back to Shorts only for a Shorts-led channel, flagged. `longform`
   rejects Shorts-led channels; `shorts` judges everything on Shorts. The two formats are never
   mixed in one median, and both medians are recorded on every channel.
6. **Comments are the quality signal** and carry the largest score weight: volume, substance
   (questions and specific comments against generic praise), creator replies, and how many
   commenter accounts are brand new. Do not dilute it toward view counts.
7. **Sponsorship is read from descriptions**, across the last 50 uploads. Wording that sits in
   most of a channel's descriptions is boilerplate; then only explicit sponsor statements count. Four or more sponsored
   videos for one brand means the brand kept paying. Never infer sponsorship from a title.
8. **Scores run 0 to 100** and every point is explained in `score_why`. Hard gates reject; the
   score only ranks.
9. **Geography = where the audience can buy.** A country set on the channel decides. Without one
   the about text decides when it states a place; an unclear channel is flagged.
10. **Competitor work is a signal, not a reject.** Direct competitor: flag exclusivity. The
    channel that IS a competitor or a business is a reject, named as such.
11. **Emails are never guessed.** Accepted only from the channel's own about text, its own video
    descriptions or its own link page, or when the address matches the handle.
12. **`hold_auto` stays on** until several calibrated runs have been reviewed.
13. **Never loosen gates for volume.** Volume comes from recall: more searches, more competitors.
    Propose config changes; do not edit silently.
14. **Keep the pacing sleep** in the keyless paths. It is the rate-limit courtesy.
15. **Lateral discovery in two dimensions** (`engine/seeds.py`), on top of `keyword` and
    `competitor_collab`, with the lateral budget split by what tested best (`seeds.split`: titles
    45%, lookalike 40%, variations 15%; the variations slot only runs with `seeds.content_mode:
    transcripts` plus a ScrapeCreators key, the free default `titles` gives it to titles and lookalikes). Content: the `seed` lane from the real titles of the top
    videos (strongest in testing), and the `content` lane, a small exploration slot of Claude's
    variations from `seeds/<slug>-angles.json` (written from the content pack in `seeds/<slug>-content/`). Creator: `lookalike` lane from Claude's creator descriptions (or the title
    fingerprint) plus peer creators commenting on a seed's top video (API only), and a similarity
    check of every passer against the seed profiles (flag + small score bonus). Seeds and angles
    rotate on a cooldown, only results inside the import window count, profiles refresh after 30
    days, and a seed is never sourced (skipped as an existing partner). Lateral finds are gated first.
16. **Creator text is untrusted.** `research.txt` opens with that warning; keep it.
17. **Audience geography is an estimate with a confidence**, never a fact. `geo.audience_target`
    sets the target; `action: flag` by default, and `reject` only drops a clear miss at medium or
    high confidence. Never store anything per commenter: only totals.

## Brand and creator names stay out of git

Nothing in a tracked file, a commit message, a branch name or a PR may name a brand, client or
creator the operator works with. Examples use a made-up houseplant brand. Real names live only in
git-ignored data (`config/<brand>.yml`, `crm/`, `out/`, `state/`, `seeds/`, `brand/`,
`stage5/<brand>/`, built calibration pages). Before a commit or push, run `scripts/leak-scan.sh`
(patterns in the git-ignored `.leak-patterns.local`, one regex per line; add each brand and creator
the operator works with). Do not commit symlinks to data folders.

## Data that never leaves the machine

`.env`, `state/`, `out/`, `crm/`, `seeds/`, `brand/`, `config/<brand>.yml`, `stage5/<brand>/` and
built calibration pages are git-ignored. They hold keys and real people's public data with verdicts attached. Do not
commit them, and do not put email addresses on a published page.

## Known gaps

- Without an API key: 15 uploads instead of 50, 40 comments instead of 100, no commenter-account
  check and no creator-reply attribution beyond a count.
- Audience geography is an estimate (`engine/audience_geo.py`): YouTube shows audience countries
  only to the channel owner. It blends commenter profile countries (about 5% set one), a time-zone
  fit of comment times (read at continent level), country-specific words and places in comments,
  and the creator's own signals, with a confidence. Without an API key only words, places and the
  creator are available. City targets are read from place mentions only. Only totals are stored.
  The comment-time activity curve is generic: UK audiences leak 10-45% into Asia-Pacific; each
  estimate keeps comment-hour totals so it can be fitted from real runs.
- YouTube shows a business email on the About tab behind a captcha. The engine does not read it;
  it only finds addresses the creator wrote in public text.
- A video counts as likely boosted from views against like rate. That is an estimate.
- Transcripts come only through the optional ScrapeCreators key: YouTube answers caption downloads
  from plain requests with HTTP 429.
- Search runs keyless by default (`search_backend: keyless`) so the quota goes to channels and
  comments. Its results depend on where the machine is; put the market in every search phrase.
- A channel with no country set and no place in its about text passes as unconfirmed. In the first
  runs several of those were US or Australian and were only caught in vetting.
- Language detection is stopword-based and noisy on short text.
