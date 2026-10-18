# Setup guide

**Start with your website. Go deeper when it pays.** The quickest setup is your website and
nothing else, with results the same day. Three upgrades make the sourcing sharper; take them before
your first run or come back for them after you've seen what it finds.

| Level | You give | Time | What it adds |
|---|---|---|---|
| **1. Quick start** | Your website | 10 min setup + the run | Markets, competitors and searches proposed from public sources. Runs without any key |
| **2. Full engine** (recommended) | A free YouTube API key | +10 min, once | Twice the depth on every channel, the commenter check, faster runs. Free: 4 runs a day at no cost |
| **3. Knows your brand** | Your ICPs, brand guidelines, what works | +15-30 min | Searches from your buyers' real moments, vetting against who you speak to, drafts in your register |
| **4. Learns from your results** | Your 5-10 best videos with results, or your best creators | +10-20 min, refreshed monthly | Lateral searches on the content that worked and lookalikes of the creators who made it, always on your latest numbers |

Written for people who run creator partnerships, not for developers. Every command is something
you paste; Claude can run all of them for you.

---

## Level 1 - Quick start

### 1. Check your computer (5 minutes)

You need:

- **Claude Code**, in the Claude desktop app (Code tab) or the terminal, on a Claude plan that
  includes it. [Install guide](https://code.claude.com/docs/en/setup).
- **A Mac, Linux, or Windows with WSL.** Native Windows is not supported; WSL is Microsoft's free
  Linux layer ([how to install](https://learn.microsoft.com/windows/wsl/install)).
- **Python 3.9 or newer.** Check in a terminal (or ask Claude to):

  ```bash
  python3 --version
  ```

  On a Mac, the first time you run this you may be asked to install Apple's **command line
  developer tools**. Click **Install** and wait a few minutes; it includes Python and git.


### 2. Get the code (3 minutes)

**Easiest: download it.** Open <https://github.com/hakon-junge/youtube-creator-sourcing>, click
the green **Code** button, then
**Download ZIP**. Unzip it (double-click on a Mac) and move the folder somewhere you'll find it,
for example your Documents folder. The folder may be called `youtube-creator-sourcing-main`; that's
fine.

**Or clone it** with git. This makes updates a single command later:

```bash
git clone https://github.com/hakon-junge/youtube-creator-sourcing.git
```

Then open a terminal in the folder (or let Claude do this in step 3) and run:

```bash
bash setup.sh
```

`setup.sh` creates a private Python environment in `.venv/` (nothing is installed system-wide),
installs two packages into it (**PyYAML** for the config, **yt-dlp** for reading public YouTube
pages), creates an empty `.env` that only you can read, and the folders your results go into. It
ends with `setup done`.

### 3. Hand it to Claude

Open the `youtube-creator-sourcing` folder in Claude Code (desktop app: **Open folder**; terminal:
`cd` into it and run `claude`) and paste:

```
Set up YouTube creator sourcing for my brand. My website is: https://your-site.com
```

Claude asks one thing first: **how do you want to run it?**

- **Quick start (keyless):** nothing more to set up. It reads public YouTube pages, so you can
  have results today, with lighter checks (15 uploads per channel, 40 comments, no check of the
  commenter accounts).
- **Free YouTube API key (recommended):** about 10 more minutes, once. See Level 2. Claude
  researches your brand while you create the key, so it adds no waiting.

Then Claude reads your site and proposes a setup as a short table. Correct it; these answers
decide the quality of everything after:

| Claude asks | Why it matters |
|---|---|
| **Where can people buy from you?** | Creators whose audience can't buy are dropped. Markets too wide or too narrow is the most common cause of bad results |
| **Who are your direct and indirect competitors? Who is missing?** | A creator paid by a direct competitor is the strongest signal there is (flagged for exclusivity, never rejected). A missing competitor means missed creators |
| **Against each direct competitor: better, cheaper, more interesting, or no clear edge?** | Tells the vetting how much a competitor's creator is worth to you |
| **Who already works with you?** | They are skipped. The same list can become your Level 4 seeds |
| **Long-form or Shorts?** | `longform_first` (default), `longform` only, or `shorts`. The formats are never mixed |
| **Subscriber band and view floor** | Default 1,000 to 250,000 subscribers, at least 1,000 median views on recent long-form |
| **Where does the audience need to be?** | Most of it in your markets by default. Set a stricter share, another country, or a city (London, New York). Each creator gets an audience estimate with a confidence; the real numbers only come from the creator |

Everything ends up in `config/<your-brand>.yml`, a plain text file with a comment on every setting.

### 4. First run (15-30 minutes, mostly waiting)

Claude runs a free preview of the searches, then discovery and the gates, the deep check on the
best channels, and then vets every creator that passed and writes a note and a first message for
each. **Nothing is ever sent.** You get a summary in the chat and these files:

```
crm/<brand>/contacts.csv        one row per creator: channel link, subscribers, verdict, email and where it was found
crm/<brand>/notes/<handle>.md   the vetting note and the draft first message
out/<brand>/<date>/digest.md    what the run did, spent and rejected
```

### 5. Calibrate (20 minutes, first run only)

Claude opens a calibration page: every creator that reached vetting plus ten rejections. Mark each
call (right, should have passed, should have failed), rate the score, and write a line on what
should have decided it. Then say `apply my feedback`: Claude turns your notes into config and
vetting rules, shows each change, re-applies the gates for free and shows who moved.

---

## Level 2 - The free YouTube API key (about 10 minutes, once)

**Why it's worth it.** Google gives every API key **10,000 quota units a day, free**, no credit
card. A run uses at most 2,400, so you can run the sourcing **four times a day at no cost**. With
the key, every channel gets 50 uploads read instead of 15 (a much fuller sponsorship history), 100
comments instead of 40, a check of who the commenters are (brand-new accounts are a warning sign),
and the creator's own replies.

**How:** follow [docs/youtube-api-key.md](youtube-api-key.md), or say `add my YouTube API key` and
Claude walks you through it one click at a time. In short: Google Cloud console -> new project ->
enable **YouTube Data API v3** -> create an API key restricted to that API -> paste it after
`.venv/bin/python set_key.py` (you paste the key privately, it saves and tests it).

Upgrading after keyless runs? Claude offers one `--fresh` run so the channels it already saw get
the full-depth check.

---

## Level 3 - Your brand pack (15-30 minutes)

Your website says what you sell. Your brand pack says who you speak to and what works. Say
`add my brand docs` and drop whatever your team already uses, as files, into
`brand/<your-brand>/`. Nothing needs rewriting:

- **ICPs and personas**: who buys, why, when, in their words
- **What you use day to day** to decide who the brand speaks to: positioning, messaging, research,
  customer interviews, survey results
- **Creators that worked**: the kinds of creators, past winners and misses and why
- **Content that works**: formats, hooks, lengths, angles, example videos
- **Brand guidelines**: tone of voice, words you use and avoid
- **Rules**: claims you can't make, regulated topics, categories to stay away from

PDF, Word, Markdown, text and CSV all work. From Notion, Google Docs or Confluence, export to PDF
or Markdown. Claude reads everything, asks at most five questions about what the files don't
cover, and writes `brand/<your-brand>/brief.md`: buyers, markets, positioning, creators that work,
content that works, no-go list, voice for drafts, compliance, with every line naming its source.
You correct it. Then Claude proposes the config changes it implies (new searches for each buyer's
moments, sharper niche vocabulary, competitors, the no-go list) and applies the ones you approve.

Every later run vets against the brief, and every draft follows its voice and rules. Say
`update my brand context` when something changes; Claude also offers it once a quarter.

The files stay on your computer and are git-ignored. Claude reads them under your Claude account's
terms; if your company has an AI policy, it applies.

---

## Level 4 - Your best videos and creators (10-20 minutes, refreshed monthly)

The best predictor of what will work next is what already worked. Say `import my best videos`.

- **Best: your 5-10 best-performing YouTube videos, with their result.** Paste the links and the
  number you judge them by (revenue, signups, sales, new customers), ideally with the date they
  went live. Or save an export from your CRM, affiliate platform, spreadsheet or warehouse into
  `brand/<your-brand>/`: one row per video, a video link and a results column. Column names don't
  matter; the importer finds them and tells you what it picked.
- **Fine: just your best creators.** Channel links or @handles, best first. It then works from each
  creator's most-viewed recent video instead of the ones that drove your results.

**What it does with them: two dimensions.**

1. **The content.** The real titles of your top videos become searches: in testing they were the
   strongest way to find creators like the ones who already worked, so they get the biggest share.
   The importer also builds a content pack per video (title, description, tags and, with the
   optional ScrapeCreators key, the transcript). Claude reads it and writes an angle per video
   with a few search variations, which run as a small exploration slot, and uses the transcripts
   when vetting and drafting.
2. **The creators.** Claude writes who each top creator is ("calm small-flat plant collector who films
   weekly care routines") as lookalike searches. With an API key the engine also pulls in peer creators who
   comment on that creator's best video. Every channel that passes is compared with your top
   creators' profiles (topic, size, country, format); a close match is flagged as a lookalike and
   ranks a little higher.

Your top creators are never sourced themselves. About 40% of each run's searches are lateral (most
of them real titles and lookalikes), and
they rotate through your videos and creators, so each run explores a different neighbourhood.

**Why it keeps getting better.** Only results from the last 180 days count, so the engine follows
what works for you now. A new list or export replaces the old one and Claude rewrites the angles;
the run report reminds you when yours is more than 60 days old. Feed it monthly, or at least every
quarter, and the sourcing stays in step with how you run influencer marketing that month.

**Two modes, the simple one first.**

| Mode | Needs | Lateral searches |
|---|---|---|
| **Titles** (default, free) | Nothing extra | Real titles of your top videos + lookalikes. This tested best |
| **Transcripts** (upgrade) | A ScrapeCreators key, 1 credit a video | Adds a small slot of variations Claude writes from the transcripts, and uses the transcripts when vetting and drafting |

Say `switch to transcript mode` to upgrade (Claude helps you add the key with `set_key.py
scrapecreators`), or `switch back to titles` to keep it simple. Transcripts need the extra key
because YouTube's API only gives captions to a video's owner, not to an API key.

---

## Everyday use

| Say to Claude | What happens |
|---|---|
| `Run the YouTube sourcing for <brand>` | A new run. Only channels it hasn't seen cost anything |
| `Is everything set up?` | Doctor: keys, setup path, brand context, seeds, calibration |
| `What should I set up next?` | The next upgrade and what it adds |
| `How does the sourcing work?` | The plain explanation ([HOW-IT-WORKS.md](HOW-IT-WORKS.md)) |
| `Refresh my top videos` + a new list or export | Replaces the seeds with your latest results and rewrites the angles |
| `Why did <creator> fail?` | The gate and the evidence |
| `Re-gate the last run` | Re-applies the gates after a config change, no quota |
| `Set up another brand: https://...` | A second brand with its own config, state and results |

## Updating

Cloned with git: `git pull && bash setup.sh`. Downloaded as a ZIP: download the new ZIP, and copy
your `.env`, `config/`, `brand/`, `seeds/`, `state/`, `out/` and `crm/` folders across into it.

Your keys, brand configs, brand pack, seeds and results are git-ignored, so an update never touches them.

## Removing it

Delete the folder. That removes the code, your keys file and every result. Then delete the API key
or the whole Google Cloud project (see [youtube-api-key.md](youtube-api-key.md#keep-the-key-safe)).

---

## Safety, your data and the rules

- **Nothing is ever sent.** Every draft is a note you review. No tool in the repo can send.
- **Everything stays on your computer.** Results, notes, drafts, your brand pack, your performance
  exports and your keys live in the folder and are git-ignored. Nothing is uploaded by this tool.
  Claude reads them to do the work, under your Claude account's terms.
- **Your key is never shown to Claude.** You paste it into `.env` yourself. The project settings
  block Claude from reading or editing that file, and `doctor.py --live` tests the key without
  printing it. Never paste a key into a chat; if it happens, rotate it.
- **Creator pages are treated as untrusted.** Everything a creator wrote is evidence, never an
  instruction. A channel whose text tries to steer an AI is held and flagged in the report.
- **Keep normal permission prompts on** (not "bypass permissions"). The repo already allows its
  own commands without a prompt each time.
- **Public data only.** The engine never logs in to YouTube and can't see who watches a video.
- **Creator emails are personal data**, even when published for collaborations. Each is stored
  with where it was found; none is ever guessed. Keep outreach one-to-one and follow the rules
  where you and the creator are (GDPR in the EU and UK, CAN-SPAM in the US).
- **YouTube's terms apply** when you use the API: the
  [YouTube API Services Terms](https://developers.google.com/youtube/terms/api-services-terms-of-service)
  and [Developer Policies](https://developers.google.com/youtube/terms/developer-policies). Your key
  is yours alone. Keyless mode reads public pages instead of the API.

## Troubleshooting

| Symptom | What to do |
|---|---|
| `python3 not found` | Level 1, step 1. On a Mac, run `python3 --version` once and accept the developer tools install |
| `permission denied: ./setup.sh` or `./run_brand.sh` | Run `bash setup.sh` once: it fixes the permissions on the other scripts |
| Doctor's key test says MISS | The line says what to fix; details in [youtube-api-key.md](youtube-api-key.md#troubleshooting) |
| Keyless reads fail | `.venv/bin/pip install -U yt-dlp`. YouTube changes its pages often and yt-dlp keeps up |
| `TODOs left in config/<brand>.yml` | Ask Claude to finish the setup |
| The importer picked the wrong column | Tell Claude which one; it re-runs with `--metric`, `--channel`, `--video` or `--date` |
| Some creators "unresolved" in the import | Give Claude their channel links |
| The log says the quota cap was reached | Normal near the end of a big run: it finished in keyless mode |
| Almost everyone rejected on geography | Your market words are too narrow. Ask Claude to show the rejected bios and widen them with you |
| Few creators found | Add searches phrased the way a viewer types them, more competitors, or import your best videos |
