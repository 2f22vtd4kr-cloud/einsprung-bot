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
    port = int(os.getenv("PORT", 8443))
    url = os.getenv("WEBHOOK_URL")
    
    if not url:
        log.error("WEBHOOK_URL is required.")
        sys.exit(1)

    # 1. Initialize the app first!
    await app.initialize()
    
    # 2. Set webhook
    await app.bot.set_webhook(
        url=f"{url}/webhook",
        allowed_updates=["message", "callback_query", "pre_checkout_query"]
    )
    
    # 3. Start the application and the updater
    await app.start()
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=f"{url}/webhook"
    )
    
    # 4. CRITICAL: Keep the process alive by waiting for an event
    log.info("Webhook server is running...")
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

