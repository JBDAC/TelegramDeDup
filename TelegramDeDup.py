import logging
import requests
import hashlib
from datetime import datetime
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram import Update
from collections import OrderedDict

#https://docs.python-telegram-bot.org/en/stable/telegram.ext.filters.html
#https://github.com/python-telegram-bot
#Create a new bot. Use the access token given at creation here, when creating use /setprivacy and 'disable' so as to receive all msgs
#This code will not look back at prior messages, therefore will only identify duplicates that are posted after it starts.
#It will not work on large files as the Telegram bot API doesn't allow downloading them.

MIN_TEXT_LENGTH = 30  # Example threshold - very short messages, which are more likely to be coincidentally duplicated and less meaningful to check, are ignored

# Initialize an OrderedDict to store checksums with a max size of 100.  For urls they are the entire url as text
# OrderedDict remembers the order items were inserted, and when it's full (more than MAX_LIST_ENTRIES items), the oldest item is removed to make  space for the new one.
MAX_LIST_ENTRIES = 1000

checksums = OrderedDict()

async def handle_media_message(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    message_date = update.effective_message.date.strftime('%Y-%m-%d %H:%M:%S UTC')
    user = update.effective_message.from_user

    if user:
        print(f"Message from {user.username or 'No username'} (ID: {user.id}) at {message_date}")
    else:
        print(f"User information is not available. Message date: {message_date}")

    #Remove the oldest entry if more than 1000
    while len(checksums) >= MAX_LIST_ENTRIES:
        checksums.popitem(last=False)  # Remove the oldest item

    file_id = (
      message.photo[-1].file_id if message.photo else
      message.video.file_id if message.video else
      message.document.file_id if message.document else None
      )

    if file_id:
        try:
            new_file = await context.bot.get_file(file_id)
        except Exception as e:  # Consider more specific exceptions based on the library's documentation
            print(f"Error fetching file: {e}")
            return
 
        try:
            file_bytes = requests.get(new_file.file_path).content
        except requests.exceptions.RequestException as e:
            print(f"Failed to download file: {e}")
            return

        item_key = hashlib.sha256(file_bytes).hexdigest()
    else:
        urls = []
        if message.entities:
            for entity in message.entities:
                if entity.type in ["url", "text_link"]:
                    if entity.url:
                        urls.append(entity.url)  # Direct URL from the entity - but it often doesn't work
                    else:
                        # Extract URL from message text using offset and length
                        start = entity.offset
                        end = entity.offset + entity.length
                        urls.append(message.text[start:end])

        if urls:
            # Process the first URL
            item_key = urls[0]
            print("URL:", item_key)

    # Handling text content for duplication detection
    if not file_id and not urls:  # Check if no file or URL is being processed
        text_content = message.text or message.caption
        if text_content and len(text_content) >= MIN_TEXT_LENGTH:
            # Calculate hash of the text content
            item_key = hashlib.sha256(text_content.encode('utf-8')).hexdigest()
        else:
            print("No text content found or too short.")
            return

    if item_key in checksums:
        # Duplicate found
        await message.reply_text('⚠️ This appears to be a duplicate. Please avoid reposting the same content. 😉')
        print("DUPLICATE! User notified.")
    else:
        # Store the checksum or URL for future reference
        checksums[item_key] = True
        print(f"Processed and stored item with key: {item_key}")

def main():
    """Start the bot."""
    application = Application.builder().token("YOUR_BOT_TOKEN_HERE").build()
    print("Listening.. (Ctrl+C to end)")
    # Handle messages with media files
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.Entity("url") | filters.Entity("text_link") | filters.TEXT, handle_media_message))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
