"""Bot bootstrap: init DB, register handlers, support polling + webhooks."""
import asyncio
import logging
import os
import sys

# Crucial for cloud runtimes like Render: ensure root workspace is discoverable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram.ext import ApplicationBuilder

from config import BOTTOKEN
import database
from handlers import common, auftraggeber, experte, bridge, admin, payments, miniapp, direct

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("einsprung")

async def postinit(application):
    await database.initdb()
    # Background invoice polling
    asyncio.create_task(payments.pollinvoices(application))
    log.info("Ein Sprung 🐸 started successfully.")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.DEBUG, # Change from INFO to DEBUG
)

def buildapp():
    if not BOTTOKEN:
        raise RuntimeError("BOTTOKEN ist nicht gesetzt.")
    
    app = ApplicationBuilder().token(BOTTOKEN).post_init(postinit).build()

    # Register handlers (order matters)
    common.register(app)
    auftraggeber.register(app)
    direct.register(app)
    payments.register(app)
    experte.register(app)
    admin.register(app)
    miniapp.register(app)
    bridge.register(app)
    return app

async def run_webhook(app):
    # 1. ALWAYS initialize the app before doing anything
    await app.initialize()

    port = int(os.getenv("PORT", 10000))
    url = os.getenv("WEBHOOK_URL")

    # 2. Set webhook (wrap in try/except to avoid 429 crashes)
    try:
        await app.bot.set_webhook(url=f"{url}/webhook")
    except Exception as e:
        log.warning(f"Note on webhook setting: {e}")

    # 3. Start the application
    await app.start()

    # 4. Start the webhook server
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=f"{url}/webhook"
    )

    # 5. This is the "blocker" that keeps the process alive
    log.info("Bot is running and waiting for requests...")
    await asyncio.Event().wait()

async def main():
    app = buildapp()
    if os.getenv("MODE") == "webhook":
        await run_webhook(app)
    else:
        # For polling, you also need to initialize
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    # Correctly run the async main function
    asyncio.run(main())

