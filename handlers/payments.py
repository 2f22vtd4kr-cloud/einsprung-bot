import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes, ConversationHandler
from config import PLATFORMFEEPCT, STARS_PROVIDER_TOKEN
import database as db

# Fix: Log variable assignment corrected
log = logging.getLogger(__name__)
WIZ_TOPUP_AMOUNT = 1

async def menuwallet(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Displays the user's financial balance interface."""
    uid = u.effective_user.id
    balance = db.get_user_balance(uid)
    
    txt = (
        f"💳 **Deine Geldbörse (Wallet)**\n\n"
        f"**Aktuelles Guthaben:** {balance} EUR\n\n"
        f"Du benötigst Guthaben, um Aufträge zu erstellen. Experten können "
        f"verdientes Guthaben über den Support zur Auszahlung anfordern."
    )
    kbd = [
        [InlineKeyboardButton("➕ Guthaben aufladen (Telegram Stars)", callback_data="wallet:topup:stars")],
        [InlineKeyboardButton("⬅️ Hauptmenü", callback_data="menu:start")]
    ]
    
    if u.callback_query:
        await u.callback_query.answer()
        await u.callback_query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    else:
        await u.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def wallettopupstarscb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Initiates topup conversation state sequence."""
    q = u.callback_query
    await q.answer()
    
    # Fix: Cleaned up undefined variable name evaluation expression parsing crash bug
    fee_pct = int(PLATFORMFEEPCT * 100)
    
    await q.message.edit_text(
        f"💳 **Guthaben aufladen**\n\n"
        f"Wie viel Euro möchtest du aufladen? (Ganze Zahl, z.B. 10).\n"
        f"Es wird zusätzlich eine Plattformgebühr von {fee_pct}% abgezogen.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")]])
    )
    return WIZ_TOPUP_AMOUNT

async def stepamounttopup(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Sends native invoice calculation via Telegram Stars."""
    txt = u.message.text.strip()
    try:
        amount = int(txt)
        if amount <= 0: raise ValueError()
    except ValueError:
        await u.message.reply_text("⚠️ Bitte gib eine gültige Zahl größer als 0 ein:")
        return WIZ_TOPUP_AMOUNT
        
    # Rate: 1 Euro = 50 Stars
    stars_price = amount * 50
    title = f"Wallet-Aufladung: {amount} EUR"
    desc = f"Fügt deiner Wallet {amount} EUR hinzu. Preis beinhaltet Systemgebühren."
    payload = f"topup:{u.effective_user.id}:{amount}"
    currency = "XTR" # Currency code for Telegram Stars
    
    prices = [LabeledPrice("Aufladung + Gebühr", stars_price)]
    
    await u.message.reply_invoice(
        title=title,
        description=desc,
        payload=payload,
        provider_token=STARS_PROVIDER_TOKEN,
        currency=currency,
        prices=prices
    )
    return ConversationHandler.END

async def precheckoutcallback(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Intercepts and answers checking requests before processing payments."""
    pq = u.pre_checkout_query
    if pq.invoice_payload.startswith("topup:"):
        await pq.answer(ok=True)
    else:
        await pq.answer(ok=False, error_message="Ungültiger Payload.")

async def successfulpaymentcallback(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Confirms receipt and updates the user's database balance."""
    msg = u.message.successful_payment
    payload = msg.invoice_payload
    _, uid_str, amount_str = payload.split(":")
    
    uid = int(uid_str)
    amount = int(amount_str)
    
    # Update user's wallet balance in database
    db.add_user_balance(uid, amount)
    log.info(f"Successfully processed payment credit payload topup: User {uid} added +{amount} EUR.")
    
    await u.message.reply_text(
        f"✅ Zahlung erfolgreich erhalten!**\n\nDeiner Wallet wurden **{amount} EUR gutgeschrieben.",
        parse_mode="Markdown"
    )
