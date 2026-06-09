import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from config import PLATFORMFEEPCT
import database as db

log = logging.getLogger("einsprung.handlers.auftraggeber")

(WIZ_TITLE, WIZ_DESC, WIZ_CAT, WIZ_REWARD, WIZ_ATTACH) = range(5)
CATEGORIES = ["Hausarbeit", "Abschlussarbeit", "Programmierung", "Lektorat", "Allgemein"]

async def menuag(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    txt = (
        "💼 **Auftraggeber-Menü**\n\n"
        "Hier kannst du neue Aufgaben ausschreiben oder deine bereits erstellten "
        "Aufträge einsehen."
    )
    kbd = [
        [InlineKeyboardButton("➕ Neuen Auftrag erstellen", callback_data="ag:new")],
        [InlineKeyboardButton("📂 Meine Aufträge verwalten", callback_data="ag:manage")],
        [InlineKeyboardButton("⬅️ Hauptmenü", callback_data="menu:start")]
    ]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def wizardstart(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    c.user_data.clear()
    
    await q.message.edit_text(
        "📝 **Schritt 1: Titel**\n\nBitte sende mir einen kurzen Titel für deinen Auftrag.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")]])
    )
    return WIZ_TITLE

async def steptitle(u: Update, c: ContextTypes.DEFAULT_TYPE):
    txt = u.message.text.strip()
    if len(txt) < 5 or len(txt) > 80:
        await u.message.reply_text("⚠️ Der Titel muss zwischen 5 und 80 Zeichen lang sein. Versuche es erneut:")
        return WIZ_TITLE
    
    c.user_data["title"] = txt
    await u.message.reply_text(
        "📄 **Schritt 2: Beschreibung**\n\nBeschreibe die Aufgabe detailliert:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")]])
    )
    return WIZ_DESC

async def stepdesc(u: Update, c: ContextTypes.DEFAULT_TYPE):
    txt = u.message.text.strip()
    if len(txt) < 20:
        await u.message.reply_text("⚠️ Die Beschreibung ist zu kurz (mind. 20 Zeichen):")
        return WIZ_DESC
    
    c.user_data["desc"] = txt
    kbd = [[InlineKeyboardButton(cat, callback_data=f"wiz:cat:{cat}")] for cat in CATEGORIES]
    kbd.append([InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")])
    
    await u.message.reply_text("🗂 **Schritt 3: Kategorie**\n\nWähle eine Kategorie aus:", reply_markup=InlineKeyboardMarkup(kbd))
    return WIZ_CAT

async def stepcategorycb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    _, _, cat = q.data.split(":", 2)
    c.user_data["cat"] = cat
    
    await q.message.edit_text(
        "💰 **Schritt 4: Belohnung (USDT)**\n\nWie viel USDT möchtest du zahlen?\n"
        "(Zahl eingeben, z.B. 25).",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")]])
    )
    return WIZ_REWARD

async def stepreward(u: Update, c: ContextTypes.DEFAULT_TYPE):
    txt = u.message.text.strip()
    try:
        val = float(txt)
        if val <= 0: raise ValueError()
    except ValueError:
        await u.message.reply_text("⚠️ Bitte gib eine gültige positive Zahl ein:")
        return WIZ_REWARD
    
    uid = u.effective_user.id
    user_row = await db.getuser(uid)
    balance = user_row["balanceusdt"] if user_row else 0.0
    
    if balance < val:
        kbd = [[InlineKeyboardButton("💳 Wallet aufladen", callback_data="menu:wallet")], [InlineKeyboardButton("⬅️ Zurück zum Menü", callback_data="menu:start")]]
        await u.message.reply_text(
            f"❌ **Unzureichendes Guthaben!**\n\nDieser Auftrag kostet {val} USDT, dein Guthaben beträgt jedoch nur {balance:.2f} USDT.",
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
        "📎 **Schritt 5: Anhänge (Optional)**\n\nSende mir jetzt Dateien als Anhang.\n"
        "Wenn du fertig bist, klicke unten auf Fertigstellen.",
        reply_markup=InlineKeyboardMarkup(kbd)
    )
    return WIZ_ATTACH

async def stepattach(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg = u.message
    file_id = None
    if msg.document: 
        file_id = msg.document.file_id
    elif msg.photo: 
        file_id = msg.photo[-1].file_id
        
    if not file_id:
        await msg.reply_text("⚠️ Sende ein Dokument oder ein Bild als Anhang:")
        return WIZ_ATTACH
        
    c.user_data["attachments"].append(file_id)
    kbd = [
        [InlineKeyboardButton(f"✅ Fertigstellen ({len(c.user_data['attachments'])} Anhänge)", callback_data="wiz:attach:done")],
        [InlineKeyboardButton("❌ Abbrechen", callback_data="wiz:cancel")]
    ]
    await msg.reply_text("📎 Anhang hinzugefügt! Du kannst einen weiteren senden oder fertigstellen:", reply_markup=InlineKeyboardMarkup(kbd))
    return WIZ_ATTACH

async def stepattachdonecb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    uid = u.effective_user.id
    ud = c.user_data
    
    user_row = await db.getuser(uid)
    balance = user_row["balanceusdt"] if user_row else 0.0
    if balance < ud["reward"]:
        await q.message.edit_text("❌ Fehler beim Erstellen: Kontostand unzureichend.")
        c.user_data.clear()
        return ConversationHandler.END

    reward_gross = float(ud["reward"])
    reward_net = round(reward_gross * (1.0 - PLATFORMFEEPCT), 8)

    taskid = await db.createtask(
        clientid=uid,
        title=ud["title"],
        description=ud["desc"],
        rewardgross=reward_gross,
        rewardnet=reward_net,
        category=ud["cat"],
        attachments=json.dumps(ud["attachments"])
    )
    
    await q.message.edit_text(
        f"🎉 **Auftrag erfolgreich erstellt!**\n\n"
        f"**ID:** #{taskid}\n"
        f"**Budget:** {reward_gross} USDT\n\n"
        f"Experten können deinen Auftrag ab sofort einsehen.",
        parse_mode="Markdown"
    )
    c.user_data.clear()
    return ConversationHandler.END

async def menuagmanage(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    uid = u.effective_user.id
    
    async with db.conn() as database_conn:
        cur = await database_conn.execute("SELECT * FROM tasks WHERE clientid = ? ORDER BY taskid DESC", (uid,))
        tasks = await cur.fetchall()
        
    if not tasks:
        await q.message.edit_text(
            "📭 Du hast bisher keine Aufträge erstellt.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Zurück", callback_data="menu:ag")]])
        )
        return
        
    txt = "📂 **Deine Aufträge:**\n\n"
    kbd = []
    for t in tasks:
        txt += f"• `#{t['taskid']}` - **{t['title']}** ({t['status'].upper()}) - {t['rewardgross']} USDT\n"
        kbd.append([InlineKeyboardButton(f"👁️ #{t['taskid']} Details", callback_data=f"ag:view:{t['taskid']}")])
        
    kbd.append([InlineKeyboardButton("⬅️ Zurück", callback_data="menu:ag")])
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def viewtaskcb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    _, _, taskid = q.data.split(":", 2)
    taskid = int(taskid)
    
    t = await db.gettask(taskid)
    if not t:
        await q.message.edit_text("❌ Auftrag nicht gefunden.")
        return
        
    txt = (
        f"📊 **Auftragsdetails `#{t['taskid']}`**\n\n"
        f"**Status:** {t['status'].upper()}\n"
        f"**Titel:** {t['title']}\n"
        f"**Kategorie:** {t['category']}\n"
        f"**Budget:** {t['rewardgross']} USDT\n\n"
        f"📝 **Beschreibung:**\n{t['description']}"
    )
    
    kbd = []
    if t["status"] in ["inprogress"]:
        kbd.append([InlineKeyboardButton("💬 Zum Workspace-Chat", callback_data=f"bridge:go:{t['taskid']}")])
    
    kbd.append([InlineKeyboardButton("⬅️ Zurück zur Liste", callback_data="ag:manage")])
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def cancel_wiz(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.callback_query: await u.callback_query.answer()
    c.user_data.clear()
    return ConversationHandler.END

def register(app):
    ag_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(wizardstart, pattern=r"^ag:new$")],
        states={
            WIZ_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, steptitle)],
            WIZ_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, stepdesc)],
            WIZ_CAT: [CallbackQueryHandler(stepcategorycb, pattern=r"^wiz:cat:")],
            WIZ_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, stepreward)],
            WIZ_ATTACH: [
                CallbackQueryHandler(stepattachdonecb, pattern=r"^wiz:attach:done$"),
                MessageHandler(filters.ALL & ~filters.COMMAND, stepattach)
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel_wiz, pattern=r"^wiz:cancel$")],
        per_message=False
    )
    app.add_handler(ag_conv)
    app.add_handler(CallbackQueryHandler(menuag, pattern=r"^menu:ag$"))
    app.add_handler(CallbackQueryHandler(menuagmanage, pattern=r"^ag:manage$"))
    app.add_handler(CallbackQueryHandler(viewtaskcb, pattern=r"^ag:view:"))
