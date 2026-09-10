"""
Shared helpers: config I/O, channel-ID resolution, GitHub release uploads,
and Resend email sending.
"""

import json
import os
import time
import requests
import yt_dlp

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "channels.json")
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "telegram_state.json")

GITHUB_API = "https://api.github.com"


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_channels():
    return load_json(CONFIG_PATH, {"channels": []})


def save_channels(data):
    save_json(CONFIG_PATH, data)


def load_telegram_state():
    return load_json(STATE_PATH, {"offset": 0})


def save_telegram_state(data):
    save_json(STATE_PATH, data)


# ----------------------------------------------------------------------
# Resolve a pasted YouTube channel URL (/@handle, /c/name, /channel/UC..,
# or a video URL from that channel) into a canonical UC... channel_id.
# ----------------------------------------------------------------------
def resolve_channel_id(url):
    ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        channel_id = info.get("channel_id") or info.get("id")
        channel_name = info.get("channel") or info.get("uploader") or info.get("title") or channel_id
        if not channel_id or not str(channel_id).startswith("UC"):
            raise ValueError("Could not resolve a channel ID from that URL.")
        return channel_id, channel_name


# ----------------------------------------------------------------------
# GitHub: upload a file as a release asset and return its public URL.
# Uses one release per run (tagged by timestamp) to avoid name clashes.
# ----------------------------------------------------------------------
def github_upload_asset(repo, token, file_path, asset_name):
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    tag = f"audio-{int(time.time())}"

    r = requests.post(
        f"{GITHUB_API}/repos/{repo}/releases",
        headers=headers,
        json={"tag_name": tag, "name": tag, "body": "Auto-uploaded dub audio.", "prerelease": True},
    )
    r.raise_for_status()
    release_id = r.json()["id"]

    upload_url = f"https://uploads.github.com/repos/{repo}/releases/{release_id}/assets?name={asset_name}"
    with open(file_path, "rb") as f:
        r2 = requests.post(
            upload_url,
            headers={**headers, "Content-Type": "audio/mpeg"},
            data=f,
        )
    r2.raise_for_status()
    return r2.json()["browser_download_url"]


# ----------------------------------------------------------------------
# Resend email
# ----------------------------------------------------------------------
def send_email(api_key, from_addr, to_addr, subject, html):
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"from": from_addr, "to": [to_addr], "subject": subject, "html": html},
    )
    r.raise_for_status()
    return r.json()
