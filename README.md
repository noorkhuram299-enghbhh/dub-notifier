# YouTube Dub-Audio Notifier

Runs entirely on GitHub's free servers. Your PC does not need to be on.

Every 5 minutes it checks the YouTube channels you're tracking. When a new
video appears, it downloads the audio track in your chosen dub language,
uploads it to a GitHub Release (so it has a public link), and emails you
that link + the video link via Resend.

You control which channels are tracked and which language each one uses by
messaging a Telegram bot — from your phone, any time, PC off or on. If
anything fails (a download error, a channel that can't be reached, etc.)
you also get a Telegram message about it.

## How it's wired up

- **GitHub Actions** — runs the checks on a schedule, free, on GitHub's
  servers.
- **YouTube RSS feed** — detects new uploads with no API key needed.
- **yt-dlp** — finds and downloads the audio track matching your chosen
  language (falls back to the original/default track if that language
  isn't available on a given video).
- **GitHub Releases** — stores the downloaded audio so it has a public
  link small enough to email (raw attachments over ~40MB get rejected by
  email providers).
- **Resend** — sends the notification email.
- **Telegram bot** — lets you add/remove channels and change languages
  remotely, and also receives error alerts.

## Files

| File | Purpose |
|---|---|
| `config/channels.json` | Tracked channels, chosen language, last seen video ID |
| `config/telegram_state.json` | Telegram polling offset (internal bookkeeping) |
| `scripts/common.py` | Shared helpers: config I/O, GitHub uploads, email, Telegram |
| `scripts/check_and_send.py` | Main checker: finds new videos, downloads audio, emails |
| `scripts/telegram_bot.py` | Handles `/add`, `/setlang`, `/remove`, `/list` commands |
| `scripts/test_email.py` | Standalone test — sends one email, no YouTube involved |
| `.github/workflows/check_videos.yml` | Runs the checker every 5 minutes |
| `.github/workflows/telegram_poll.yml` | Polls Telegram every 2 minutes |
| `.github/workflows/test_email.yml` | Manual-only workflow to test the email pipeline |

## Required secrets

Set these under **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `RESEND_API_KEY` | from resend.com |
| `EMAIL_FROM` | sender address on a domain verified with Resend (or `onboarding@resend.dev` for testing) |
| `EMAIL_TO` | where notifications go — **must match your Resend account's signup email** unless you've verified your own domain |
| `TELEGRAM_BOT_TOKEN` | from @BotFather |
| `TELEGRAM_CHAT_ID` | your personal Telegram chat ID, so only you can control the bot |

(`GITHUB_TOKEN` is provided automatically by GitHub Actions — no need to add it.)

## Using it (all via Telegram)
