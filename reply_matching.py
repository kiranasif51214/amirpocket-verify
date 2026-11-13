"""Pure reply correlation rules, shared by the helper and its tests."""
import re


def reply_kind(text, trader_id):
    text = (text or "").replace("`", "").replace("*", "")
    uid = re.search(r"(?:UID:\s*|Trader\s*#\s*)(\d+)", text, re.I)
    if uid:
        return "verified" if uid.group(1) == trader_id else "mismatch"
    if re.search(r"user\s+not\s+found|was\s+not\s+found", text, re.I):
        return "not_found"
    if re.search(r"/user\s+\{uid\}", text, re.I):
        return "command_hint"
    return "ignore"


def correlated_kind(message, sender_id, sent_id, trader_id):
    if message.sender_id != sender_id or message.id <= sent_id:
        return "ignore"
    reply_to = getattr(message, "reply_to_msg_id", None)
    if reply_to is not None and reply_to != sent_id:
        return "ignore"
    return reply_kind(message.text, trader_id)