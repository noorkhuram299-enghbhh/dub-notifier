# YouTube Dub-Audio Notifier

Runs entirely on GitHub's free servers. Your PC does not need to be on.

Every 15 minutes it checks the YouTube channels you're tracking. When a new
video appears, it downloads the audio track in your chosen dub language,
uploads it to a GitHub Release (so it has a public link), and emails you
that link + the video link via Resend.

You control which channels are tracked and which language each one uses by
messaging a Telegram bot — from your phone, any time, PC off or on.

## One-time setup

### 1. Create the repo
- Create a **public** GitHub repo (public repos get free, effectively
  unlimited Actions minutes; private repos get 2,000 free minutes/month,
  which is usually still plenty at this schedule).
- Upload all these files to it, preserving the folder structure.

### 2. Get a Resend API key
- Sign up at resend.com, verify a sending domain (or use their test domain
  for your own inbox while testing), and grab an API key.

### 3. Create a Telegram bot
- Message **@BotFather** on Telegram, send `/newbot`, follow the prompts.
  You'll get a bot token like `123456:ABC-...`.
- Message your new bot anything, then visit
  `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser to find
  your numeric `chat.id` — that's your `TELEGRAM_CHAT_ID`. This restricts
  the bot so only you can issue commands.

### 4. Add repo secrets
In your repo: **Settings → Secrets and variables → Actions → New repository
secret**. Add:

| Secret | Value |
|---|---|
| `RESEND_API_KEY` | from Resend |
| `EMAIL_FROM` | e.g. `notifier@yourdomain.com` (must match your verified Resend domain) |
| `EMAIL_TO` | the address you want notifications sent to |
| `TELEGRAM_BOT_TOKEN` | from BotFather |
| `TELEGRAM_CHAT_ID` | your chat id from step 3 |

(`GITHUB_TOKEN` is provided automatically — you don't need to add it.)

### 5. Turn it on
The workflows run automatically on their schedule once the files are on
GitHub. You can also trigger either one manually from the **Actions** tab
to test it right away, instead of waiting for the schedule.

## Using it (all via Telegram)

```
/add https://youtube.com/@somechannel hindi
/list
/setlang somechannel english
/remove somechannel
/help
```

The channel "name" used in `/setlang` and `/remove` is whatever YouTube
reports as the channel's display name — check `/list` if unsure.

## Things worth knowing

- **First run for a new channel**: it remembers the current latest video as
  "already seen" so you don't get flooded with the entire back-catalog —
  only videos uploaded *after* you add the channel trigger an email.
- **Language fallback**: if the video doesn't have your chosen dub, the
  email says so and includes the original/default audio track instead.
- **Storage**: audio files are attached to time-stamped GitHub Releases in
  this repo, not stored in the repo history — that keeps the repo itself
  small. Delete old releases from the repo's Releases page occasionally if
  you want to tidy up.
- **Check interval**: 15 minutes for new videos, 2 minutes for Telegram
  commands — adjust the `cron` lines in `.github/workflows/*.yml` if you
  want it faster or slower (more frequent = more Actions minutes used).
- **YouTube's Terms of Service** technically don't allow downloading videos.
  This is intended for personal use of content — worth being aware of.
