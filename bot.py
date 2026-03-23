import os
import logging
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x]
SUB_DAYS = int(os.environ.get("SUB_DAYS", "30"))
DB_FILE = "subscribers.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def add_subscriber(user_id, days=30):
    db = load_db()
    expiry = datetime.now() + timedelta(days=days)
    db[str(user_id)] = {"expiry": expiry.isoformat(), "added": datetime.now().isoformat()}
    save_db(db)
    return expiry.strftime("%Y-%m-%d %H:%M")

def remove_subscriber(user_id):
    db = load_db()
    db.pop(str(user_id), None)
    save_db(db)

def get_subscriber(user_id):
    db = load_db()
    return db.get(str(user_id))

def get_all_subscribers():
    return load_db()

def admin_only(func):
    async def wrapper(update, context):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        return await func(update, context)
    return wrapper

async def start(update, context):
    keyboard = [[InlineKeyboardButton("My Status", callback_data="my_status")]]
    await update.message.reply_text("Welcome to VIP Bot!\nPress the button to check your subscription:", reply_markup=InlineKeyboardMarkup(keyboard))

@admin_only
async def add_user(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /add USER_ID [days]")
        return
    try:
        user_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else SUB_DAYS
        link = await context.bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1, name=f"User {user_id}")
        expiry = add_subscriber(user_id, days)
        await update.message.reply_text(f"Added!\nID: {user_id}\nExpiry: {expiry}\nLink: {link.invite_link}")
        try:
            await context.bot.send_message(chat_id=user_id, text=f"Your subscription is active for {days} days!\nExpiry: {expiry}\nJoin: {link.invite_link}")
        except:
            await update.message.reply_text("Could not message user directly.")
    except ValueError:
        await update.message.reply_text("Invalid ID.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

@admin_only
async def remove_user(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /remove USER_ID")
        return
    try:
        user_id = int(context.args[0])
        await context.bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        await context.bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        remove_subscriber(user_id)
        await update.message.reply_text(f"Removed user {user_id}")
        try:
            await context.bot.send_message(chat_id=user_id, text="Your subscription has ended.")
        except:
            pass
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

@admin_only
async def list_subs(update, context):
    db = get_all_subscribers()
    if not db:
        await update.message.reply_text("No subscribers.")
        return
    lines = ["Subscribers:\n"]
    for uid, info in db.items():
        expiry = datetime.fromisoformat(info["expiry"])
        remaining = (expiry - datetime.now()).days
        status = "Active" if remaining > 0 else "EXPIRED"
        lines.append(f"{status} | {uid} | {remaining} days left")
    await update.message.reply_text("\n".join(lines))

@admin_only
async def broadcast(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /broadcast your message")
        return
    text = " ".join(context.args)
    db = get_all_subscribers()
    sent, failed = 0, 0
    for uid in db:
        try:
            await context.bot.send_message(chat_id=int(uid), text=text)
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"Sent: {sent} | Failed: {failed}")

async def my_status_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    sub = get_subscriber(user_id)
    if not sub:
        await query.edit_message_text("No active subscription. Contact admin.")
        return
    expiry = datetime.fromisoformat(sub["expiry"])
    remaining = (expiry - datetime.now()).days
    if remaining > 0:
        await query.edit_message_text(f"Active!\nExpiry: {expiry.strftime('%Y-%m-%d')}\nDays left: {remaining}")
    else:
        await query.edit_message_text("Your subscription has expired. Contact admin to renew.")

async def check_expired(context):
    db = get_all_subscribers()
    expired = []
    for uid, info in db.items():
        if datetime.now() > datetime.fromisoformat(info["expiry"]):
            expired.append(int(uid))
    for user_id in expired:
        try:
            await context.bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            await context.bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            try:
                await context.bot.send_message(chat_id=user_id, text="Your subscription has ended.")
            except:
                pass
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=f"Expired user removed: {user_id}")
                except:
                    pass
            remove_subscriber(user_id)
        except Exception as e:
            logger.error(f"Failed to remove {user_id}: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("subs", list_subs))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(my_status_callback, pattern="^my_status$"))
    app.job_queue.run_repeating(check_expired, interval=3600, first=60)
    logger.info("Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
