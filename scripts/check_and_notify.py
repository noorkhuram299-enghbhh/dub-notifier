"""
Runs on a GitHub Actions schedule (no PC required).

For every channel in config/channels.json:
  1. Use yt-dlp to read the channel's Videos tab and find videos newer
     than the last one we already processed.
  2. For each new video, send a Telegram message with the channel name
     and the video link.
  3. Save the new "last seen" video ID back to config/channels.json.

No downloading, no email, no ffmpeg needed - just detection + a Telegram
ping. Much simpler and far more reliable than trying to download audio.

Required environment variables (set as GitHub Actions secrets):
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID - required, used to send notifications
  YOUTUBE_COOKIES  - optional, can help avoid rare bot-detection issues
"""

import os
import sys

import yt_dlp

from common import load_channels, save_channels, send_telegram_message

COOKIE_FILE = "/tmp/youtube_cookies.txt"


def _cookie_opts():
    cookies = os.environ.get("YOUTUBE_COOKIES")
    if not cookies:
        return {}
    if not os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write(cookies)
    return {"cookiefile": COOKIE_FILE}


def fetch_feed_entries(channel_id):
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "playlistend": 15,
        **_cookie_opts(),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = []
    for e in info.get("entries", []) or []:
        video_id = e.get("id")
        title = e.get("title")
        if not video_id:
            continue
        entries.append({
            "video_id": video_id,
            "title": title,
            "link": f"https://www.youtube.com/watch?v={video_id}",
        })
    return entries


def main():
    tg_token = os.environ["TELEGRAM_BOT_TOKEN"]
    tg_chat_id = os.environ["TELEGRAM_CHAT_ID"]

    data = load_channels()
    changed = False

    for channel in data["channels"]:
        print(f"Checking {channel['name']} ({channel['channel_id']})...")
        try:
            entries = fetch_feed_entries(channel["channel_id"])
        except Exception as e:
            print(f"  failed to fetch feed: {e}")
            send_telegram_message(tg_token, tg_chat_id, f"Failed to check {channel['name']}: {e}")
            continue

        if not entries:
            continue

        last_id = channel.get("last_video_id")
        if last_id is None:
            channel["last_video_id"] = entries[0]["video_id"]
            changed = True
            print("  first run for this channel, marking latest video as seen")
            continue

        new_ones = []
        for e in entries:
            if e["video_id"] == last_id:
                break
            new_ones.append(e)
        new_ones.reverse()

        for video in new_ones:
            print(f"  new video: {video['title']}")
            message = f"New upload from {channel['name']}:\n{video['title']}\n{video['link']}"
            send_telegram_message(tg_token, tg_chat_id, message)
            channel["last_video_id"] = video["video_id"]
            changed = True

    if changed:
        save_channels(data)
        print("Config updated.")
    else:
        print("Nothing new.")


if __name__ == "__main__":
    sys.exit(main())
