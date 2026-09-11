"""
Runs on a GitHub Actions schedule (every couple of minutes). Polls Telegram
for new messages and lets you control the tool from your phone, e.g.:

  /add https://youtube.com/@somechannel hindi
  /setlang somechannel english
  /remove somechannel
  /list
  /help

Required environment variables (GitHub Actions secrets):
  TELEGRAM_BOT_TOKEN - from @BotFather
  TELEGRAM_CHAT_ID   - your personal chat id (so only you can issue commands)
"""

import os
import sys

import requests

from common import load_channels, save_channels, load_telegram_state, save_telegram_state, resolve_channel_id

API = "https://api.telegram.org/bot{token}/{method}"


def tg(token, method, **params):
    r = requests.post(API.format(token=token, method=method), json=params, timeout=20)
    r.raise_for_status()
    return r.json()


def reply(token, chat_id, text):
    tg(token, "sendMessage", chat_id=chat_id, text=text, disable_web_page_preview=True)


def find_channel(data, name):
    name = name.lower()
    for c in data["channels"]:
        if c["name"].lower() == name:
            return c
    return None


def handle_command(token, chat_id, text, data):
    parts = text.strip().split()
    cmd = parts[0].lower()

    if cmd == "/help":
        reply(token, chat_id,
              "Commands:\n"
              "/add <channel url> <language code>\n"
              "/setlang <channel name> <language code>\n"
              "/remove <channel name>\n"
              "/list")

    elif cmd == "/add" and len(parts) >= 3:
        url, language = parts[1], parts[2]
        try:
            channel_id, channel_name = resolve_channel_id(url)
        except Exception as e:
            reply(token, chat_id, f"Couldn't resolve that channel: {e}")
            return
        if find_channel(data, channel_name):
            reply(token, chat_id, f"'{channel_name}' is already being tracked.")
            return
        data["channels"].append({
            "name": channel_name,
            "channel_id": channel_id,
            "language": language,
            "last_video_id": None,
        })
        reply(token, chat_id, f"Added '{channel_name}' ({channel_id}), dub language: {language}")

    elif cmd == "/setlang" and len(parts) >= 3:
        name, language = " ".join(parts[1:-1]), parts[-1]
        ch = find_channel(data, name)
        if not ch:
            reply(token, chat_id, f"No channel named '{name}'. Use /list to see tracked channels.")
            return
        ch["language"] = language
        reply(token, chat_id, f"'{ch['name']}' will now use dub language: {language}")

    elif cmd == "/remove" and len(parts) >= 2:
        name = " ".join(parts[1:])
        ch = find_channel(data, name)
        if not ch:
            reply(token, chat_id, f"No channel named '{name}'.")
            return
        data["channels"].remove(ch)
        reply(token, chat_id, f"Removed '{ch['name']}'.")

    elif cmd == "/list":
        if not data["channels"]:
            reply(token, chat_id, "No channels tracked yet. Use /add <url> <language>.")
        else:
            lines = [f"- {c['name']}: {c['language']}" for c in data["channels"]]
            reply(token, chat_id, "Tracked channels:\n" + "\n".join(lines))

    else:
        reply(token, chat_id, "Unrecognized command. Send /help for the list of commands.")


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    allowed_chat_id = str(os.environ["TELEGRAM_CHAT_ID"])

    state = load_telegram_state()
    data = load_channels()

    updates = tg(token, "getUpdates", offset=state["offset"], timeout=0)["result"]

    changed = False
    for update in updates:
        state["offset"] = update["update_id"] + 1
        msg = update.get("message")
        if not msg or "text" not in msg:
            continue
        chat_id = str(msg["chat"]["id"])
        if chat_id != allowed_chat_id:
            continue  # ignore anyone who isn't you
        handle_command(token, chat_id, msg["text"], data)
        changed = True

    save_telegram_state(state)
    if changed:
        save_channels(data)
    print(f"Processed {len(updates)} update(s).")


if __name__ == "__main__":
    sys.exit(main())
