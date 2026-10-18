# Contributing

YouTube Creator Sourcing is maintained by Fluencrs. For now **pull requests are maintainer-only**,
but the sourcing gets better from real-world feedback, and that's where you come in. Everyone
taking part follows the [code of conduct](CODE_OF_CONDUCT.md).

## Support scope

Best effort from a small team. Supported today: macOS in Claude Code. Linux and Windows (WSL)
should work but are less tested. No one-to-one setup help or guaranteed response times - the most
widely felt problems get fixed first.

## Ways to help

- **Report a shortlist call that was wrong** - the "Shortlist quality" issue template: a creator
  passed or rejected wrongly, a score or audience estimate that looked off, a weak draft. This is
  the most valuable feedback there is. Use fictional or fully redacted examples: no real brand or
  creator names, emails, fees or results.
- **Report a bug** - the "Bug" template. Include the output of `.venv/bin/python doctor.py` (it
  contains no secrets) and what you asked Claude to do.
- **Ideas, questions, show-and-tell** - [Discussions](../../discussions).
- **Security issues** - privately, via the Security tab. See [SECURITY.md](SECURITY.md).

## What makes a good change

A rule belongs in the shared engine or skill when it holds for most people sourcing creators, not
just one brand. Tell us:

1. the situation (fictional example),
2. what the engine or Claude did,
3. what an experienced partnerships manager would have done, and why.

Brand-specific rules belong in your own brand config, brand brief or calibration doctrine, and the
calibration step puts them there.

## For maintainers

Before every push:

```bash
python3 -m unittest discover -s tests -v
./scripts/leak-scan.sh
```

- Keep private names that must never appear in `.leak-patterns.local` (git-ignored) and in the
  `LEAK_PATTERNS` repository secret for CI.
- Releasing: add a `CHANGELOG.md` entry and merge to `main`.
- The skill stays under 500 lines and its description under 1,024 characters (the Agent Skills
  limits); longer procedures go in `references/`. `tests/test_repo.py` checks both.
- Never add real creator data, real emails or real results - examples are fictional, figures
  illustrative.
