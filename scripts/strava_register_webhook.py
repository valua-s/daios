"""Одноразовая регистрация Strava push-subscription.

Запуск:
    python -m scripts.strava_register_webhook https://your-domain.tld/api/webhooks/strava

Или:
    STRAVA_CALLBACK_URL=https://your-domain.tld/api/webhooks/strava \
        python -m scripts.strava_register_webhook

Перед запуском убедись, что бэкенд развёрнут и `GET <callback>` отвечает на
hub.challenge корректно.

Дополнительные команды:
    python -m scripts.strava_register_webhook --list      # текущая подписка
    python -m scripts.strava_register_webhook --delete    # удалить подписку
"""
from __future__ import annotations

import os
import sys

import httpx

from backend.core.config import settings

API_URL = "https://www.strava.com/api/v3/push_subscriptions"


def _creds() -> dict[str, str]:
    return {
        "client_id": settings.strava_client_id,
        "client_secret": settings.strava_client_secret.get_secret_value(),
    }


def create(callback_url: str) -> None:
    payload = {
        **_creds(),
        "callback_url": callback_url,
        "verify_token": settings.strava_webhook_verify_token,
    }
    r = httpx.post(API_URL, data=payload, timeout=30.0)
    print(r.status_code, r.text)
    r.raise_for_status()


def list_subs() -> None:
    r = httpx.get(API_URL, params=_creds(), timeout=30.0)
    print(r.status_code, r.text)


def delete_sub() -> None:
    r = httpx.get(API_URL, params=_creds(), timeout=30.0)
    subs = r.json()
    if not subs:
        print("No subscriptions")
        return
    for s in subs:
        sid = s["id"]
        dr = httpx.delete(f"{API_URL}/{sid}", params=_creds(), timeout=30.0)
        print(f"DELETE {sid}: {dr.status_code} {dr.text}")


def main() -> None:
    args = sys.argv[1:]
    if "--list" in args:
        list_subs()
        return
    if "--delete" in args:
        delete_sub()
        return

    callback = args[0] if args else os.environ.get("STRAVA_CALLBACK_URL", "")
    if not callback:
        print("Usage: python -m scripts.strava_register_webhook <callback_url>")
        sys.exit(1)
    create(callback)


if __name__ == "__main__":
    main()
