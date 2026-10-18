# The free API key: the scripted walkthrough

Read this in full before Step 2 of the skill. Follow it word for word in spirit: one message per step.

This is where people get lost, so it is scripted. Start the brand research (Step 3) in the
background first, so their 10 minutes cost no waiting.

**How to guide it:** five steps, one message each. Every message has the same shape: a bold
heading with "step N of 5" and the minutes it takes, a direct link, numbered clicks with the button
names in **bold** exactly as Google shows them, what they should see when it worked, and "say
done when you see that". Wait for "done" before the next step. If they say something else ("I
can't find it", "it looks different"), stop and solve that first using the "Where people get
stuck" table below; never move on with a step half done. Offer to open each link in their browser.
Google renames menus now and then: tell them once, at step 1, that if a button isn't where you
say, they can search the page for the word in bold, or describe what they see and you'll find it.

**Step 1 of 5 - Create a project (2 min).** Link: <https://console.cloud.google.com/projectcreate>
1. Sign in with a Google account they will keep (a personal Gmail is fine).
2. First time: pick a country, tick the terms, click **Agree and continue**. If Google offers a
   free trial or asks for a card, close it: none of this needs billing.
3. Project name: `YouTube Creator Sourcing`. Leave Location as it is. Click **Create**.
4. Wait for the bell notification, then check the project picker in the top bar says
   **YouTube Creator Sourcing**. If it shows another name, click it and choose the new project.
Worked when: the top bar shows the new project's name.

**Step 2 of 5 - Turn on the YouTube Data API v3 (1 min).** Link:
<https://console.cloud.google.com/apis/library/youtube.googleapis.com>
1. Check the top bar still says **YouTube Creator Sourcing**.
2. Click the blue **Enable** button. Not "YouTube Analytics API" or "YouTube Reporting API".
Worked when: the page changes to the API's overview and the button says **Manage** (or a
**Disable API** button appears).

**Step 3 of 5 - Create the key (2 min).** Link: <https://console.cloud.google.com/apis/credentials>
1. Click **+ Create credentials** at the top, then **API key**.
2. If a box asks about restrictions, set: **Name** `youtube-creator-sourcing`; **API
   restrictions**: choose **Restrict key** and tick only **YouTube Data API v3**; **Application
   restrictions**: leave on **None** (a laptop's address changes from network to network, so any
   other choice breaks the engine). Leave the service-account box unticked. Click **Create**.
3. A box shows the key: about 39 characters starting with `AIza`. Click the **copy icon** next to
   it. Keep this tab open.
4. If the key was created without asking about restrictions: click the key's name in the list,
   set **API restrictions** as above, click **Save**, then copy the key with **Show key**.
Worked when: the key is copied. Say plainly: "Don't paste it here in the chat. The next step puts
it in the engine without me ever seeing it."

**Step 4 of 5 - Put the key into the engine (2 min).** Use the helper; it is the easy path.
- *Claude desktop app:* open a Terminal tab for them in the engine folder, running
  `.venv/bin/python set_key.py` (with the app's terminal tool when it is available; otherwise
  give them the command in a `bash` block so they get a Run button). Then say:
  1. "Click inside the Terminal tab I just opened. It says *Paste your YouTube API key*."
  2. "Paste with **Cmd+V** (Windows/Linux: **Ctrl+Shift+V**). Nothing appears while you paste:
     that's on purpose, it keeps the key private."
  3. "Press **Enter**. It checks the key, saves it, and asks YouTube whether it works."
  4. "When it says *It works*, come back here and say done."
- *Terminal (CLI):* they open a second terminal window: **Cmd+Space**, type `Terminal`, **Enter**.
  Give them two lines to paste, with the real folder path filled in:
  `cd "<absolute path of this folder>"` and `.venv/bin/python set_key.py`. Same four steps.
- *Fallback if the helper can't run:* run `open -e .env` (macOS; it opens the file in TextEdit
  without Claude reading it). Then: "Click right after `YOUTUBE_API_KEY=`, paste with **Cmd+V**,
  make sure there's no space before or after the key and no quotes, press **Cmd+S**, close the
  window." On Linux use `xdg-open .env`.
Never run `set_key.py` yourself with a key, and never type a key into a command.

**Step 5 of 5 - Check it (30 sec).** Run `.venv/bin/python doctor.py --live` and read the
key-test line to them in plain words. "works" -> "You're on the full engine: four free runs a
day." A MISS line names the fix: walk them through it with the table below. A brand-new key can
take five minutes: if the test fails within five minutes of creating the key, wait and test again
before changing anything. Then `doctor.py --path api`.

**Where people get stuck**

| They say or see | What to do |
|---|---|
| "I can't find the project picker" | It's the box just right of the Google Cloud logo in the top bar, showing a project name or **Select a project** |
| The **Enable** button is missing or greyed out | Wrong project selected, or the API is already on (button says **Manage**): check the top bar |
| Google asks for a credit card or a free trial | Close it. The YouTube key is free and needs no billing |
| "It asks me to configure a consent screen" | They clicked **OAuth client ID**. Go back: **+ Create credentials** -> **API key** |
| The key box closed before they copied it | Credentials page -> the key's name -> **Show key** -> copy |
| YouTube Data API v3 isn't in the restriction list | Step 2 didn't finish in this project: enable it, then come back |
| The helper says "doesn't look like a YouTube API key" | Something else was copied (often the key's name or ID). Copy from **Show key** and paste again |
| Pasting does nothing in the Terminal tab | It did paste: the input is hidden on purpose. Press **Enter** |
| Key test says *not a valid key* | Copied with a missing character: copy again with the copy icon and rerun the helper |
| Key test says *restricted to other APIs* | The key -> **API restrictions** -> tick **YouTube Data API v3** -> **Save** |
| Key test says *only allows other IP addresses* or *websites* | The key -> **Application restrictions** -> **None** -> **Save** |
| Key test says *not enabled* | The key belongs to a different project than the enabled API: check the top bar, then step 2 |
| They pasted the key into the chat | Ask them to rotate it (the key -> **Rotate key**), then use the helper with the new one |

- **Never ask for the key, never read `.env`, never print a key.** The project settings deny
  reading and editing `.env`; that is deliberate, do not work around it.
- Never create the Google account, project or key for them. Never turn on billing.

