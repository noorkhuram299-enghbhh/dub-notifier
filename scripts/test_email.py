import os
import requests


def main():
    api_key = os.environ["RESEND_API_KEY"]
    from_addr = os.environ["EMAIL_FROM"]
    to_addr = os.environ["EMAIL_TO"]

    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "from": from_addr,
            "to": [to_addr],
            "subject": "Test email from dub-notifier",
            "html": "<p>This is a test email. If you're reading this, your Resend + secrets setup is working correctly.</p>",
        },
    )
    print("Status code:", r.status_code)
    print("Response:", r.text)
    r.raise_for_status()


if __name__ == "__main__":
    main()
