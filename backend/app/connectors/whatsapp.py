"""WhatsApp payload normalizer for Evolution API webhook format."""

from typing import Optional


def extract_text_and_group(payload: dict) -> tuple[str, str]:
    """
    Normalize an incoming webhook payload to (raw_text, source_group).

    Handles two formats:
    1. Evolution API real format  — payload has a "data" key
    2. Test/curl format           — payload has "text" and "group" keys directly

    Evolution API payload structure:
    {
        "event": "messages.upsert",
        "instance": "campusflow",
        "data": {
            "key": {
                "id": "MSG_ID",
                "remoteJid": "120363XXXXXXXX@g.us",
                "fromMe": false
            },
            "message": {
                "conversation": "actual message text here"
                # OR for quoted/extended messages:
                # "extendedTextMessage": {"text": "actual message text here"}
            },
            "messageTimestamp": 1718234400,
            "pushName": "Sender Name"
        }
    }
    """
    # Evolution API format
    if "data" in payload:
        data = payload["data"]

        # Extract message text — try conversation first, then extendedTextMessage
        message_obj = data.get("message", {})
        raw_text: str = (
            message_obj.get("conversation")
            or message_obj.get("extendedTextMessage", {}).get("text")
            or message_obj.get("imageMessage", {}).get("caption")
            or ""
        )

        # Extract group identifier from remoteJid
        # Group JIDs end in @g.us, individual chats end in @s.whatsapp.net
        remote_jid: str = data.get("key", {}).get("remoteJid", "unknown")
        sender_name: str = data.get("pushName", "unknown")

        if "@g.us" in remote_jid:
            # Group message — use the numeric group ID as group name
            source_group = f"group_{remote_jid.split('@')[0]}"
        else:
            # Direct message — use sender name
            source_group = sender_name

        return raw_text, source_group

    # Fallback: test/curl format {"text": "...", "group": "..."}
    return payload.get("text", ""), payload.get("group", "unknown")
