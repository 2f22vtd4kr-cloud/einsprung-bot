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
