# Deploy Checklist

This project is ready for deploy after you complete the steps below.

## 1. Security First

1. Revoke current bot token in BotFather and create a new one.
2. Put the new token only in server environment variables.
3. Never commit `.env` with production secrets.

## 2. Required Environment Variables

Use `.env.example` as a template.

Required:
- `BOT_TOKEN`
- `DATABASE_URL`
- `RUN_MODE` (`polling` or `webhook`)
- `ADMIN_IDS`
- `GROUP_CHAT_ID`

For webhook mode:
- `WEBHOOK_URL` (base URL like `https://bot.example.com` or full URL with path)
- `WEBHOOK_PATH` (default `/webhook`)
- `APP_HOST` (default `0.0.0.0`)
- `APP_PORT` (default `8080`)

## 3. Database

Recommended for production: PostgreSQL.

Example:
`DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname`

Notes:
- Tables are created automatically at startup (`create_all`).
- For long-term production use, add Alembic migrations later.

## 4. Install and Run

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m app.main
```

## 5. Run Mode Choice

### Polling (simpler)
- Set `RUN_MODE=polling`
- Do not run multiple replicas with polling.

### Webhook (recommended for production platforms)
- Set `RUN_MODE=webhook`
- Ensure public HTTPS endpoint is reachable.
- Ensure reverse proxy forwards to `APP_HOST:APP_PORT`.

## 6. Telegram Group/Topics Validation

Before production use, verify:
1. Bot is in target supergroup.
2. Bot has permission to post messages.
3. `GROUP_CHAT_ID` is correct.
4. `CITY_TOPIC_*` thread IDs are correct.

## 7. Smoke Test After Deploy

1. `/start` works.
2. `/help` shows full instructions.
3. Admin: `/admin` and admin buttons work.
4. Manager flow: `/new_order` creates and publishes an order.
5. Master flow: respond -> accept -> upload photos -> finish.
6. Export commands return CSV files.

## 8. Operational Notes

- Current FK mapping uses Telegram IDs (`users.telegram_id`) for manager/master links.
- If you already have an old DB created with previous schema, recreate DB or run migration before switching to PostgreSQL.
