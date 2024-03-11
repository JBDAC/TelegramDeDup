import aiohttp
import asyncio
import re
import logging
import requests
import hashlib
import argparse
from datetime import datetime
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram import Update
from collections import OrderedDict
from unidecode import unidecode

#https://docs.python-telegram-bot.org/en/stable/telegram.ext.filters.html
#https://github.com/python-telegram-bot
#https://docs.python-telegram-bot.org/en/stable/telegram.messageorigin.html
#Create a new bot. Use the access token given at creation here, when creating use /setprivacy and 'disable' so as to receive all msgs
#This code will not look back at prior messages, therefore will only identify duplicates that are posted after it starts.
#For media files, the metadata is checked & only if there is a match here will the file be downloaded to double check. This check will not work on large files as the Telegram bot API doesn't allow downloading them.
#Ver 2: 11/03/2024

# Set up argument parsing
parser = argparse.ArgumentParser(description='Telegram Bot for duplicate message detection.')
parser.add_argument('--token', type=str, required=True, help='Telegram Bot Token')
parser.add_argument('--channel', type=str, required=True, help='Channel Username')
parser.add_argument('--chat', type=str, required=True, help='Chat Username')
parser.add_argument('--opmode', type=int, required=True, choices=[0, 1, 2], help='Operation Mode (0: watch, 1: warn, 2: delete)')

# Parse arguments
args = parser.parse_args()

# Assign arguments to variables
BotToken = args.token
ChannelUsername = args.channel
ChatUsername = args.chat
OpMode = args.opmode

MIN_TEXT_LENGTH = 30  # Example threshold - very short messages, which are more likely to be coincidentally duplicated and less meaningful to check, are ignored

# Initialize an OrderedDict to store checksums with a max size of 100.  For urls they are the entire url as text
# OrderedDict remembers the order items were inserted, and when it's full (more than MAX_LIST_ENTRIES items), the oldest item is removed to make  space for the new one.
MAX_LIST_ENTRIES = 1000
MSG_IN_UNKNOWN = 0
MSG_IN_CHANNEL = 1
MSG_IN_CHAT = 2

MODE_WATCH = 0
MODE_WARN = 1
MODE_DELETE = 2

DUP_CHANNEL_MSG = '⚠️ This appears to duplicate an existing message in the *channel*. Please avoid reposting the same content. 😉'
DUP_CHAT_MSG = '⚠️ This appears to duplicate an existing message in the *chat*. Please avoid reposting the same content. 😉 (Posts to the channel are copied to the chat, posts to the chat are not necessarily copied to the channel.)'

#global variables, need protecting from async accesses / race conditions:
chat_checksums = OrderedDict()
channel_checksums = OrderedDict()
# Create a lock for each shared resource
chat_checksums_lock = asyncio.Lock()
channel_checksums_lock = asyncio.Lock()

MyUserID = ""

def simplify_text(text):
   # Normalize unicode characters to their closest ASCII representation
#    print(text)
    text = unidecode(text)
    
    text = text.lower()
    
    # Replace common abbreviations and symbols with their "full" words or equivalents
    substitutions = {
        "&": "and",
        "@": "at",
        "w/": "with",
        "w/o": "without",
    }
    for symbol, replacement in substitutions.items():
        text = text.replace(symbol, replacement)
    
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    # Remove all non-alphanumeric characters (keeping spaces), use a space to replace them to preserve word boundaries
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text).strip()

#    print(text)
    return text

async def download_file(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()  # Returns the content of the file
            else:
                raise Exception(f"Failed to download file with status {response.status}")

def generate_unique_file_identifier(message):
    # Initialize a list to hold pieces of metadata
    metadata_parts = []

    if message.photo:
        # Telegram sends photos in different sizes; choose one (e.g., the largest)
        largest_photo = max(message.photo, key=lambda p: p.file_size)
        metadata_parts.append('photo')
        metadata_parts.append(str(largest_photo.file_size))
        metadata_parts.append(largest_photo.file_unique_id)
    elif message.video:
        metadata_parts.append('video')
        metadata_parts.append(str(message.video.file_size))
        metadata_parts.append(message.video.file_unique_id)
        metadata_parts.append(message.video.file_name or '')  # File name might not always be present
    elif message.document:
        metadata_parts.append('document')
        metadata_parts.append(str(message.document.file_size))
        metadata_parts.append(message.document.file_unique_id)
        metadata_parts.append(message.document.file_name or '')

    # Add the media caption if present
    if message.caption:
        metadata_parts.append(message.caption)

    # Combine all parts into a single string
    combined_metadata = '|'.join(metadata_parts)

    # Hash the combined string to generate a unique identifier
    unique_identifier = hashlib.sha256(combined_metadata.encode()).hexdigest()

    return unique_identifier

async def send_temporary_warning(context, chat_id, warning_text, delete_after=60):
    # Send the warning message
    warning_message = await context.bot.send_message(chat_id=chat_id, text=warning_text, parse_mode='Markdown')
    
    # Wait for 'delete_after' seconds (e.g., 60 for 1 minute)
    await asyncio.sleep(delete_after)
    
    # Delete the warning message
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=warning_message.message_id)
    except Exception as e:
        print(f"Failed to delete the warning message: {e}")


async def handle_media_message(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg_type = MSG_IN_UNKNOWN
    channelMsgIsDup = False
    chatMsgIsDup = False
    doubleCheck = False
    file_key = None
    message = update.effective_message
    chat_id = message.chat.id  # Extract the chat ID from the update object

    print("========================")

    task = asyncio.current_task()
    task_id = id(task)  # Using the task's memory id as an identifier
    print(f"Task {task_id}:")

    print(message.chat)

    # Skip duplicate checking for messages forwarded from the linked channel
    if message.chat.username == ChannelUsername: 
        msg_type = MSG_IN_CHANNEL

    if message.chat.username == ChatUsername: 
        msg_type = MSG_IN_CHAT

    if msg_type == MSG_IN_UNKNOWN: #still unknown? 
        print("Skipping unknown message type.")
        return

    message_date = update.effective_message.date.strftime('%Y-%m-%d %H:%M:%S UTC')
    user = update.effective_message.from_user

    if user:
        print(f"Message from {user.username or 'No username'} (ID: {user.id}) at {message_date}")
    else:
        print(f"User information is not available. Message date: {message_date}")

    #Remove the oldest entry if more than 1000
    async with chat_checksums_lock:
        while len(chat_checksums) >= MAX_LIST_ENTRIES:
            chat_checksums.popitem(last=False)

    async with channel_checksums_lock:
        while len(channel_checksums) >= MAX_LIST_ENTRIES:
            channel_checksums.popitem(last=False)

    file_id = (
      message.photo[-1].file_id if message.photo else
      message.video.file_id if message.video else
      message.document.file_id if message.document else None
      )

    #Strangely, the file_id changes for each time a user forwards the same file, so we can't just use that as it's not unique
    #so we will combine the metadata & hash that & only if that matches will we attempt to download the file
    if file_id:     
        item_key = generate_unique_file_identifier(message)
        print(f"Metadata:{item_key}")
        if msg_type == MSG_IN_CHANNEL:
            async with channel_checksums_lock:
                if item_key in channel_checksums:
                    doubleCheck = True
        if msg_type == MSG_IN_CHAT:
            async with chat_checksums_lock:
                if item_key in chat_checksums:
                    doubleCheck = True

#        item_key = file_id
#        item_key = hashlib.sha256(file_id.encode('utf-8')).hexdigest()

        if doubleCheck:
            # Resource / bandwidth intensive as it needs to download the entire file:
            print("Metadata duplicate: downloading file to double check!")
            file_bytes = None
            try:
                new_file = await context.bot.get_file(file_id)	#gets path
                try:
                    #file_bytes = requests.get(new_file.file_path).content
                    file_bytes = await download_file(new_file.file_path)
                except requests.exceptions.RequestException as e:
                    print(f"Failed to download file: {e}")
                    file_bytes = None

            except Exception as e:
                print(f"Error fetching file: {e}")

            if file_bytes:
                file_key = hashlib.sha256(file_bytes).hexdigest()
                print(f"Downloaded ok, file_key is: {file_key}")
            else:
                print("download failed, skipping this check")

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
        text_content = simplify_text(message.text)
        print(f"text_content={text_content}")

        #sometimes it gets triggered when deleting multiple messages
        if text_content == "":
            return

	#avoid detecting own notification messages:
        if text_content == simplify_text(DUP_CHANNEL_MSG):
            print("Skipping own channel dup msg!")
            return
        if text_content == simplify_text(DUP_CHAT_MSG):
            print("Skipping own chat dup msg!")
            return

        if text_content and len(text_content) >= MIN_TEXT_LENGTH:
            # Calculate hash of the text content
            item_key = hashlib.sha256(text_content.encode('utf-8')).hexdigest()
        else:
            print("No text content found or too short.")
            return

    # Now we can finally determine if the message is a duplicate & do something about it:
    if msg_type == MSG_IN_CHANNEL:
        async with channel_checksums_lock:
            if file_key:
                if file_key in channel_checksums:
                    channelMsgIsDup = True 
            if item_key in channel_checksums:
                channelMsgIsDup = True 

        if channelMsgIsDup == True:
            print("DUPLICATE in channel!")
            if OpMode == MODE_WARN:
                asyncio.create_task(send_temporary_warning(context, chat_id, DUP_CHANNEL_MSG))

            if OpMode == MODE_DELETE:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    asyncio.create_task(send_temporary_warning(context, chat_id, DUP_CHANNEL_MSG))
                    print("Duplicate CHANNEL message deleted.")
                except Exception as e:
                    print(f"Failed to delete the CHANNEL message or warn users: {e}")

        else:
            # Store the checksum or URL for future reference
            async with channel_checksums_lock:
                channel_checksums[item_key] = True
            print(f"Processed and stored channel item with key: {item_key}")
            if file_key:
                async with channel_checksums_lock:
                    channel_checksums[file_key] = True
                print(f"Also stored channel item with file_key: {file_key}")

    if msg_type == MSG_IN_CHAT:
        async with chat_checksums_lock:
            if file_key:
                if file_key in chat_checksums:
                    chatMsgIsDup = True 
            if item_key in chat_checksums:
                chatMsgIsDup = True 

        if chatMsgIsDup == True:
            print("DUPLICATE in chat!")
            if OpMode == MODE_WARN:
                asyncio.create_task(send_temporary_warning(context, chat_id, DUP_CHAT_MSG))
    
            if OpMode == MODE_DELETE:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    asyncio.create_task(send_temporary_warning(context, chat_id, DUP_CHAT_MSG))
                    print("Duplicate CHAT message deleted.")
                except Exception as e:
                    print(f"Failed to delete the CHAT message or warn users: {e}")

        else:
            # Store the checksum or URL for future reference
            async with chat_checksums_lock:
                chat_checksums[item_key] = True
            print(f"Processed and stored chat item with key: {item_key}")
            if file_key:
                async with chat_checksums_lock:
                    chat_checksums[file_key] = True
                print(f"Also stored chat item with file_key: {file_key}")

def get_bot_user_id():
    url = f"https://api.telegram.org/bot{BotToken}/getMe"
    response = requests.get(url)
    response_json = response.json()
    if response_json["ok"]:
        return response_json["result"]["id"]
    else:
        return "Error: Couldn't fetch bot information"

def main():
    """Start the bot."""
    application = Application.builder().token(BotToken).build()
    MyUserID = get_bot_user_id()
    print(f"Bot's user ID: {MyUserID}")

    print("Operation mode: ", end="")
    if OpMode == MODE_WATCH:
        print("watch")
    elif OpMode == MODE_WARN:
        print("warn")
    elif OpMode == MODE_DELETE:
        print("delete")
    else:
        print("Unknown mode")
        return

    print("Listening.. (Ctrl+C to end)")

    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.Entity("url") | filters.Entity("text_link") | filters.TEXT, handle_media_message))

    #NB. this is asycnchronous and can create multiple event loops, one per message coming in so we need to ensure locking of global dictionaries when accessing to avoide race conditions or other strange stuff...
    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()


