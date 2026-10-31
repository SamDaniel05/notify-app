import json
import os

import requests


def send_ntfy(topic: str, title: str, body: str):
    topic = (topic or "").strip().lstrip("/")
    if not topic:
        return False, "Missing ntfy topic"
    try:
        res = requests.post(
            f"https://ntfy.sh/{topic}",
            data=body.encode("utf-8"),
            headers={"Title": title[:200], "Priority": "high", "Tags": "bell"},
            timeout=15,
        )
        if res.status_code >= 400:
            return False, f"ntfy HTTP {res.status_code}"
        return True, "ok"
    except requests.RequestException as e:
        return False, str(e)


def send_telegram(bot_token: str, chat_id: str, title: str, body: str):
    if not bot_token or not chat_id:
        return False, "Missing Telegram bot token or chat_id"
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": f"*{title}*\n\n{body}"[:4000], "parse_mode": "Markdown"},
            timeout=15,
        )
        data = res.json() if res.content else {}
        if not data.get("ok"):
            return False, str(data)[:300]
        return True, "ok"
    except requests.RequestException as e:
        return False, str(e)


def send_webpush(subscription: dict, title: str, body: str):
    """subscription: {endpoint, keys: {p256dh, auth}} from browser PushManager."""
    if not subscription or not subscription.get("endpoint"):
        return False, "Missing web push subscription"
    public = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
    private = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    subject = os.environ.get("VAPID_SUBJECT", "mailto:notify@localhost").strip()
    if not public or not private:
        return False, "VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY not set on server"
    try:
        from pywebpush import webpush, WebPushException

        payload = json.dumps({"title": title[:120], "body": body[:500], "url": "/"})
        webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=private,
            vapid_claims={"sub": subject},
        )
        return True, "ok"
    except Exception as e:
        return False, str(e)[:300]
