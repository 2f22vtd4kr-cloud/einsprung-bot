import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import CATEGORIES, MAXATTACHMENTTOTALMB
import database as db

# Fix: Syntax multiplication logic and string name bug resolved
log = logging.getLogger(__name__)
MAXBYTES = MAXATTACHMENTTOTALMB * 1024 * 1024

(WIZ_TITLE, WIZ_DESC, WIZ_CAT, WIZ_REWARD, WIZ_ATTACH) = range(5)

async def menuag(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Displays the Client (Auftraggeber) Main Menu."""
    q = u.callback_query
    await q.answer()
    
    txt = (
        "💼 **Auftraggeber-Menü**\n\n"
        "Hier kannst du neue Aufgaben ausschreiben oder deine bereits erstellten "
        "Aufträge und aktiven Sessions einsehen."
    )
    kbd = [
        [InlineKeyboardButton("➕ Neuen Auftrag erstellen", callback_data="ag:new")],
        [InlineKeyboardButton("📂 Meine Aufträge verwalten", callback_data="ag:manage")],
        [InlineKeyboardButton("⬅️ Hauptmenü", callback_data="menu:start")]
    ]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def wizardstart(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Starts the creation wizard for a new job/task."""
    q = u.callback_query
    await q.answer()
    c.user_data.clear()
    
    await q.message.edit_text(
        "📝 **Schritt 1: Titel**\n\nBitte sende mir einen kurzen, aussagekräftigen Titel für deinen Auftrag.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")]])
    )
    return WIZ_TITLE

async def steptitle(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Saves the title and requests the description."""
    txt = u.message.text.strip()
    if len(txt) < 5 or len(txt) > 80:
        await u.message.reply_text("⚠️ Der Titel muss zwischen 5 und 80 Zeichen lang sein. Bitte versuche es erneut:")
        return WIZ_TITLE
    
    c.user_data["title"] = txt
    await u.message.reply_text(
        "📄 **Schritt 2: Beschreibung**\n\nBeschreibe die Aufgabe nun so detailliert wie möglich:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")]])
    )
    return WIZ_DESC

async def stepdesc(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Saves description and asks for the category choice via inline buttons."""
    txt = u.message.text.strip()
    if len(txt) < 20:
        await u.message.reply_text("⚠️ Die Beschreibung ist zu kurz. Bitte liefere mehr Details (mind. 20 Zeichen):")
        return WIZ_DESC
    
    c.user_data["desc"] = txt
    
    kbd = [[InlineKeyboardButton(cat, callback_data=f"wiz:cat:{cat}")] for cat in CATEGORIES]
    kbd.append([InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")])
    
    await u.message.reply_text("🗂 **Schritt 3: Kategorie**\n\nWähle eine passende Kategorie aus:", reply_markup=InlineKeyboardMarkup(kbd))
    return WIZ_CAT

async def stepcategorycb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Saves selected category and asks for the reward payout amount."""
    q = u.callback_query
    await q.answer()
    
    # Fix: Tuple unpacking variable names cleaned up
    _, _, cat = q.data.split(":", 2)
    c.user_data["cat"] = cat
    
    await q.message.edit_text(
        "💰 **Schritt 4: Belohnung (EUR)**\n\nWie viel Euro möchtest du für die Erfüllung zahlen?\n"
        "(Ganze Zahl, z.B. 25. Dein Wallet muss gedeckt sein).",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")]])
    )
    return WIZ_REWARD

async def stepreward(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Validates payment balance capability and asks for file attachments."""
    txt = u.message.text.strip()
    try:
        val = int(txt)
        if val <= 0: raise ValueError()
    except ValueError:
        await u.message.reply_text("⚠️ Bitte gib eine gültige, positive Ganzzahl ein:")
        return WIZ_REWARD
    
    uid = u.effective_user.id
    balance = db.get_user_balance(uid)
    if balance < val:
        # Fix: Cleanly reset reply markup so the user isn't stuck with an empty UI
        kbd = [[InlineKeyboardButton("💳 Geldbörse aufladen", callback_data="menu:wallet")], [InlineKeyboardButton("⬅️ Zurück zum Menü", callback_data="menu:start")]]
        await u.message.reply_text(
            f"❌ **Unzureichendes Guthaben!**\n\nDieser Auftrag kostet {val} EUR, dein Guthaben beträgt jedoch nur {balance} EUR.",
            reply_markup=InlineKeyboardMarkup(kbd),
            parse_mode="Markdown"
        )
        c.user_data.clear()
        return ConversationHandler.END
        
    c.user_data["reward"] = val
    c.user_data["attachments"] = []
    
    kbd = [
        [InlineKeyboardButton("✅ Keine Anhänge / Fertigstellen", callback_data="wiz:attach:done")],
        [InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")]
    ]
    await u.message.reply_text(
        "📎 **Schritt 5: Anhänge (Optional)**\n\nSende mir jetzt Dateien, Dokumente oder Bilder als Anhang.\n"
        "Wenn du fertig bist oder keine Anhänge hinzufügen willst, klicke unten auf Fertigstellen.",
        reply_markup=InlineKeyboardMarkup(kbd)
    )
    return WIZ_ATTACH

async def stepattach(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Collects individual files/attachments sent by the user."""
    msg = u.message
    file_id = None
    file_type = None
    
    if msg.document:
        file_id = msg.document.file_id
        file_type = "document"
    elif msg.photo:
        file_id = msg.photo[-1].file_id
        file_type = "photo"
    elif msg.audio:
        file_id = msg.audio.file_id
        file_type = "audio"
    elif msg.video:
        file_id = msg.video.file_id
        file_type = "video"
        
    if not file_id:
        await msg.reply_text("⚠️ Dieses Dateiformat wird nicht unterstützt. Sende ein Dokument, Bild oder Video:")
        return WIZ_ATTACH
        
    c.user_data["attachments"].append({"file_id": file_id, "type": file_type})
    
    kbd = [
        [InlineKeyboardButton(f"✅ Fertigstellen ({len(c.user_data['attachments'])} Anhänge)", callback_data="wiz:attach:done")],
        [InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")]
    ]
    await msg.reply_text("📎 Anhang hinzugefügt! Du kannst einen weiteren senden oder fertigstellen:", reply_markup=InlineKeyboardMarkup(kbd))
    return WIZ_ATTACH

async def stepattachdonecb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Persists everything to the database, deducts budget escrow, and closes setup."""
    q = u.callback_query
    await q.answer()
    
    uid = u.effective_user.id
    ud = c.user_data
    
    # Final database safety check logic execution
    balance = db.get_user_balance(uid)
    if balance < ud["reward"]:
        await q.message.edit_text("❌ Fehler beim Erstellen: Kontostand unzureichend.")
        c.user_data.clear()
        return ConversationHandler.END

    # Transaction Execution
    taskid = db.create_task(
        ag_id=uid,
        title=ud["title"],
        description=ud["desc"],
        category=ud["cat"],
        reward=ud["reward"],
        attachments=ud["attachments"]
    )
    
    await q.message.edit_text(
        f"🎉 **Auftrag erfolgreich erstellt!**\n\n"
        f"**ID:** #{taskid}\n"
        f"**Titel:** {ud['title']}\n"
        f"**Budget:** {ud['reward']} EUR\n\n"
        f"Experten können deinen Auftrag ab sofort einsehen und annehmen.",
        parse_mode="Markdown"
    )
    c.user_data.clear()
    return ConversationHandler.END

async def menuagmanage(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """View and manage existing tasks owned by the Client."""
    q = u.callback_query
    await q.answer()
    uid = u.effective_user.id
    
    tasks = db.get_user_tasks(uid)
    if not tasks:
        await q.message.edit_text(
            "📭 Du hast bisher keine Aufträge erstellt.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Zurück", callback_data="menu:ag")]])
        )
        return
        
    txt = "📂 **Deine Aufträge:**\n\n"
    kbd = []
    for t in tasks:
        txt += f"• `#{t['taskid']}` - **{t['title']}** ({t['status'].upper()}) - {t['reward']} EUR\n"
        kbd.append([InlineKeyboardButton(f"👁️ #{t['taskid']} Details", callback_data=f"ag:view:{t['taskid']}")])
        
    kbd.append([InlineKeyboardButton("⬅️ Zurück", callback_data="menu:ag")])
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def viewtaskcb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Detailed visual card layout for individual jobs."""
    q = u.callback_query
    await q.answer()
    
    _, _, taskid = q.data.split(":", 2)
    taskid = int(taskid)
    
    t = db.get_task(taskid)
    if not t:
        await q.message.edit_text("❌ Auftrag nicht gefunden.")
        return
        
    txt = (
        f"📊 **Auftragsdetails `#{t['taskid']}`**\n\n"
        f"**Status:** {t['status'].upper()}\n"
        f"**Titel:** {t['title']}\n"
        f"**Kategorie:** {t['category']}\n"
        f"**Belohnung:** {t['reward']} EUR\n\n"
        f"📝 **Beschreibung:**\n{t['description']}"
    )
    
    kbd = []
    # If the job is active and has an associated workspace conversation sequence running
    if t["status"] in ["claimed", "delivered"]:
        kbd.append([InlineKeyboardButton("💬 Zum Workspace-Chat", callback_data=f"bridge:go:{t['taskid']}" )])
    
    kbd.append([InlineKeyboardButton("⬅️ Zurück zur Liste", callback_data="ag:manage")])
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
