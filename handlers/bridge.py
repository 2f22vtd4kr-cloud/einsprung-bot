import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

# Fix: Log tracking identifier string resolution
log = logging.getLogger(__name__)

async def enterbridge(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Bridges active sessions, putting users into text-forwarding states."""
    q = u.callback_query
    await q.answer()
    
    _, _, taskid = q.data.split(":", 2)
    taskid = int(taskid)
    uid = u.effective_user.id
    
    session = db.get_session(taskid)
    task = db.get_task(taskid)
    if not session or not task:
        await q.message.edit_text("❌ Session wurde nicht gefunden oder bereits archiviert.")
        return
        
    # Assign local tracking values to accurately map downstream text routing inputs
    c.user_data["active_bridge_taskid"] = taskid
    role = "AG" if session["ag_id"] == uid else "EXP"
    c.user_data["bridge_role"] = role
    
    txt = (
        f"🚪 **Du hast den Workspace zu Auftrag `#{taskid}` betreten** ({task['title']}).\n\n"
        f"⚠️ **Regeln:**\n"
        f"• Jede Nachricht (Text, Bilder, Audio, Dokumente), die du ab jetzt abschickst, "
        f"wird anonymisiert an die Gegenseite weitergeleitet.\n"
        f"• Nutze die Knöpfe unten, um Aktionen durchzuführen oder den Chat wieder zu verlassen."
    )
    
    await q.message.edit_text(txt, reply_markup=getbridgekbd(role, taskid, task["status"]), parse_mode="Markdown")

def getbridgekbd(role: str, taskid: int, status: str):
    """Dynamic context routing keyboard logic generator layout control."""
    kbd = []
    if role == "EXP":
        if status == "claimed":
            kbd.append([InlineKeyboardButton("🎁 Ergebnisse liefern / Abgeben", callback_data=f"deal:deliver:{taskid}")])
    elif role == "AG":
        if status == "delivered":
            kbd.append([InlineKeyboardButton("🌟 Freigeben & Auszahlen", callback_data=f"deal:release:{taskid}")])
            
    kbd.append([InlineKeyboardButton("🚪 Chat verlassen", callback_data="bridge:leave")])
    return InlineKeyboardMarkup(kbd)

async def leavebridgecb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Safely handles the breakout sequence of forwarding mechanisms."""
    q = u.callback_query
    await q.answer()
    
    c.user_data.pop("active_bridge_taskid", None)
    c.user_data.pop("bridge_role", None)
    
    await q.message.edit_text("🚪 Du hast den Chatroom verlassen. Es werden keine Nachrichten mehr weitergeleitet.")
    from handlers.common import cmdstart
    await cmdstart(u, c)

async def proxymessage(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Intercepts and forwards assets across the structural anonymous layer tunnel."""
    taskid = c.user_data.get("active_bridge_taskid")
    role = c.user_data.get("bridge_role")
    
    if not taskid or not role:
        return # User is inside the workflow ecosystem but outside an explicit context state

    session = db.get_session(taskid)
    if not session:
        c.user_data.clear()
        await u.effective_message.reply_text("❌ Chat-Sitzung abgelaufen.")
        return
        
    target_chat_id = session["exp_id"] if role == "AG" else session["ag_id"]
    msg = u.effective_message
    
    # Fix: Swapped the system-breaking keyword property layout `.class.name` for standard native inspection.
    attachment = msg.effective_attachment
    prefix = f"💬 **[{'Auftraggeber' if role == 'AG' else 'Experte'}]:** "
    
    try:
        if msg.text:
            await c.bot.send_message(chat_id=target_chat_id, text=prefix + msg.text, parse_mode="Markdown")
        elif attachment:
            caption = (prefix + msg.caption) if msg.caption else prefix
            # Dynamic type identification strategy block implementation
            att_type = type(attachment).__name__.lower() if not isinstance(attachment, list) else "photo"
            
            if att_type == "photo":
                await c.bot.send_photo(chat_id=target_chat_id, photo=msg.photo[-1].file_id, caption=caption, parse_mode="Markdown")
            elif "document" in att_type or msg.document:
                await c.bot.send_document(chat_id=target_chat_id, document=msg.document.file_id, caption=caption, parse_mode="Markdown")
            elif "video" in att_type or msg.video:
                await c.bot.send_video(chat_id=target_chat_id, video=msg.video.file_id, caption=caption, parse_mode="Markdown")
            elif "audio" in att_type or msg.audio:
                await c.bot.send_audio(chat_id=target_chat_id, audio=msg.audio.file_id, caption=caption, parse_mode="Markdown")
            elif "voice" in att_type or msg.voice:
                await c.bot.send_voice(chat_id=target_chat_id, voice=msg.voice.file_id, caption=caption, parse_mode="Markdown")
            else:
                await msg.reply_text("⚠️ Dieser Dateityp kann nicht weitergeleitet werden.")
                return
        
        await msg.react("🕊️") # Give immediate structural visual feedback
    except Exception as e:
        log.error(f"Error handling proxy bridge dispatch routing execution link: {e}")
        await msg.reply_text("❌ Nachricht konnte nicht zugestellt werden. Ist dein Gegenüber blockiert?")

async def dealdelivercb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Marks task work status ready for programmatic clearance approval verification checks."""
    q = u.callback_query
    await q.answer()
    
    # Fix: Index split boundaries confirmed
    taskid = int(q.data.split(":")[2])
    
    # Verification processing step logic execution
    task = db.get_task(taskid)
    if task["status"] != "claimed":
        await q.answer("❌ Statusänderung nicht zulässig.", show_alert=True)
        return

    db.update_task_status(taskid, "delivered")
    session = db.get_session(taskid)
    
    await q.message.edit_text("🎁 Abgabe registriert! Der Auftraggeber wurde benachrichtigt.", reply_markup=getbridgekbd("EXP", taskid, "delivered"))
    
    try:
        await c.bot.send_message(
            chat_id=session["ag_id"],
            text=f"🎁 **Der Experte hat seine Arbeit für Auftrag `#{taskid}` abgegeben!**\n\nBitte prüfe das Ergebnis und gib das Budget frei, wenn alles passt.",
            reply_markup=getbridgekbd("AG", taskid, "delivered")
        )
    except Exception as e:
        log.error(f"Delivery notify fault: {e}")

async def dealreleasecb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Triggers ultimate settlement framework processing state closures."""
    q = u.callback_query
    await q.answer()
    
    taskid = int(q.data.split(":")[2])
    task = db.get_task(taskid)
    
    if task["status"] != "delivered":
        await q.answer("❌ Auszahlung nicht möglich. Keine Abgabe vorhanden.", show_alert=True)
        return
        
    session = db.get_session(taskid)
    
    # Final transactional clearance integration sequence operations execution
    success = db.payout_task(taskid)
    if not success:
        await q.message.edit_text("❌ Ein Fehler bei der Transaktionsabwicklung ist aufgetreten.")
        return
        
    await q.message.edit_text("🌟 Auftrag erfolgreich abgeschlossen und Guthaben freigegeben! Vielen Dank.")
    
    try:
        await c.bot.send_message(
            chat_id=session["exp_id"],
            text=f"💰 **Gute Arbeit! Der Auftraggeber hat das Budget für `#{taskid}` freigegeben.**\n\nDer Betrag wurde deiner Wallet gutgeschrieben."
        )
    except Exception as e:
        log.error(f"Payout notify execution crash: {e}")
        
    c.user_data.clear()
