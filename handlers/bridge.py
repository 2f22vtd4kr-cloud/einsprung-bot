import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler
from telegram.ext import filters  # Explicitly import the filters module
import database as db

log = logging.getLogger("einsprung.handlers.bridge")

async def enterbridge(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    _, _, taskid = q.data.split(":", 2)
    taskid = int(taskid)
    uid = u.effective_user.id
    
    task = await db.gettask(taskid)
    if not task or task["status"] != "inprogress":
        await q.message.edit_text("❌ Session wurde nicht gefunden oder ist nicht aktiv.")
        return
        
    c.user_data["active_bridge_taskid"] = taskid
    role = "AG" if task["clientid"] == uid else "EXP"
    c.user_data["bridge_role"] = role
    
    txt = (
        f"🚪 Du hast den Workspace zu Auftrag `#{taskid}` betreten ({task['title']}).\n\n"
        f"⚠️ Jede Nachricht, die du ab jetzt absendest, wird anonymisiert an die Gegenseite weitergeleitet."
    )
    
    kbd = []
    if role == "AG":
        kbd.append([InlineKeyboardButton("🌟 Freigeben & Auszahlen", callback_data=f"deal:release:{taskid}")])
    kbd.append([InlineKeyboardButton("🚪 Chat verlassen", callback_data="bridge:leave")])
    
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def leavebridgecb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    c.user_data.pop("active_bridge_taskid", None)
    c.user_data.pop("bridge_role", None)
    
    await q.message.edit_text("🚪 Du hast den Chatroom verlassen.")

async def proxymessage(u: Update, c: ContextTypes.DEFAULT_TYPE):
    taskid = c.user_data.get("active_bridge_taskid")
    role = c.user_data.get("bridge_role")
    
    if not taskid or not role:
        return 

    task = await db.gettask(taskid)
    if not task or task["status"] != "inprogress":
        return
        
    target_chat_id = task["executorid"] if role == "AG" else task["clientid"]
    msg = u.effective_message
    prefix = f"💬 [{'Auftraggeber' if role == 'AG' else 'Experte'}]: "
    
    try:
        if msg.text:
            await c.bot.send_message(chat_id=target_chat_id, text=prefix + msg.text, parse_mode="Markdown")
            pass
    except Exception as e:
        log.error(f"Error handling proxy bridge dispatch routing execution link: {e}")

async def dealreleasecb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    taskid = int(q.data.split(":")[2])
    task = await db.gettask(taskid)
    
    if not task or task["status"] != "inprogress":
        await q.answer("❌ Aktion nicht möglich.", show_alert=True)
        return
        
    try:
        # 1. Execute the real atomic database ledger transfer to credit the executor
        await db.releasefundstoexecutor(
            clientid=task["clientid"],
            executorid=task["executorid"],
            gross=task["rewardgross"],
            net=task["rewardnet"]
        )
        
        # 2. Update the task status explicitly so it leaves the active queue
        await db.settaskstatus(taskid, "completed")
        await db.setsessionstatus(taskid, "closed")
        
    except Exception as e:
        log.error(f"Financial ledger execution crash on task #{taskid}: {e}")
        await q.message.edit_text("❌ Interner Fehler bei der Transaktionsabwicklung.")
        return
        
    await q.message.edit_text("🌟 Auftrag erfolgreich abgeschlossen und Guthaben freigegeben!")
    # ... (rest of notification logic stays the same)
    
    try:
        await c.bot.send_message(
            chat_id=task["executorid"],
            text=f"💰 **Gute Arbeit! Der Auftraggeber hat das Budget für #{taskid} freigegeben.**"
        )
    except Exception as e:
        log.error(f"Payout notify fault: {e}")
        
    c.user_data.clear()

def register(app):
    app.add_handler(CallbackQueryHandler(enterbridge, pattern=r"^bridge:go:"))
    app.add_handler(CallbackQueryHandler(leavebridgecb, pattern=r"^bridge:leave$"))
    app.add_handler(CallbackQueryHandler(dealreleasecb, pattern=r"^deal:release:"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, proxymessage), group=1)
