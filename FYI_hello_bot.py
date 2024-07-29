import os
import json
import argparse
from datetime import datetime
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, Filters, CallbackContext, Dispatcher
from telegram import Bot
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, workers=1)

log_data = []
new_users = {}

# Function to manage log data length
def add_log_message(message):
    log_data.append(message)
    if len(log_data) > 200:
        log_data.pop(0)
    logger.info(message)

# /start command handler
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Привет! Я чат-бот, который будет удалять непредставившихся участников")
    log_message = f"{datetime.now()} - Bot started by user {update.message.from_user.full_name}\n"
    add_log_message(log_message)

# Handler for new chat members
def new_member(update: Update, context: CallbackContext) -> None:
    for member in update.message.new_chat_members:
        user_id = member.id
        chat_id = update.message.chat_id
        new_users[user_id] = {
            "chat_id": chat_id,
            "joined": datetime.now(),
            "name": member.full_name,
        }
        context.job_queue.run_once(check_introduction, 86400 * 2, context=(chat_id, user_id))
        log_message = f"{datetime.now()} - New member added: {member.full_name}\n"
        add_log_message(log_message)

# Check if the user has introduced themselves
def check_introduction(context: CallbackContext) -> None:
    chat_id, user_id = context.job.context
    if user_id in new_users:
        context.bot.kick_chat_member(chat_id, user_id)
        context.bot.unban_chat_member(chat_id, user_id)
        del new_users[user_id]
        log_message = f"{datetime.now()} - Member removed due to lack of introduction: {user_id}\n"
        add_log_message(log_message)

# Handler for messages with the #whois tag
def whois_handler(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id in new_users:
        update.message.reply_text(f"Спасибо за представление, {update.message.from_user.full_name}!")
        del new_users[user_id]
        log_message = f"{datetime.now()} - User introduced themselves: {update.message.from_user.full_name}\n"
        add_log_message(log_message)

# Register handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.status_update.new_chat_members, new_member))
dispatcher.add_handler(MessageHandler(Filters.regex(r"#whois"), whois_handler))

def lambda_handler(event, context):
    """Lambda function to handle Telegram webhook calls."""
    if event.get("httpMethod", None) == "POST":
        body = json.loads(event.get("body", "{}"))
        update = Update.de_json(body, bot)
        dispatcher.process_update(update)
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "ok"})
        }
    else:
        return {
            "statusCode": 405,
            "body": json.dumps({"error": "Method not allowed"})
        }
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local Lambda function test")
    parser.add_argument("--event", type=str, help="Path to the event file")
    args = parser.parse_args()

    if args.event:
        with open(args.event, "r") as f:
            event = json.load(f)
            print(lambda_handler(event, None))    