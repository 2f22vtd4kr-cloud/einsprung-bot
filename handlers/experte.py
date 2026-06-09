import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import CATEGORIES
import database as db

# Fix: Log identifier fixed
log = logging.getLogger(__name__)

async def menuexp(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Main dashboard entry point for service providers/Freelancers."""
    q = u.callback_query
    await q.answer()
    
    txt = (
        "🎓 **Experten-Menü**\n\n"
        "Suche nach offenen Aufträgen oder verwalte deine laufenden Workspaces."
    )
    kbd = [
        [InlineKeyboardButton("🔍 Offene Aufträge durchsuchen", callback_data="exp:browse")],
        [InlineKeyboardButton("💬 Meine aktiven Chats / Workspaces", callback_data="exp:chats")],
        [InlineKeyboardButton("⬅️ Hauptmenü", callback_data="menu:start")]
    ]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def browseccategories(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Lists operational target areas for workers to explore."""
    q = u.callback_query
    await q.answer()
    
    txt = "🗂 **Wähle eine Kategorie, um offene Aufträge zu sehen:**"
    kbd = [[InlineKeyboardButton(cat, callback_data=f"exp:cat:{cat}")] for cat in CATEGORIES]
    kbd.append([InlineKeyboardButton("⬅️ Zurück", callback_data="menu:exp")])
    
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def browsetasks(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Lists unassigned jobs waiting for a match within a chosen category."""
    q = u.callback_query
    await q.answer()
    
    _, _, cat = q.data.split(":", 2)
    tasks = db.get_open_tasks_by_category(cat)
    
    if not tasks:
        await q.message.edit_text(
            f"📭 Keine offenen Aufträge in der Kategorie **{cat}** gefunden.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Zurück", callback_data="exp:browse")]]),
            parse_mode="Markdown"
        )
        return
        
    txt = f"🔍 **Offene Aufträge in {cat}:**\n\n"
    kbd = []
    for t in tasks:
        txt += f"• `#{t['taskid']}` - **{t['title']}** | 💰 {t['reward']} EUR\n"
        kbd.append([InlineKeyboardButton(f"👁️ #{t['taskid']} ansehen", callback_data=f"exp:view:{t['taskid']}")])
        
    kbd.append([InlineKeyboardButton("⬅️ Zurück", callback_data="exp:browse")])
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def viewtaskexp(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Displays detailed preview to a prospective claims provider before signing up."""
    q = u.callback_query
    await q.answer()
    
    _, _, taskid = q.data.split(":", 2)
    taskid = int(taskid)
    
    t = db.get_task(taskid)
    if not t or t["status"] != "open":
        await q.message.edit_text("❌ Dieser Auftrag ist nicht mehr verfügbar.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Zurück", callback_data="exp:browse")]]))
        return
        
    txt = (
        f"📋 **Auftrag `#{t['taskid']}`**\n\n"
        f"**Titel:** {t['title']}\n"
        f"**Kategorie:** {t['category']}\n"
        f"**Vergütung:** {t['reward']} EUR\n\n"
        f"📝 **Beschreibung:**\n{t['description']}\n\n"
        f"⚠️ *Hinweis: Mit Annahme des Auftrags wird ein anonymer 1:1 Chat mit dem Auftraggeber eröffnet.*"
    )
    
    kbd = [
        [InlineKeyboardButton("✅ Auftrag verbindlich annehmen", callback_data=f"exp:claim:{t['taskid']}")],
        [InlineKeyboardButton("⬅️ Zurück", callback_data=f"exp:cat:{t['category']}")]
    ]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def claimcallback(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Claims the job and initializes the shared workplace session."""
    q = u.callback_query
    await q.answer()
    
    # Fix: Secure explicit target variable unpacking
    _, _, taskid_str = q.data.split(":", 2)
    taskid = int(taskid_str)
    exp_id = u.effective_user.id
    
    t = db.get_task(taskid)
    if t["ag_id"] == exp_id:
        await q.answer("❌ Du kannst deinen eigenen Auftrag nicht annehmen!", show_alert=True)
        return

    success = db.claim_task(taskid, exp_id)
    if not success:
        await q.message.edit_text("❌ Fehler: Der Auftrag wurde bereits anderweitig vergeben oder storniert.")
        return
        
    # Send configuration alerts to the client side asynchronously
    try:
        await c.bot.send_message(
            chat_id=t["ag_id"],
            text=f"🚀 **Dein Auftrag `#{taskid}` wurde angenommen!**\n\nEin Experte arbeitet nun daran. Ihr könnt ab jetzt anonym kommunizieren, indem ihr den Chatroom betretet.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Workspace betreten", callback_data=f"bridge:go:{taskid}")]])
        )
    except Exception as e:
        log.error(f"Failed notification push to client {t['ag_id']}: {e}")
        
    kbd = [[InlineKeyboardButton("💬 Chatroom direkt öffnen", callback_data=f"bridge:go:{taskid}")]]
    await q.message.edit_text(
        "🎉 **Auftrag erfolgreich angenommen!**\n\nDer Workspace-Kanal wurde generiert. Du kannst dich nun direkt mit dem Auftraggeber besprechen.",
        reply_markup=InlineKeyboardMarkup(kbd),
        parse_mode="Markdown"
    )

async def menumychats(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Lists current running chats active for the expert."""
    q = u.callback_query
    await q.answer()
    uid = u.effective_user.id
    
    # Fix: SQLite wildcard evaluation fixed (Changed from s., to s.*)
    with db.get_db() as conn:
        res = conn.execute(
            """SELECT s.*, t.title, t.status AS taskstatus FROM dealsessions s
               JOIN tasks t ON t.taskid = s.taskid
               WHERE s.exp_id = ? OR s.ag_id = ?""", (uid, uid)
        ).fetchall()
        
    if not res:
        await q.message.edit_text("💬 Du hast aktuell keine aktiven Chatrooms.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Zurück", callback_data="menu:start")]]))
        return
        
    txt = "💬 **Deine aktiven Workspaces:**\n\n"
    kbd = []
    for r in res:
        role = "Auftraggeber" if r["ag_id"] == uid else "Experte"
        txt += f"• `#{r['taskid']}` - **{r['title']}** (Rolle: {role})\n"
        kbd.append([InlineKeyboardButton(f"🚪 Workspace #{r['taskid']}", callback_data=f"bridge:go:{r['taskid']}")])
        
    kbd.append([InlineKeyboardButton("⬅️ Zurück", callback_data="menu:start")])
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
