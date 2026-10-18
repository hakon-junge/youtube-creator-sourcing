<!--
Pull requests are maintainer-only for now (see CONTRIBUTING.md). Not a maintainer?
Please open an issue instead: the "Shortlist quality" or "Bug" template.
-->

## What this changes

<!-- One or two sentences: what is different after this merges, and why. -->

## How it was checked

<!-- What you ran or tried, and what you saw. -->

## Checklist

- [ ] Tests pass: `python3 -m unittest discover -s tests`
- [ ] Leak scan passes: `./scripts/leak-scan.sh`
- [ ] Examples are fictional: no real brand or creator names, emails, fees or results
- [ ] The skill stays under 500 lines and its description under 1,024 characters
- [ ] If this touches keys, the quota guard, what is stored, or what Claude may run: the description says what changed, and `SECURITY.md` still matches
- [ ] If users should receive this: `CHANGELOG.md` has an entry
