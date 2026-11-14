# Pocket Option auto-verification helper (Railway) — v5

## Recommended: saved Telegram session (no code on redeploy)

This version accepts `TG_SESSION` in Railway Variables. It takes priority over
the session saved in the app, survives Railway redeployments, and never requests
a login code when that variable is set. Telegram can revoke or expire sessions;
no Telegram session can be guaranteed to last forever.

1. On your own computer, install Python 3.12 or later and extract this package.
2. Open a terminal in the extracted folder and run:

   ```sh
   python -m pip install -r requirements.txt
   python generate_session.py
   ```

3. Enter your app URL and the matching `VERIFIER_SECRET` when prompted.
   The helper reads the existing Telegram API settings from your app securely.
4. On your signed-in phone open Telegram → Settings → Devices → Link Desktop
   Device, then scan the QR code shown in your local terminal. If Telegram asks
   for your two-step verification password, enter it locally when prompted.
   This uses QR approval, not a delivered login code.
5. The script saves `tg-session.txt` privately on your computer. If that file
   already exists, move or delete it before generating another session.
6. In Railway → service → Variables add `TG_SESSION` with the entire file contents.
   Keep `APP_URL=https://pocket-trader-gatekeeper.lovable.app` and your existing
   `VERIFIER_SECRET` unchanged. Then delete the local session file.
7. Replace the deployed helper files with this package and redeploy. Run only
   one service with one replica for this Telegram session. Do not run the same
   session on another computer or helper at the same time.
8. Railway should show `Telegram authorized — auto-verification starting with saved session.`
   Send a Trader ID to @AmirfxPO_bot and check that the bot returns the partner result.

`TG_SESSION` gives access to your Telegram account: never paste it into chat,
commit it, share the QR code, or upload `tg-session.txt` with your source files.
If Railway says it is invalid/expired/revoked, generate a new session and replace
the variable. Temporary connection failures reconnect automatically. If Telegram
reports `AuthKeyDuplicatedError`, stop duplicate workers and generate a new session.

Tests: `python -m unittest discover -v`.
Live Railway login and verification still require your QR approval and redeployment.

## Optional fallback: login by code (without TG_SESSION)

## Updating your existing Railway service

Replace all helper files with the contents of this package and redeploy.
Keep APP_URL and VERIFIER_SECRET unchanged. Stop any duplicate helper services
using the same Telegram account; run only one worker, with one replica.
Publish the Lovable app changes too, then resend the Trader ID.

This version discards old replies, ignores other Trader IDs and help messages,
and only submits a fresh result for the requested ID. If the partner bot asks
for `/user {uid}`, the helper automatically retries with that command.
A matching UID confirms registration; services still require the configured
current balance (not total historical deposits).

This little service runs your Telegram account in the background and makes
verification automatic: when someone sends their Trader ID to
**@AmirfxPO_bot**, this helper forwards the ID to your Pocket Option affiliate
bot, reads the reply, and your main bot instantly tells the user the result.

**Important:** deploy ONLY the contents of this zip. If your Railway service
or repo folder already has files from a previous attempt (especially any old
`Dockerfile`), delete them first — a broken `Dockerfile` is what caused the
"ENV names can not be blank" build error.

## 1. Deploy on Railway

1. Railway → **New Project → Deploy from ZIP** → upload this zip
   (or push only this folder's files to a repo and deploy it).
2. No extra build settings needed — Railway reads `railway.json` and the
   included `Dockerfile`.

## 2. Set two environment variables

In Railway → your service → **Variables**:

| Variable | Value |
| --- | --- |
| `APP_URL` | `https://pocket-trader-gatekeeper.lovable.app` (your published app URL) |
| `VERIFIER_SECRET` | **Exactly the same value** you saved in the Lovable app secrets |

> `VERIFIER_SECRET` must match on both sides — this helper and the app.
> If you lost the value, open the Lovable project → **Settings → Secrets** and
> update `VERIFIER_SECRET` to a new value, then paste the same new value here.

Everything else (your Telegram API ID/hash, phone, 2FA password, affiliate bot
username) is fetched from the app's own secrets — you already saved them there.

## 3. Log in once

After deploy, open your app's admin panel (`/admin`):

1. Status shows **Waiting for your Telegram login code**.
2. Telegram sends you a code — type it in the box that appears.
3. Status changes to **Running — verifying automatically**. Done: the session
   is saved, so Railway restarts never ask for a code again.

## 4. Test it

Send an 8–9 digit Trader ID to **@AmirfxPO_bot**. The helper forwards it to
your affiliate bot and the bot replies with the verified balance within
about a minute.

## Files

- `bot.py` — the helper
- `reply_matching.py` — fresh-reply and Trader ID matching rules
- `session_login.py` — saved-session authorization rules
- `generate_session.py` — local, private QR session generator
- `test_session_login.py` — saved-session and redeployment regression checks
- `test_reply_matching.py` — regression checks (run `python -m unittest`)
- `requirements.txt` — Python packages
- `Dockerfile` — build instructions for Railway
- `railway.json` — Railway build/deploy settings

Optional variables (rarely needed):

- `AFFILIATE_QUERY_TEMPLATE` — what gets sent to the affiliate bot; `{id}` is
  the trader ID. Default: `{id}`
- `POLL_SECONDS` — how often to check for new IDs (default 8)
- `REPLY_TIMEOUT` — seconds to wait for the affiliate bot (default 90)
