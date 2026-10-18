# Changelog

## 0.1.1 - 2026-10-18

- **Repository setup to match our other public repositories:** security policy, contributing
  guide, code of conduct, issue and pull request templates, CI with tests and a leak scan on every
  push, and a protected `main` branch.
- **Tests** (`tests/`): the skill's size limits, the config template, the permission rules, the
  git-ignore rules, key validation, seed import parsing, lateral search planning and the
  audience-geography estimate. They run offline.
- The skill's API key walkthrough and rehearsal mode moved into `references/` so the skill stays
  under the 500-line Agent Skills limit; the procedure is unchanged.

## 0.1.0 - 2026-10-18

First public release.

- **Setup in four levels, the simplest first:** a website and nothing else (keyless), then a free
  YouTube API key, a brand pack (ICPs, guidelines, what works), and your 5-10 best videos with
  their results. Each level can come before the first run or after it.
- **Discovery:** searches for the moments the product matters, reviews of competitors, and lateral
  searches from your best videos: their real titles and lookalikes of the creators who made them.
  An optional transcript mode adds variations written from the transcripts.
- **Cheapest checks first:** niche, subscriber band, country, activity, median views by format,
  sponsorship history across 50 uploads, a published email (never guessed), and a comment check.
- **Audience geography:** an estimate of where each creator's audience is, from commenter
  countries, comment times and local words, with a confidence and a target you set.
- **Vetting and drafts:** Claude writes a verdict with reasons and a first message that refers to
  the creator's own video. Nothing is ever sent.
- **Calibration:** a 20-minute review after the first run turns your corrections into settings and
  vetting rules.
- **Safety:** keys pasted privately with `set_key.py`, never visible to Claude; creator text
  treated as untrusted; everything stays on your machine.
