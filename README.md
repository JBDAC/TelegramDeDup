# TelegramDeDup

Telegram Duplicate Message Detector Bot

This Python-based Telegram bot is designed to identify and alert users about duplicate messages within a chat, aiming to reduce redundancy and maintain the quality of conversation. It handles text, images, videos, documents, and URLs, leveraging checksums to detect duplicates. Note that it will only recognize duplicates of messages sent after it starts and cannot process large files due to Telegram API limitations.

## Features

- **Duplicate Detection**: Utilizes checksums to identify duplicate text, media files, and URLs.
- **Configurable Text Length Threshold**: Ignores very short messages (less than 30 characters by default) to avoid false positives.
- **Efficient Memory Management**: Maintains a maximum of 1000 entries in its checksum database, removing the oldest entries to make room for new ones.
- **User Notifications**: Alerts users with a friendly wink emoji when a duplicate is posted.

## Setup and Operation

1. **Create a Bot**: Use [BotFather](https://t.me/botfather) to create a new bot. Note down the access token provided upon creation.
2. **Disable Privacy**: With BotFather, set the bot's privacy settings to 'disable' to allow it to receive all messages.
3. **Dependencies**: Ensure you have `python-telegram-bot` and `requests` libraries installed. Use pip commands like `pip install python-telegram-bot requests` to install them.
4. **Running the Bot**: Insert your bot's access token in the provided placeholder within the code. Run the script in a Python 3.6+ environment.
5. **Operation**: The bot starts listening for messages across all types (text, photo, video, document, and URLs). It will notify users if a duplicate content is detected.

## Limitations

- The bot does not retrospectively check past messages. It only starts detecting duplicates from the point it is activated.
- Large files that cannot be downloaded via the Telegram bot API will not be checked for duplication.

## Getting Started

Replace `"YOUR_BOT_TOKEN_HERE"` with your actual bot token in the script and execute it in a suitable Python environment. The bot will begin monitoring the chat for duplicate messages and alert as configured.

You need a machine that's connected to the net all the time. Copy the code to a directory such as /scanner/. 

Then run: python TelegramDeDup.py

It will poll the channel over HTTPS for messages and manage duplicaes whilst it's running.
