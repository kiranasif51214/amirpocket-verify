# Pocket Option auto-verification helper (Railway) — v4

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
- `test_reply_matching.py` — regression checks (run `python -m unittest`)
- `requirements.txt` — Python packages
- `Dockerfile` — build instructions for Railway
- `railway.json` — Railway build/deploy settings

Optional variables (rarely needed):

- `AFFILIATE_QUERY_TEMPLATE` — what gets sent to the affiliate bot; `{id}` is
  the trader ID. Default: `{id}`
- `POLL_SECONDS` — how often to check for new IDs (default 8)
- `REPLY_TIMEOUT` — seconds to wait for the affiliate bot (default 90)
