# Get your YouTube API key (about 10 minutes, once)

Five steps: create a project, turn on the API, create the key, put it in the engine, check it.
Claude walks you through them one at a time in the chat; this page is the same walkthrough to read
alongside or come back to.

The engine reads YouTube through Google's official **YouTube Data API v3**. To use it you create a
free key in your own Google Cloud project. The key is yours: it sits in one file on your computer,
the quota it uses is yours, and nobody else (including the people who made this repo) ever sees it.

**Is it really free?** Yes. Every Google Cloud project gets 10,000 YouTube quota units a day at no
cost. You do not need a credit card and you do not need to turn on billing. The engine never uses
more than 9,600 units a day (see [What the quota means](#what-the-quota-means)).

**Can I skip it?** You can. Without a key the engine runs in keyless mode: slower, 15 uploads per
channel instead of 50, 40 comments instead of 100, and no check of who the commenters are. The key
is what makes the comment check, the strongest part of the vetting, work properly.

Google renames these menus from time to time. If a button isn't where this guide says, search the
page for the word in **bold**, or ask Claude to open the page with you.

---

## Before you start

- Use a Google account you will keep. A personal Gmail is fine. A work Google account works too,
  unless your company blocks staff from creating Cloud projects (then a step will be greyed out,
  and a personal account is the easy way round).
- If you already have a Google Cloud project for something else, make a new one anyway. The quota
  is per project, so a separate project keeps this tool's usage apart and easy to delete.

---

## Step 1 - Create a project (2 minutes)

1. Open <https://console.cloud.google.com> and sign in.
2. First time here? Pick your country, accept the terms and close any "free trial" offer. You do
   **not** need the free trial or a billing account for this.
3. In the top bar, click the project picker (it says **Select a project** or shows a project name)
   -> **New project**.
4. Project name: `YouTube Creator Sourcing`. Leave **Location** as it is (**No organization** is
   fine). Click **Create**.
5. Wait a few seconds for the notification, then make sure the new project is selected in the top
   bar. Every step below happens inside this project.

## Step 2 - Turn on the YouTube Data API v3 (1 minute)

1. In the search bar at the top, type **YouTube Data API v3** and open the result under
   *Marketplace* or *APIs & Services*. (Or: left menu ☰ -> **APIs & Services** -> **Library** ->
   search for it.)
2. Click **Enable**.

   Pick **YouTube Data API v3**, not "YouTube Analytics API" or "YouTube Reporting API". Those are
   for channel owners reading their own stats and will not work here.

3. You land on the API's overview page. That means it is on.

## Step 3 - Create the key (2 minutes)

1. Left menu ☰ -> **APIs & Services** -> **Credentials**.
2. Click **+ Create credentials** -> **API key**.
3. Google asks you to restrict the key. Do this now:
   - **Name**: `youtube-creator-sourcing`
   - **API restrictions**: choose **Restrict key** and tick only **YouTube Data API v3**. If it is
     not in the list, Step 2 did not finish: go back and click Enable.
   - **Application restrictions**: leave on **None**. (Why: see the note below.)
   - Leave "Authenticate API calls through a service account" **unticked**.
4. Click **Create**. A box shows your key: a string of about 39 characters that starts with
   `AIza`. Click the copy icon.

   If your screen created the key straight away without asking about restrictions, click the key's
   name in the Credentials list, set the **API restrictions** as above and click **Save**.

**About the restrictions.** The API restriction means that if the key ever leaked, it could only be
used to read public YouTube data, not to run up any other Google service. Application restrictions
(websites, IP addresses, Android or iOS apps) are made for keys that live inside a website or an
app. This key lives in a file on your computer, and a laptop's IP address changes from network to
network, so an IP restriction would break the engine every time you move. If you run the engine on
a server with a fixed IP address, you can set **IP addresses** to that address.

## Step 4 - Put the key in the engine (2 minutes)

**The easy way: the key helper.** You paste the key once, into a private prompt. You never open a
file, and Claude never sees the key.

1. Open a terminal in the engine's folder.
   - In the Claude desktop app, Claude opens a Terminal tab for you, already running the helper.
     Skip to step 3.
   - Otherwise open the Terminal app (**Cmd+Space**, type `Terminal`, press **Enter**) and go to
     the folder. Claude gives you this line with your real folder path filled in:

     ```bash
     cd "/path/to/youtube-creator-sourcing"
     ```

2. Start the helper:

   ```bash
   .venv/bin/python set_key.py
   ```

3. It says **Paste your YouTube API key and press Enter**. Paste with **Cmd+V** (Windows or Linux:
   **Ctrl+Shift+V**). **Nothing appears while you paste.** That is on purpose, so the key never
   shows on screen.
4. Press **Enter**. The helper checks that it looks like a YouTube key (39 characters, starting
   `AIza`), saves it to `.env` so only your user account can read it, and asks YouTube whether it
   works. You'll see one of these:
   - **It works. YouTube accepted the key.** You're done. Go back to Claude and say "done".
   - **That doesn't look like a YouTube API key.** Something else was copied, often the key's name.
     On the Credentials page click the key, then **Show key**, copy it with the copy icon, and paste
     again (you get three tries).
   - **YouTube did not accept it yet: ...** A brand-new key can take up to five minutes. Wait, then
     run the helper again. If it still fails, tell Claude what the line says.

**The manual way, if you prefer.** Ask Claude to "open my .env file" (on a Mac it opens in
TextEdit; Claude doesn't read it). Click right after `YOUTUBE_API_KEY=`, paste, make sure there is
no space before or after the key and no quotes, press **Cmd+S**, and close the window. The line
should look like this:

```
YOUTUBE_API_KEY=AIzaSyYourKeyGoesHere
```

The same helper works for the optional keys: `.venv/bin/python set_key.py serper` and
`.venv/bin/python set_key.py scrapecreators`.

**Do not paste the key into a chat with Claude**, into an issue, or into a screenshot. Claude never
needs to see it: the engine reads it from `.env` itself. `.env` is git-ignored, so it is never
committed, and only your user account can read it. If you did paste it somewhere, rotate it (see
[Keep the key safe](#keep-the-key-safe)).

## Step 5 - Check that it works (1 minute)

```bash
.venv/bin/python doctor.py --live
```

You should see:

```
  ok    YOUTUBE_API_KEY        set - official API in use; today 0 of 9600 units and 0 of 4 runs used
  ok    key test               works - YouTube accepted the key (1 unit used)
```

`--live` makes one real request to YouTube for 1 unit of your 10,000. Without `--live`, doctor
only checks that a key is present and spends nothing. If the key test says MISS, the line tells you
what to fix; the table under [Troubleshooting](#troubleshooting) has the details.

A brand-new key can take a few minutes to start working. If the test fails right after creating
it, wait five minutes and run it again before changing anything.

That's it. The next run uses the official API automatically.

---

## What the quota means

Google measures YouTube usage in **units**, not requests. Your project gets **10,000 units a day**,
and the count resets at **midnight Pacific time** (08:00 in London, 09:00 in Berlin, an hour off for a week or two
around the daylight-saving changes).

What the engine spends units on:

| Call | Units | When the engine makes it |
|---|---|---|
| Read a channel (subscribers, country, about text) | 1 | Every new channel that passes the title gate |
| Read 50 uploads with their views and descriptions | 2 | Only channels inside your subscriber band |
| Read up to 100 comments on a video | 1 | The comment check, best-scoring channels first |
| Look up commenter accounts | 1 per 50 | The comment check |
| A search | **100** | Only with `search_backend: api` |

Searches are the expensive part, which is why the default config searches without the API
(`search_backend: keyless`) and spends the quota on channels and comments, where it matters most.

**The quota guard.** The engine holds itself to four rules you do not need to manage:

- at most **4 runs a day** use the API,
- each run gets at most **2,400 units**,
- the day never goes past **9,600 units** (a safety margin under Google's 10,000),
- anything over a cap carries on in keyless mode. A run finishes; it never overspends and never
  fails because of quota. The run's digest says when this happened.

The ledger lives in `state/youtube_quota.json`. `doctor.py` shows how much of today is used.

**What a run typically uses.** A run that reads a few hundred channels and deep-checks 10-30 of them
uses roughly 300-900 units with the default keyless search. A repeat run for the same brand costs less, because
the engine remembers every channel it has already seen.

**Need more?** Google offers more quota through its YouTube API Services audit and quota extension
form. For sourcing, four runs a day is plenty, and the engine is built to stay inside the free tier.
Never raise the caps in `engine/providers/yt.py` to get round it.

---

## Keep the key safe

- **One key, one person.** Google's YouTube developer policies do not allow sharing API credentials
  with other people or embedding them in open-source code. Each person who uses this repo creates
  their own key in their own project. Teammates: send them this guide, not your key.
- **Never commit it.** `.env` is in `.gitignore`. If you ever paste the key somewhere public by
  accident, rotate it (below). GitHub's secret scanning may also warn you.
- **Rotate it** if it leaked or you are unsure: **Credentials** -> click the key -> **Rotate key**
  (or delete it and create a new one), paste the new one into `.env`, run `doctor.py --live`.
- **Delete it** when you stop using the tool: **Credentials** -> the key -> **Delete**. Or delete
  the whole project: ☰ -> **IAM & Admin** -> **Settings** -> **Shut down**.

## Optional: watch your usage

☰ -> **APIs & Services** -> **YouTube Data API v3** -> **Quotas & System Limits**. "Queries per
day" shows today's usage against 10,000. The engine's own count in `doctor.py` should be close to
it; Google's figure can lag by a few minutes.

---

## Troubleshooting

| `doctor.py --live` says, or you see | What it means | Do this |
|---|---|---|
| `not a valid key` (`API_KEY_INVALID`, `keyInvalid`) | The text in `.env` is not a working key | Copy it again from Credentials (click **Show key**). No spaces, quotes or line breaks around it |
| `YouTube Data API v3 is not enabled` (`SERVICE_DISABLED`, `accessNotConfigured`) | The key is from a project where the API is off, often a different project than you think | Check the project in the top bar, then Step 2 in that project |
| `restricted to other APIs` (`API_KEY_SERVICE_BLOCKED`) | The key's API restrictions don't include YouTube | Credentials -> the key -> API restrictions -> tick **YouTube Data API v3** -> Save |
| `only allows other IP addresses` / `only allows websites` | An application restriction is set | Credentials -> the key -> Application restrictions -> **None** -> Save |
| `today's quota is used up` (`quotaExceeded`) | 10,000 units were used today in this project | Wait for midnight Pacific. If the engine did not use them, something else shares the project: give this tool its own |
| `YOUTUBE_API_KEY not set` though you pasted it | The line is misspelled, commented out with `#`, or the file was not saved | Run `.venv/bin/python set_key.py` and paste the key again |
| Pasting into the helper shows nothing | Normal: the input is hidden so the key never shows | Press **Enter** |
| The helper says the key doesn't look right | Something else was copied, often the key's name or ID | Credentials -> the key -> **Show key** -> copy icon, then paste again |
| Worked yesterday, fails today | The key was deleted, rotated or restricted, or the project was shut down | Check Credentials. Make a new key if needed |
| The test fails right after creating the key | New keys can take a few minutes | Wait five minutes, run it again |
| The log says the quota cap was reached during a run | Normal near the end of a big run: the engine finished in keyless mode | Nothing. To keep more of a run on the API, use fewer searches or a lower `max_profiles` |

Still stuck? Open an issue with the doctor output. Remove the key first: doctor never prints it,
but check anything you paste.
