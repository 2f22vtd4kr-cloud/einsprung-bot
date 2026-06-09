"""Bot bootstrap: init DB, register handlers, support polling + webhooks."""
import asyncio
import logging
import os
import sys
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
    """Run with webhooks (recommended for production)."""
    port = int(os.getenv("PORT", 8443))
    url = os.getenv("WEBHOOK_URL")  # e.g. https://yourapp.railway.app
    
    if not url:
        log.error("WEBHOOK_URL environment variable is required for webhook mode.")
        sys.exit(1)

    await app.bot.set_webhook(
        url=f"{url}/webhook",
        allowed_updates=["message", "callback_query", "pre_checkout_query"]
    )
    log.info(f"Webhook set to {url}/webhook")
    
    await app.start()
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=f"{url}/webhook"
    )

def main():
    app = buildapp()
    
    # Choose mode based on environment
    if os.getenv("MODE") == "webhook":
        asyncio.run(run_webhook(app))
    else:
        # Default: Polling (good for local testing)
        app.run_polling(allowed_updates=["message", "callback_query", "pre_checkout_query"])

if __name__ == "__main__":
    main()
