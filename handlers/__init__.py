import logging
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ConversationHandler, filters
)

import handlers.common as common
import handlers.auftraggeber as ag
import handlers.experte as exp
import handlers.bridge as bridge
import handlers.payments as pay

log = logging.getLogger(__name__)

# Fix: Helper callback function to prevent infinite inline loading spinners on cancellation
async def cancel_handler_callback(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.callback_query:
        await u.callback_query.answer()
    return await common.cmdcancel(u, c)

def register_handlers(app: Application):
    """Hooks up all routing elements inside the main application engine."""
    
    # 1. Global Command Handlers
    app.add_handler(CommandHandler("start", common.cmdstart))
    app.add_handler(CommandHandler("cancel", common.cmdcancel))
    
    # 2. Main Interface Flow Navigation Options
    app.add_handler(CallbackQueryHandler(common.cmdstart, pattern=r"^menu:start$"))
    app.add_handler(CallbackQueryHandler(ag.menuag, pattern=r"^menu:ag$"))
    app.add_handler(CallbackQueryHandler(exp.menuexp, pattern=r"^menu:exp$"))
    app.add_handler(CallbackQueryHandler(pay.menuwallet, pattern=r"^menu:wallet$"))
    
    # 3. Auftraggeber (Client) Conversation Multi-State Wizard Handler
    ag_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ag.wizardstart, pattern=r"^ag:new$")],
        states={
            ag.WIZ_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ag.steptitle)],
            ag.WIZ_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, ag.stepdesc)],
            ag.WIZ_CAT: [CallbackQueryHandler(ag.stepcategorycb, pattern=r"^wiz:cat:")],
            ag.WIZ_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ag.stepreward)],
            ag.WIZ_ATTACH: [
                CallbackQueryHandler(ag.stepattachdonecb, pattern=r"^wiz:attach:done$"),
                MessageHandler(filters.ALL & ~filters.COMMAND, ag.stepattach)
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel_handler_callback, pattern=r"^wiz:cancel$")],
        per_message=False
    )
    app.add_handler(ag_conv)
    
    # Client Management Bindings
    app.add_handler(CallbackQueryHandler(ag.menuagmanage, pattern=r"^ag:manage$"))
    app.add_handler(CallbackQueryHandler(ag.viewtaskcb, pattern=r"^ag:view:"))
    
    # 4. Experte (Freelancer) Flow System Handlers
    app.add_handler(CallbackQueryHandler(exp.browseccategories, pattern=r"^exp:browse$"))
    app.add_handler(CallbackQueryHandler(exp.browsetasks, pattern=r"^exp:cat:"))
    app.add_handler(CallbackQueryHandler(exp.viewtaskexp, pattern=r"^exp:view:"))
    app.add_handler(CallbackQueryHandler(exp.claimcallback, pattern=r"^exp:claim:"))
    app.add_handler(CallbackQueryHandler(exp.menumychats, pattern=r"^exp:chats$"))
    
    # 5. Native Payments Integration Flow Wizard Handler
    pay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(pay.wallettopupstarscb, pattern=r"^wallet:topup:stars$")],
        states={
            pay.WIZ_TOPUP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay.stepamounttopup)]
        },
        fallbacks=[CallbackQueryHandler(cancel_handler_callback, pattern=r"^wiz:cancel$")],
        per_message=False
    )
    app.add_handler(pay_conv)
    
    # Native Payment Verification Triggers
    app.add_handler(app.pre_checkout_query_handler(pay.precheckoutcallback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, pay.successfulpaymentcallback))
    
    # 6. Bridge Workspace Forwarder Framework Routing Endpoints
    app.add_handler(CallbackQueryHandler(bridge.enterbridge, pattern=r"^bridge:go:"))
    app.add_handler(CallbackQueryHandler(bridge.leavebridgecb, pattern=r"^bridge:leave$"))
    app.add_handler(CallbackQueryHandler(bridge.dealdelivercb, pattern=r"^deal:deliver:"))
    app.add_handler(CallbackQueryHandler(bridge.dealreleasecb, pattern=r"^deal:release:"))
