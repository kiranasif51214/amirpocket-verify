"""Run locally: QR login, then save the session to a private file, never logs."""
import asyncio
import getpass
import os
from pathlib import Path

import aiohttp
import qrcode
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession


async def main():
    app_url = input("App URL [https://pocket-trader-gatekeeper.lovable.app]: ").strip()
    app_url = (app_url or "https://pocket-trader-gatekeeper.lovable.app").rstrip("/")
    if not app_url.startswith("https://"):
        raise SystemExit("Use the HTTPS address of your own app.")
    verifier_secret = getpass.getpass("VERIFIER_SECRET (hidden): ")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as http:
        async with http.get(
            f"{app_url}/api/public/telegram/bridge",
            headers={"X-Verifier-Secret": verifier_secret},
            allow_redirects=False,
        ) as response:
            if response.status != 200:
                raise SystemExit(f"Cannot read app login settings (HTTP {response.status}).")
            config = await response.json()
    if not config.get("api_id") or not config.get("api_hash"):
        raise SystemExit("Set TG_API_ID and TG_API_HASH in your app secrets first.")
    client = TelegramClient(StringSession(), int(config["api_id"]), config["api_hash"])
    try:
        await client.connect()
        print("On your phone: Telegram > Settings > Devices > Link Desktop Device.")
        print("Scan this QR code here. Do not share it or screenshot it for others.")
        while True:
            qr = await client.qr_login()
            picture = qrcode.QRCode(border=2)
            picture.add_data(qr.url)
            picture.print_ascii(invert=True)
            try:
                await qr.wait()
                break
            except asyncio.TimeoutError:
                print("QR expired; scan the new code below.")
            except SessionPasswordNeededError:
                password = getpass.getpass("Telegram two-step verification password (hidden): ")
                await client.sign_in(password=password)
                break
        if not await client.is_user_authorized():
            raise SystemExit("Telegram login was not completed.")
        target = Path("tg-session.txt")
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(client.session.save())
        print("Saved privately to tg-session.txt. Copy its contents into Railway TG_SESSION.")
        print("Do not upload this file or paste the session into chat. Delete it after saving in Railway.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        raise SystemExit(f"Session generation failed ({type(error).__name__}). No credentials were printed.")