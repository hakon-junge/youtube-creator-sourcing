# Rehearsal mode ("make data up")

For trying the whole onboarding end to end without real company data: a demo, a test of the flow,
or someone evaluating the tool. It starts when the operator says "make data up", "use test data"
or similar at any step, and applies only to the steps they skip.

- **Interview answers:** invent answers that fit the website and show each in one line, so the
  operator sees what was assumed.
- **Brand pack:** write two to four made-up files into `brand/<slug>/` (`icp.md`,
  `brand-guidelines.md`, `what-works.md`), each opening with `MADE-UP TEST DATA - not from
  <Company>`, consistent with what the website sells. Then run Level 3 as normal on them.
- **Top videos:** seeds must be real or the import cannot resolve them. Find four to six real,
  on-niche, in-market YouTube channels by search, pick one or two of each one's recent on-topic
  videos, then write `brand/<slug>/performance-TEST.csv` with the video links, dates inside the
  last 180 days and made-up results (signups or sales), import it, and write the angles as normal.
- **Never fake a key.** A skipped API key means a keyless run.
- Write `brand/<slug>/REHEARSAL` (one line: date and what was made up). Every run report and the
  calibration page for that brand then say "rehearsal: made-up inputs". The creators, searches,
  checks and quota are real; observations in drafts still come only from what creators published.
- At the end, ask for feedback on the onboarding itself: which step was unclear, too long, or
  missing, and which question they would cut.

