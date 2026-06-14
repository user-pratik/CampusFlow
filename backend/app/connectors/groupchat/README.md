# Group Chat Connector

## Status: NOT READY — Awaiting Real Data Source

This connector is a **skeleton** prepared for when group chat access is available.
It follows the same normalizer pattern as `connectors/whatsapp.py`.

## What's Needed Before Activation

1. **Identify the data source**: Which platform delivers group chat messages?
   - WhatsApp groups via Evolution API? (already handled by `connectors/whatsapp.py`)
   - Telegram groups?
   - Discord channels?
   - A custom webhook?

2. **Capture real sample payloads**: Get 5-10 real webhook/API payloads from the
   actual group chat source. Save them as `sample_payloads.json` in this directory.

3. **Update `normalizer.py`**: Replace the placeholder `extract_text_and_group()`
   with parsing logic based on the real payload structure.

4. **Set `GROUPCHAT_ENABLED=true`** in `.env` to activate processing.

## Architecture (Ready to Wire)

```
Webhook/Message → normalizer.extract_text_and_group()
                       ↓
              classifier.classify_group_message()
                       ↓
              ┌─── category == "DEADLINE" → deadline_aggregator
              ├─── category == "PLACEMENT" → placement_prep_agent
              └─── category == "NOTICE" → notice pipeline (existing)
```

## Integration Points

Once activated, classified messages feed into:
- `deadline_aggregator.py` → `extract_deadlines_from_emails()` pattern (adapted for groupchat)
- `placement_prep_agent.py` → `extract_placement_drives()` pattern (adapted for groupchat)
- Existing Notice pipeline via `notices` router

The `processor.py` module orchestrates this routing.
