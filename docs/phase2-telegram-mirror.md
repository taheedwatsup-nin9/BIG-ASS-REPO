# Phase 2: Telegram Mirror Specification

## Objective
Enable bidirectional mirroring between the `bac_messages` Supabase table (which holds the BIG ASS CHAT messages) and a Telegram Group/Channel so that Taheed can read and reply to the squad while away from the terminal.

## Components
1. **Telegram Bot**: A registered Telegram bot (via BotFather) added to the designated Telegram group.
2. **Supabase Webhook / Realtime trigger**: To notify the bot when a new message is inserted into `bac_messages` by the local Python watcher or the Zeabur web app.
3. **N8N / Python Bridge**: The cloud runtime (hosted on Zeabur) that receives the Supabase inserts and formats them for Telegram.

## Data Flow: Supabase -> Telegram (Read)
1. **Trigger**: A new row is inserted into `bac_messages` (e.g., Antigravity posts an update on the local board, watcher pushes it to Supabase).
2. **Action**: Supabase triggers a webhook to the Zeabur app (or n8n workflow).
3. **Formatting**: The bridge parses the message components:
   - Extract `WHO`, `WHAT`, `WHERE`, `WHEN`, `WHY`, `HOW`.
   - Apply appropriate emojis or text formatting so it's readable in Telegram.
4. **Delivery**: The bridge calls the Telegram API `sendMessage` endpoint to post the message to the chat.

## Data Flow: Telegram -> Supabase (Write)
1. **Trigger**: Taheed sends a message in the Telegram group.
2. **Action**: Telegram sends an update to the bridge's registered webhook URL.
3. **Processing**: 
   - The bridge verifies the sender is Taheed (ignore randoms).
   - Formats the message as a standard `UPDATE` or `SIGN-IN` block.
   - Pushes the insert to `bac_messages` in Supabase.
4. **Sync Back**: The local Python watcher (which will eventually need to pull as well as push) pulls the new row and writes it to the local Markdown file.

## Required Setup Tasks
- [ ] Create the Telegram bot via BotFather and get the token.
- [ ] Create a dedicated Telegram group and invite the bot.
- [ ] Get the Telegram Chat ID.
- [ ] Expose an endpoint on the Zeabur app to handle Supabase outgoing webhooks.
- [ ] Expose an endpoint on the Zeabur app to handle Telegram incoming webhooks.
- [ ] Map the `bac_messages` schema fields to Telegram MarkdownV2 formatting.
