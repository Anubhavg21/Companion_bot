# CaringX Telegram Bot

## Run locally

1. Use Python 3.11 or newer.
2. Create and activate a virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and set `BOT_TOKEN`, `OPENROUTER_API_KEY`,
   and `ADMIN_ID`.
5. Run `python main.py`.
6. Open the bot in Telegram and send `/start` to the configured admin account.

Only the configured admin account can start conversations or use reminder
buttons.

The bot sends reminders using the `Asia/Kolkata` timezone. Keep the process
running continuously for reminders to fire.

## Deployment

- `render.yaml` configures this as a Render background worker. Create a
  Blueprint from the repository and provide the requested `BOT_TOKEN`,
  `OPENROUTER_API_KEY`, and `ADMIN_ID` values in Render's environment settings.
  Keep `.env` out of the repository.
- Render background workers require a paid compute plan; free Render service
  instances do not include background workers. Review the plan and price shown
  by Render before creating the service.
- Run one worker only. This bot uses Telegram long polling, so multiple
  instances with the same bot token will conflict.
- SQLite is only for conversation history, not required bot infrastructure.
  By default it writes `memory.db` in the worker's local filesystem. On Render
  that filesystem is ephemeral, so history can be lost on restart or deploy.
  For a single-user bot, this is fine if you do not need durable history. If
  you do, attach a persistent disk and set `DB_PATH` to a database file on its
  mount path (for example, `/data/memory.db`); a disk may add cost.
- Back up the database securely. It stores conversation messages indefinitely;
  the model receives up to 25 prior messages plus the current message.
- Confirm the bot can reach both Telegram and OpenRouter from the host, then
  check the worker logs after startup and after a scheduled reminder time.

The bot has no web server or health-check endpoint; deploy it as a continuously
running worker, not as a web service or a scale-to-zero service.
