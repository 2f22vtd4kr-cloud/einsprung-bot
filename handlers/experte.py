edit_text("❌ Fehler beim Annehmen.")
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
    app.add_handler(CallbackQueryHandler(viewtaskexp, pattern=r"^exp:view:"))
    app.add_handler(CallbackQueryHandler(claimcallback, pattern=r"^exp:claim:"))
    app.add_handler(CallbackQueryHandler(menumychats, pattern=r"^exp:chats$"))
