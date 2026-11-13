"""
Pocket Option auto-verification helper for the Amir FX Community Telegram bot.

Runs on Railway. It:
  1. Reads its Telegram login details from the app (no need to set TG_* here).
  2. Logs in once as your Telegram account (code + optional 2FA password) and
     saves the login session back to the app, so restarts never ask again.
  3. Polls the app for pending Trader ID checks, forwards each ID to your
     Pocket Option affiliate bot, and posts the bot's reply back to the app.

Required environment variables on Railway:
  APP_URL         e.g. https://project--YOUR-PROJECT-dev.lovable.app
                  (or your published app URL)
  VERIFIER_SECRET The same value saved in the app's secrets. Shared secret.

Optional:
  AFFILIATE_QUERY_TEMPLATE  Message template sent to the affiliate bot.
                            {id} is replaced with the trader ID.
                            Default: "{id}"
  POLL_SECONDS              Seconds between pending-check polls. Default: 8
  REPLY_TIMEOUT             Seconds to wait for the affiliate bot. Default: 90
"""

import asyncio
import os
import time
from datetime import datetime, timezone

import aiohttp
from telethon import TelegramClient, events
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession
from reply_matching import correlated_kind

APP_URL = (os.environ.get("APP_URL") or "").rstrip("/")
VERIFIER_SECRET = os.environ.get("VERIFIER_SECRET") or ""
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "8"))
REPLY_TIMEOUT = int(os.environ.get("REPLY_TIMEOUT", "90"))
QUERY_TEMPLATE = os.environ.get("AFFILIATE_QUERY_TEMPLATE", "{id}")

if not APP_URL or not VERIFIER_SECRET:
    raise SystemExit("Set APP_URL and VERIFIER_SECRET environment variables on Railway.")

BRIDGE_URL = f"{APP_URL}/api/public/telegram/bridge"
PENDING_URL = f"{APP_URL}/api/public/telegram/pending-requests"
RESULT_URL = f"{APP_URL}/api/public/telegram/verify-result"
HEADERS = {"X-Verifier-Secret": VERIFIER_SECRET}

LOG = lambda msg: print(  # noqa: E731
    f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}", flush=True
)


class Api:
    """Small async wrapper for the app's bridge endpoints."""

    def __init__(self, http: aiohttp.ClientSession):
        self.http = http

    async def get_config(self) -> dict:
        async with self.http.get(BRIDGE_URL, headers=HEADERS) as r:
            if r.status == 401:
                raise SystemExit("VERIFIER_SECRET does not match the app's VERIFIER_SECRET.")
            r.raise_for_status()
            return await r.json()

    async def post_bridge(self, payload: dict) -> None:
        async with self.http.post(BRIDGE_URL, headers=HEADERS, json=payload) as r:
            if r.status >= 400:
                LOG(f"bridge POST failed [{r.status}]: {await r.text()}")

    async def pending(self) -> list[dict]:
        async with self.http.get(PENDING_URL, headers=HEADERS) as r:
            if r.status == 401:
                raise SystemExit("VERIFIER_SECRET does not match the app's VERIFIER_SECRET.")
            r.raise_for_status()
            body = await r.json()
            return body.get("requests", [])

    async def result(self, request_id: str, affiliate_reply: str) -> bool:
        """Posts the partner bot's reply to the app; retries so a temporary
        app error never leaves the user stuck on the checking message."""
        payload = {"request_id": request_id, "verified": True, "affiliate_reply": affiliate_reply[:2000]}
        for attempt in range(1, 6):
            try:
                async with self.http.post(RESULT_URL, headers=HEADERS, json=payload,
                                          timeout=aiohttp.ClientTimeout(total=45)) as r:
                    text = await r.text()
                    if r.status < 400:
                        body = await r.json()
                        LOG(f"result accepted for {request_id}: verified={body.get('verified')}, eligible={body.get('eligible')}, already_resolved={body.get('already_resolved', False)}")
                        return True
                    if r.status in (400, 401, 404, 409):
                        LOG(f"result NOT accepted for {request_id} [{r.status}]: {text[:200]}")
                        return False
                    LOG(f"verify-result attempt {attempt} failed [{r.status}]: {text[:200]}")
            except Exception as e:
                LOG(f"verify-result attempt {attempt} error: {e}")
            await asyncio.sleep(3 * attempt)
        LOG(f"giving up posting result for {request_id}")
        return False


async def wait_for_reply(queue: asyncio.Queue, sender_id: int, sent_id: int, trader_id: str, timeout: float):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=max(0.1, remaining))
        except asyncio.TimeoutError:
            return None
        kind = correlated_kind(msg, sender_id, sent_id, trader_id)
        if kind == "mismatch":
            LOG(f"Ignored unrelated UID reply while checking {trader_id}")
        if kind in ("verified", "not_found", "command_hint"):
            return msg
    return None


async def login_flow(api: Api, client: TelegramClient, cfg: dict):
    """Interactive one-time login; saves the session back to the app."""
    phone = cfg.get("phone")
    if not phone:
        await api.post_bridge({"status": "config_missing"})
        LOG("No phone in app config — set TG_PHONE in the app secrets.")
        raise SystemExit("TG_PHONE missing in app config.")

    password = cfg.get("password") or None
    while True:
        try:
            await client.send_code_request(phone)
            LOG(f"Login code requested for {phone}")
            break
        except Exception as e:  # noqa: BLE001
            LOG(f"send_code_request failed: {e}")
            await asyncio.sleep(30)

    await api.post_bridge({"status": "waiting_code"})
    LOG("Waiting for the login code — type it in the app's admin panel.")

    while True:
        cfg = await api.get_config()
        code = (cfg.get("login_code") or "").strip()
        if code:
            try:
                if password:
                    await client.sign_in(phone, code=code, password=password)
                else:
                    await client.sign_in(phone, code=code)
                break
            except (PhoneCodeInvalidError, PhoneCodeExpiredError):
                LOG("Code rejected — requesting a fresh one in 60s.")
                await api.post_bridge({"status": "login_failed"})
                await asyncio.sleep(60)
                try:
                    await client.send_code_request(phone)
                except Exception as e:  # noqa: BLE001
                    LOG(f"send_code_request failed: {e}")
                await api.post_bridge({"status": "waiting_code"})
            except SessionPasswordNeededError:
                if not password:
                    LOG("2FA needed but TG_2FA_PASSWORD is empty in the app secrets.")
                    await api.post_bridge({"status": "login_failed"})
                    await asyncio.sleep(60)
                    continue
                await client.sign_in(password=password)
                break
            except Exception as e:  # noqa: BLE001
                LOG(f"sign_in failed: {e}")
                await api.post_bridge({"status": "login_failed"})
                await asyncio.sleep(30)
        else:
            await asyncio.sleep(5)

    await api.post_bridge(
        {"session_string": client.session.save(), "clear_code": True, "status": "running"}
    )
    LOG("Login complete — session saved to the app.")


async def verify_loop(api: Api, client: TelegramClient, cfg: dict):
    """Polls pending checks and resolves them through the affiliate bot."""
    affiliate_bot = cfg.get("affiliate_bot")
    if not affiliate_bot:
        LOG("No affiliate bot configured — set AFFILIATE_BOT in the app secrets.")
        await api.post_bridge({"status": "config_missing"})
        return

    try:
        entity = await client.get_entity(affiliate_bot)
    except Exception as e:  # noqa: BLE001
        LOG(f"Cannot resolve affiliate bot {affiliate_bot}: {e}")
        await api.post_bridge({"status": "config_missing"})
        return
    LOG(f"Watching {affiliate_bot} — auto-verification running.")
    replies: asyncio.Queue = asyncio.Queue()

    @client.on(events.NewMessage(incoming=True, from_users=entity.id))
    @client.on(events.MessageEdited(incoming=True, from_users=entity.id))
    async def _on_reply(event):
        if event.is_private:
            await replies.put(event.message)

    recent: dict[str, float] = {}
    last_heartbeat = 0.0

    while True:
        try:
            now = time.monotonic()
            if now - last_heartbeat > 30:
                await api.post_bridge({"status": "running"})
                last_heartbeat = now

            for r in await api.pending():
                request_id, trader_id = r.get("id"), str(r.get("trader_id", ""))
                if not request_id or not trader_id:
                    continue
                if now - recent.get(request_id, 0) < 120:
                    continue
                recent[request_id] = now

                query = QUERY_TEMPLATE.replace("{id}", trader_id)
                LOG(f"Checking trader ID {trader_id} (request {request_id})")
                try:
                    # Discard unsolicited/old replies before each query. The sent
                    # message ID is a second boundary for delayed event delivery.
                    while not replies.empty():
                        replies.get_nowait()
                    sent = await client.send_message(entity, query)
                except Exception as e:  # noqa: BLE001
                    LOG(f"send to affiliate bot failed: {e}")
                    await api.result(request_id, f"[HELPER] could not message affiliate bot: {e}")
                    continue

                msg = await wait_for_reply(replies, entity.id, sent.id, trader_id, REPLY_TIMEOUT)
                if msg and correlated_kind(msg, entity.id, sent.id, trader_id) == "command_hint":
                    sent = await client.send_message(entity, f"/user {trader_id}")
                    msg = await wait_for_reply(replies, entity.id, sent.id, trader_id, REPLY_TIMEOUT)
                reply_text = (msg.text or "").strip() if msg else ""
                if msg and correlated_kind(msg, entity.id, sent.id, trader_id) in ("verified", "not_found"):
                    accepted = await api.result(request_id, reply_text)
                    if not accepted:
                        recent.pop(request_id, None)
                else:
                    LOG(f"No reply from affiliate bot for {trader_id} within {REPLY_TIMEOUT}s")
                    await api.result(request_id, "[HELPER] no reply from affiliate bot")
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            LOG(f"verify loop error: {e}")
        await asyncio.sleep(POLL_SECONDS)


async def main():
    LOG(f"Helper starting — app {APP_URL}")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as http:
        api = Api(http)
        while True:
            try:
                cfg = await api.get_config()
            except SystemExit:
                raise
            except Exception as e:  # noqa: BLE001
                LOG(f"cannot reach app: {e}")
                await asyncio.sleep(30)
                continue

            if not cfg.get("api_id") or not cfg.get("api_hash"):
                LOG("App is missing TG_API_ID / TG_API_HASH secrets.")
                await api.post_bridge({"status": "config_missing"})
                await asyncio.sleep(30)
                continue

            session_string = cfg.get("session_string") or None
            client = TelegramClient(
                StringSession(session_string), int(cfg["api_id"]), cfg["api_hash"]
            )
            await client.connect()

            if not await client.is_user_authorized():
                if session_string:
                    LOG("Saved session is not valid — logging in again.")
                    await api.post_bridge({"session_string": None, "status": "restart_needed"})
                await login_flow(api, client, cfg)
            else:
                LOG(f"Logged in with saved session ({(await client.get_me()).first_name}).")
                if not session_string:
                    await api.post_bridge(
                        {"session_string": client.session.save(), "status": "running"}
                    )
                else:
                    await api.post_bridge({"status": "running"})

            await verify_loop(api, client, cfg)

            await client.disconnect()
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
