import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import BOTUSERNAME

log = logging.getLogger("einsprung.handlers.common")

async def cmdstart(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command and displays the main menu."""
    uid = u.effective_user.id
    log.info(f"User {uid} started the bot.")
    
    txt = (
        "👋 **Willkommen bei Ein Sprung 🐸**\n\n"
        "Hier kannst du entweder als Auftraggeber akademische Aufgaben ausschreiben oder "
        "als Experte Aufträge annehmen und USDT verdienen.\n\n"
        "Bitte wähle deine Option aus dem Menü unten:"
    )
    
    kbd = [
        [InlineKeyboardButton("💼 Auftraggeber-Menü", callback_data="menu:ag")],
        [InlineKeyboardButton("🎓 Experten-Menü", callback_data="menu:exp")],
        [InlineKeyboardButton("💳 Geldbörse / Wallet", callback_data="menu:wallet")]
    ]
    
    if u.message:
        await u.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    elif u.callback_query:
        await u.callback_query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def cmdcancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Global fallback cancel command for conversations."""
    q = u.callback_query
    if q:
        await q.answer()
        await q.message.edit_text("❌ Vorgang abgebrochen.")
    else:
        await u.effective_message.reply_text("❌ Vorgang abgebrochen.")
    
    c.user_data.clear()
    await cmdstart(u, c)
    return ConversationHandler.END

def register(app):
    """Registers basic structural components."""
    from telegram.ext import CommandHandler, CallbackQueryHandler
    app.add_handler(CommandHandler("start", cmdstart))
    app.add_handler(CommandHandler("cancel", cmdcancel))
    app.add_handler(CallbackQueryHandler(cmdstart, pattern=r"^menu:start$"))
