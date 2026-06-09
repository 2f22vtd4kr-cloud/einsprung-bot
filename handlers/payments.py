import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

log = logging.getLogger("einsprung.handlers.payments")

async def menuwallet(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    user_row = await db.getuser(uid)
    balance = user_row["balanceusdt"] if user_row else 0.0
    
    txt = (
        f"💳 **Deine Geldbörse (Wallet)**\n\n"
        f"**Aktuelles Guthaben:** {balance:.2f} USDT\n\n"
        f"Guthaben-Aufladungen werden via CryptoBot oder Mini-App verarbeitet."
    )
    kbd = [[InlineKeyboardButton("⬅️ Hauptmenü", callback_data="menu:start")]]
    
    if u.callback_query:
        await u.callback_query.answer()
        await u.callback_query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    else:
        await u.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def pollinvoices(application):
    """Placeholder function required by main.py postinit sequence."""
    pass

def register(app):
    from telegram.ext import CallbackQueryHandler, CommandHandler
    app.add_handler(CallbackQueryHandler(menuwallet, pattern=r"^menu:wallet$"))
    app.add_handler(CommandHandler("wallet", menuwallet))
