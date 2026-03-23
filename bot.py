import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text("marhaba! bot VIP aqoud al-options. lil-ishtrak tawassal
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not context.args:
await update.message.reply_text("istad5dm: /add USER_ID")
return
try:
link = await context.bot.create_chat_invite_link(chat_id=int(CHANNEL_ID), member_limi
await update.message.reply_text("rabat al-du5ul: " + link.invite_link)
except Exception as e:
await update.message.reply_text("5ata: " + str(e))
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not context.args:
await update.message.reply_text("istad5dm: /remove USER_ID")
return
try:
user_id = int(context.args[0])
await context.bot.ban_chat_member(chat_id=int(CHANNEL_ID), user_id=user_id)
await context.bot.unban_chat_member(chat_id=int(CHANNEL_ID), user_id=user_id)
await update.message.reply_text("tam izalat al-udw " + str(user_id))
except Exception as e:
await update.message.reply_text("5ata: " + str(e))
def main():
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add_user))
app.add_handler(CommandHandler("remove", remove_user))
app.run_polling()
if __name__ == "__main__":
main()
