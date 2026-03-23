import os, logging, json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x]
SUB_DAYS = int(os.environ.get("SUB_DAYS", "30"))
DB_FILE = "subscribers.json"
def load_db():
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except: return {}
def save_db(db):
    with open(DB_FILE, "w") as f: json.dump(db, f, indent=2)
def add_sub(uid, days=30):
    db = load_db()
    exp = datetime.now() + timedelta(days=days)
    db[str(uid)] = {"expiry": exp.isoformat(), "added": datetime.now().isoformat()}
    save_db(db)
    return exp.strftime("%Y-%m-%d %H:%M")
def remove_sub(uid):
    db = load_db()
    db.pop(str(uid), None)
    save_db(db)
def get_sub(uid): return load_db().get(str(uid))
def get_all(): return load_db()
def admin_only(func):
    async def wrapper(update, context):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("Admins only.")
            return
        return await func(update, context)
    return wrapper
async def start(update, context):
    kb = [[InlineKeyboardButton("My Status", callback_data="my_status")]]
    await update.message.reply_text("Welcome to VIP Bot!\nCheck your subscription:", reply_markup=InlineKeyboardMarkup(kb))
@admin_only
async def add_user(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /add USER_ID [days]")
        return
    try:
        uid = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else SUB_DAYS
        link = await context.bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
        exp = add_sub(uid, days)
        await update.message.reply_text(f"Added!\nID: {uid}\nExpiry: {exp}\nLink: {link.invite_link}")
        try: await context.bot.send_message(chat_id=uid, text=f"Subscription active for {days} days!\nExpiry: {exp}\nJoin: {link.invite_link}")
        except: await update.message.reply_text("Could not message user.")
    except Exception as e: await update.message.reply_text(f"Error: {e}")
@admin_only
async def remove_user(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /remove USER_ID")
        return
    try:
        uid = int(context.args[0])
        await context.bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=uid)
        await context.bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=uid)
        remove_sub(uid)
        await update.message.reply_text(f"Removed {uid}")
    except Exception as e: await update.message.reply_text(f"Error: {e}")
@admin_only
async def list_subs(update, context):
    db = get_all()
    if not db:
        await update.message.reply_text("No subscribers.")
        return
    lines = []
    for uid, info in db.items():
        rem = (datetime.fromisoformat(info["expiry"]) - datetime.now()).days
        lines.append(f"{'OK' if rem > 0 else 'EXP'} | {uid} | {rem}d")
    await update.message.reply_text("\n".join(lines))
@admin_only
async def broadcast(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /broadcast msg")
        return
    txt = " ".join(context.args)
    s, f = 0, 0
    for uid in get_all():
        try: await context.bot.send_message(chat_id=int(uid), text=txt); s += 1
        except: f += 1
    await update.message.reply_text(f"Sent: {s} | Failed: {f}")
async def status_cb(update, context):
    q = update.callback_query
    await q.answer()
    sub = get_sub(q.from_user.id)
    if not sub:
        await q.edit_message_text("No subscription. Contact admin.")
        return
    rem = (datetime.fromisoformat(sub["expiry"]) - datetime.now()).days
    if rem > 0: await q.edit_message_text(f"Active!\nExpiry: {sub['expiry'][:10]}\nDays left: {rem}")
    else: await q.edit_message_text("Expired. Contact admin.")
async def check_expired(context):
    for uid, info in list(get_all().items()):
        if datetime.now() > datetime.fromisoformat(info["expiry"]):
            try:
                await context.bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=int(uid))
                await context.bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=int(uid))
                remove_sub(uid)
                for a in ADMIN_IDS:
                    try: await context.bot.send_message(chat_id=a, text=f"Removed expired: {uid}")
                    except: pass
            except Exception as e: logger.error(f"Remove failed {uid}: {e}")
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("subs", list_subs))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(status_cb, pattern="^my_status$"))
    if app.job_queue:
        app.job_queue.run_repeating(check_expired, interval=3600, first=60)
    logger.info("Bot started!")
    app.run_polling()
if __name__ == "__main__":
    main()
