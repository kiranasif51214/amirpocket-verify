"""Saved-session selection and authorization without exposing credentials."""


class SessionLoginRequired(RuntimeError):
    """An explicitly supplied session cannot be silently replaced by code login."""


def select_session(config, environment):
    supplied = (environment.get("TG_SESSION") or "").strip()
    return supplied or config.get("session_string") or None, bool(supplied)


async def authorize_session(api, client, config, session, explicit, login_flow):
    if await client.is_user_authorized():
        await api.post_bridge({
            "session_string": client.session.save(),
            "clear_code": True,
            "status": "running",
        })
        return
    if explicit:
        await api.post_bridge({"status": "restart_needed"})
        raise SessionLoginRequired(
            "TG_SESSION is expired or revoked. Generate a new session and replace "
            "TG_SESSION in Railway. No login code was requested."
        )
    if session:
        await api.post_bridge({"session_string": None, "status": "restart_needed"})
    await login_flow(api, client, config)


SESSION_DUPLICATED_MESSAGE = (
    "Telegram revoked TG_SESSION because it was used from two places at the same time "
    "(AuthKeyDuplicatedError). This session can never work again. Stop every other "
    "helper/computer using it, generate a NEW session with generate_session.py, replace "
    "TG_SESSION in Railway, and keep only one replica running."
)


async def report_duplicated_session(api):
    """Tell the admin panel the session is dead; never retry it (retrying cannot help)."""
    try:
        await api.post_bridge({"session_string": None, "status": "restart_needed"})
    except Exception:  # noqa: BLE001
        pass
