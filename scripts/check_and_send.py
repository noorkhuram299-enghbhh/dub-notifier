"""
Runs on a GitHub Actions schedule (no PC required).

For every channel in config/channels.json:
  1. Use yt-dlp to read the channel's Videos tab and find videos newer
     than the last one we already processed.
  2. For each new video, use yt-dlp to find the audio track matching the
     saved language preference (falls back to the original/default track
     if that language isn't available on this particular video).
  3. Download that track as MP3.
  4. Upload the MP3 to a GitHub Release on this repo (so it has a public
     link) and email that link + the video link via Resend.
  5. Save the new "last seen" video ID back to config/channels.json.

Required environment variables (set as GitHub Actions secrets):
  RESEND_API_KEY   - from resend.com
  EMAIL_FROM       - a sender address on a domain verified with Resend
  EMAIL_TO         - where notifications should be sent
  GITHUB_TOKEN     - provided automatically by GitHub Actions
  GITHUB_REPOSITORY- provided automatically by GitHub Actions (owner/repo)
  YOUTUBE_COOKIES  - optional, exported browser cookies to bypass bot checks
"""

import os
import sys

import requests
import yt_dlp

from common import load_channels, save_channels, github_upload_asset, send_email, send_telegram_message


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
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
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


LANGUAGE_ALIASES = {
    "chinese": ["zh", "cmn", "yue"],
    "mandarin": ["cmn", "zh"],
    "cantonese": ["yue"],
    "english": ["en"],
    "hindi": ["hi"],
    "arabic": ["ar"],
    "spanish": ["es"],
    "french": ["fr"],
    "german": ["de"],
    "japanese": ["ja"],
    "korean": ["ko"],
    "portuguese": ["pt"],
    "russian": ["ru"],
    "italian": ["it"],
    "turkish": ["tr"],
    "vietnamese": ["vi"],
    "thai": ["th"],
    "indonesian": ["id"],
    "urdu": ["ur"],
    "bengali": ["bn"],
    "tamil": ["ta"],
    "telugu": ["te"],
    "polish": ["pl"],
    "dutch": ["nl"],
    "ukrainian": ["uk"],
    "bulgarian": ["bg"],
    "croatian": ["hr"],
    "czech": ["cs"],
    "danish": ["da"],
}


def best_track_for_language(info, language):
    formats = info.get("formats", []) or []
    audio_only = [f for f in formats if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none")]

    best_by_lang = {}
    for f in audio_only:
        raw_lang = f.get("language") or "und"
        lang = raw_lang.lower()
        abr = f.get("abr") or 0
        note = f.get("format_note", "") or ""
        current = best_by_lang.get(lang)
        if current is None or abr > (current["abr"] or 0):
            best_by_lang[lang] = {
                "language": lang,
                "raw_language": raw_lang,
                "format_id": f.get("format_id"),
                "abr": abr,
                "is_default": "default" in note.lower() or "original" in note.lower(),
            }

    wanted = language.lower().strip()

    if wanted in best_by_lang:
        return best_by_lang[wanted], True

    prefixes = LANGUAGE_ALIASES.get(wanted, [wanted])
    for lang_code, track in best_by_lang.items():
        for prefix in prefixes:
            if lang_code == prefix or lang_code.startswith(prefix + "-") or lang_code.startswith(prefix + "_"):
                return track, True

    for t in best_by_lang.values():
        if t["is_default"]:
            return t, False
    if best_by_lang:
        return next(iter(best_by_lang.values())), False
    return None, False


def download_audio(url, out_dir, language_code=None, format_id=None):
    if format_id:
        fmt = format_id
    elif language_code:
        fmt = f'bestaudio[language="{language_code}"]/bestaudio'
    else:
        fmt = "bestaudio"

    ydl_opts = {
        "format": fmt,
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        **_cookie_opts(),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        base = os.path.join(out_dir, info["id"])
        return base + ".mp3"


def process_video(channel, video, repo, github_token, resend_key, email_from, email_to):
    video_url = video["link"]
    with yt_dlp.YoutubeDL({
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        **_cookie_opts(),
    }) as ydl:
        info = ydl.extract_info(video_url, download=False)

    track, matched = best_track_for_language(info, channel["language"])
    if track is None:
        print(f"  no audio tracks found for {video_url}, skipping")
        return

    out_dir = "/tmp/downloads"
    os.makedirs(out_dir, exist_ok=True)

    mp3_path = None
    got_requested_language = matched
    for attempt in (
        {"language_code": track["raw_language"]},
        {"format_id": track["format_id"]},
        {},
    ):
        try:
            mp3_path = download_audio(video_url, out_dir, **attempt)
            if attempt == {}:
                got_requested_language = False
            break
        except Exception:
            continue

    if mp3_path is None:
        raise RuntimeError("Could not download any audio track for this video.")

    asset_name = f"{channel['name'].replace(' ', '_')}_{video['video_id']}.mp3"
    download_url = github_upload_asset(repo, github_token, mp3_path, asset_name)
    os.remove(mp3_path)

    lang_note = "" if got_requested_language else (
        f"<p><em>Note: the \"{channel['language']}\" dub wasn't available on this video, "
        f"so the original/default audio track is attached instead.</em></p>"
    )

    html = f"""
        <h2>New upload: {info.get('title', video['title'])}</h2>
        <p><strong>Channel:</strong> {channel['name']}</p>
        <p><strong>Video:</strong> <a href="{video_url}">{video_url}</a></p>
        <p><strong>Audio ({channel['language']}):</strong> <a href="{download_url}">{download_url}</a></p>
        {lang_note}
    """
    send_email(resend_key, email_from, email_to, f"New video: {info.get('title', video['title'])}", html)
    print(f"  emailed {video_url}")


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    github_token = os.environ["GITHUB_TOKEN"]
    resend_key = os.environ["RESEND_API_KEY"]
    email_from = os.environ["EMAIL_FROM"]
    email_to = os.environ["EMAIL_TO"]
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

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
            try:
                process_video(channel, video, repo, github_token, resend_key, email_from, email_to)
            except Exception as e:
                print(f"  failed to process {video['link']}: {e}")
                send_telegram_message(
                    tg_token, tg_chat_id,
                    f"Failed to process video for {channel['name']}: {video['title']}\nReason: {e}"
                )
                continue
            channel["last_video_id"] = video["video_id"]
            changed = True

    if changed:
        save_channels(data)
        print("Config updated.")
    else:
        print("Nothing new.")


if __name__ == "__main__":
    sys.exit(main())
