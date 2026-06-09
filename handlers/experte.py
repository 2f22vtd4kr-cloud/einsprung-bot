import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import database as db

log = logging.getLogger("einsprung.handlers.experte")

CATEGORIES = ["Hausarbeit", "Abschlussarbeit", "Programmierung", "Lektorat", "Allgemein"]

async def menuexp(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    txt = (
        "🎓 **Experten-Menü**\n\n"
        "Hier kannst du nach verfügbaren Aufträgen suchen oder deine aktiven Chats einsehen."
    )
    kbd = [
        [InlineKeyboardButton("🔍 Aufträge durchsuchen", callback_data="exp:browse")],
        [InlineKeyboardButton("💬 Meine aktiven Workspaces", callback_data="exp:mychats")],
        [InlineKeyboardButton("⬅️ Hauptmenü", callback_data="menu:start")]
    ]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def browseccategories(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    txt = "🗂 **Wähle eine Kategorie aus, um Aufträge anzuzeigen:**"
    kbd = [[InlineKeyboardButton(cat, callback_data=f"exp:cat:{cat}")] for cat in CATEGORIES]
    kbd.append([InlineKeyboardButton("⬅️ Zurück", callback_data="menu:exp")])
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd))

async def browsetasks(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    _, _, cat = q.data.split(":", 2)
    
    async with db.conn() as database_conn:
        cur = await database_conn.execute(
            "SELECT * FROM tasks WHERE category = ? AND status = 'open' ORDER BY taskid DESC", (cat,)
        )
        tasks = await cur.fetchall()
        
    if not tasks:
        await q.message.edit_text(
            f"📭 Keine offenen Aufträge in der Kategorie **{cat}** gefunden.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Zurück", callback_data="exp:browse")]]),
            parse_mode="Markdown"
        )
        return
        
    txt = f"🔍 **Offene Aufträge in '{cat}':**\n\n"
    kbd = []
    for t in tasks:
        txt += f"• `#{t['taskid']}` - **{t['title']}** - {t['rewardnet']} USDT\n"
        kbd.append([InlineKeyboardButton(f"👁️ #{t['taskid']} ansehen", callback_data=f"exp:view:{t['taskid']}")])
        
    kbd.append([InlineKeyboardButton("⬅️ Zurück", callback_data="exp:browse")])
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def viewtaskexpcb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    _, _, taskid = q.data.split(":", 2)
    taskid = int(taskid)
    
    t = await db.gettask(taskid)
    if not t or t["status"] != "open":
        await q.message.edit_text("❌ Dieser Auftrag steht nicht mehr zur Verfügung.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Zurück", callback_data="exp:browse")]]))
        return
        
    txt = (
        f"📋 **Auftrag `#{t['taskid']}`**\n\n"
        f"**Kategorie:** {t['category']}\n"
        f"**Deine Auszahlung (Netto):** {t['rewardnet']} USDT\n\n"
        f"📝 **Beschreibung:**\n{t['description']}"
    )
    
    kbd = [
        [InlineKeyboardButton("✅ Auftrag annehmen & Chat starten", callback_data=f"exp:accept:{t['taskid'] concrete}") if False else InlineKeyboardButton("✅ Auftrag annehmen & Chat starten", callback_data=f"exp:accept:{t['taskid']}")],
        [InlineKeyboardButton("⬅️ Zurück", callback_data="exp:browse")]
    ]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def accepttaskcb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    taskid = int(q.data.split(":")[2])
    uid = u.effective_user.id
    
    t = await db.gettask(taskid)
    if not t or t["status"] != "open":
        await q.answer("❌ Aktion nicht möglich. Auftrag bereits vergeben.", show_alert=True)
        return
        
    if t["clientid"] == uid:
        await q.answer("❌ Du kannst deinen eigenen Auftrag nicht annehmen!", show_alert=True)
        return
        
    success = await db.accepttask(taskid, uid)
    if not success:
        await q.message.edit_text("❌ Fehler beim Annehmen.")
        return
        
    try:
        await c.bot.send_message(
            chat_id=t["clientid"],
            text=f"🚀 **Dein Auftrag #{taskid} wurde angenommen!**\n\nEin Experte arbeitet nun daran. Ihr könnt ab jetzt kommunizieren.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Workspace betreten", callback_data=f"bridge:go:{taskid}")]])
        )
    except Exception as e:
        log.error(f"Failed notice: {e}")
        
    kbd = [[InlineKeyboardButton("💬 Chatroom direkt öffnen", callback_data=f"bridge:go:{taskid}")]]
    await q.message.edit_text(
        "🎉 **Auftrag erfolgreich angenommen!**\n\nDu kannst dich nun direkt abstimmen.",
        reply_markup=InlineKeyboardMarkup(kbd),
        parse_mode="Markdown"
    )

async def menumychats(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    uid = u.effective_user.id
    
    async with db.conn() as database_conn:
        cur = await database_conn.execute(
            "SELECT * FROM tasks WHERE (clientid = ? OR executorid = ?) AND status = 'inprogress'", (uid, uid)
        )
        res = await cur.fetchall()
        
    if not res:
        await q.message.edit_text("💬 Du hast aktuell keine aktiven Workspaces.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Zurück", callback_data="menu:start")]]))
        return
        
    txt = "💬 **Deine aktiven Workspaces:**\n\n"
    kbd = []
    for r in res:
        txt += f"• #{r['taskid']} - **{r['title']}**\n"
        kbd.append([InlineKeyboardButton(f"🚪 Workspace #{r['taskid']}", callback_data=f"bridge:go:{r['taskid']}")])
        
    kbd.append([InlineKeyboardButton("⬅️ Zurück", callback_data="menu:start")])
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

def register(app):
    app.add_handler(CallbackQueryHandler(menuexp, pattern=r"^menu:exp$"))
    app.add_handler(CallbackQueryHandler(browseccategories, pattern=r"^exp:browse$"))
    app.add_handler(CallbackQueryHandler(browsetasks, pattern=r"^exp:cat:"))
    app.add_handler(CallbackQueryHandler(viewtaskexpcb, pattern=r"^exp:view:"))
    app.add_handler(CallbackQueryHandler(accepttaskcb, pattern=r"^exp:accept:"))
    app.add_handler(CallbackQueryHandler(menumychats, pattern=r"^exp:mychats$"))
