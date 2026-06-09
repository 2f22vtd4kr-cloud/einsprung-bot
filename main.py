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
    """Run with webhooks safely bypassing unnecessary set_webhook rate-limits."""
    port = int(os.getenv("PORT", 8443))
    url = os.getenv("WEBHOOK_URL")  # e.g. https://einsprung-bot.onrender.com
    
    if not url:
        log.error("WEBHOOK_URL environment variable is required for webhook mode.")
        sys.exit(1)

    target_webhook_url = f"{url}/webhook"

    # --- SAFE CHECK TO PREVENT FLOOD LIMITS ---
    try:
        current_info = await app.bot.get_webhook_info()
        if current_info.url == target_webhook_url:
            log.info("✅ Webhook URL already configured correctly. Skipping set_webhook endpoint.")
        else:
            log.info(f"🔄 Updating Webhook URL to: {target_webhook_url}")
            await app.bot.set_webhook(
                url=target_webhook_url,
                allowed_updates=["message", "callback_query", "pre_checkout_query"]
            )
    except Exception as e:
        log.warning(f"Could not verify or set webhook safely: {e}. Attempting standard run.")

    await app.start()
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=target_webhook_url
    )
    
async def main():
    app = buildapp()
    # ... your webhook setup logic ...
    
    # IMPORTANT: Use run_polling() OR start the webhook server and keep it alive
    # If you are using webhooks, you need to keep the event loop running:
    await app.initialize()
    await app.start()
    await app.updater.start_webhook(...)
    
    # This block prevents the script from exiting immediately
    log.info("Bot is running...")
    await asyncio.Event().wait() 

    # Choose mode based on environment
    if os.getenv("WEBHOOK_MODE", "false").lower() == "true" or os.getenv("WEBHOOK_URL"):
        asyncio.run(run_webhook(app))
    else:
        log.info("Starting bot in local polling mode...")
        app.run_polling(allowed_updates=["message", "callback_query", "pre_checkout_query"])

if __name__ == "__main__":
    main()
