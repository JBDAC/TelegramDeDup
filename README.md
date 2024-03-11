# Telegram Duplicate Message Detection Bot

This Python script introduces a Telegram bot designed to identify and notify about duplicate messages within a specific channel or chat. Utilizing the Telegram Bot API and asynchronous programming (aiohttp and asyncio), the bot offers real-time monitoring to enhance content uniqueness in Telegram communities.

## Features

- **Real-Time Duplicate Detection**: Monitors messages for duplicates post-bot activation, ignoring historical data.
- **Support for Various Content Types**: Handles text, photos, videos, and documents, using unique identifiers for duplication checking.
- **Customizable Message Thresholds**: Includes an adjustable text length threshold to ignore brief messages likely to be coincidental duplicates.
- **Resource Management**: Employs an `OrderedDict` for memory-efficient tracking, with a customizable maximum entry limit.
- **Asynchronous Operation**: Designed for concurrency, handling multiple messages simultaneously without blocking.
- **Security Conscious**: Utilizes hashing to generate unique identifiers for content, ensuring privacy and reducing storage requirements.

## Dependencies

- `aiohttp`: Asynchronous HTTP client/server framework.
- `asyncio`: For writing single-threaded concurrent code using coroutines.
- `re`: Module provides regular expression matching operations.
- `logging`: Standard Python library for logging.
- `requests`: Simple HTTP library for Python.
- `hashlib`: Module providing a common interface to many secure hash and message digest algorithms.
- `datetime`: Module for manipulating dates and times.
- `telegram.ext`: Extension module to help make it easier to use the API.
- `collections.OrderedDict`: Dictionary subclass that remembers the order entries were added.
- `unidecode`: Module to decode unicode characters to their closest ASCII representation.

## Setup Instructions

1. **Install Dependencies**: Ensure all required libraries are installed using pip:

    ```sh
    pip install python-telegram-bot aiohttp requests unidecode
    ```

2. **Telegram Bot Token and Usernames**: You will need to have the following details ready:
   - A Telegram Bot Token: Create a bot by talking to BotFather (@BotFather) on Telegram and following the instructions to get a bot token.
   - Your channel's username: This is the username of the channel where the bot will monitor for duplicate messages.
   - Your chat's username: This is the username of the chat where the bot will also monitor for duplicates.

3. **Set Privacy Settings**: Use the `/setprivacy` command with BotFather to disable privacy mode, allowing the bot to access all messages.

4. **Bot Permissions**: Make sure your bot has the necessary permissions in your channel and chat for managing messages.

5. **Configuration**: The bot's behavior can be adjusted by setting environment variables or passing arguments directly. Relevant parameters include `MIN_TEXT_LENGTH` and `MAX_LIST_ENTRIES` for tuning the bot's sensitivity and memory usage.

7. **Run the Bot**: Execute the script. The bot will start listening for messages, identifying duplicates based on configured thresholds. It uses https, so it does not require any special port to be opened.

## How It Works

- The bot distinguishes between channel and chat messages, applying separate duplicate checks for each context.
- For media messages (photos, videos, documents), metadata is used to generate a unique identifier. If potential duplication is detected, the bot may download the file to confirm.
- For text messages, the bot simplifies the content by removing non-alphanumeric characters and converts to lowercase for case-insensitive comparison. A hash of this simplified text is then used for duplication checking.
- When a duplicate is identified, the bot sends a warning message to the relevant chat or channel, advising against reposting similar content.

## Security and Privacy

- The bot does not store personal information or content beyond what is necessary for duplicate detection. 
- Unique identifiers for content are generated using hashing, ensuring content privacy is maintained.

## Limitations

- The bot does not retrospectively analyze past messages; it only starts monitoring from the point of activation.
- Large files are not supported due to Telegram Bot API limitations on downloading size.

For more information on the Telegram Bot API and the python-telegram-bot library, consult the [official documentation](https://docs.python-telegram-bot.org/).

## Running the Bot

Execute the script with the necessary command-line arguments for your bot token, channel username, and chat username. Use the following format:

```sh
python chk4dups.py --token YOUR_BOT_TOKEN_HERE --channel YOUR_CHANNEL_USERNAME --chat YOUR_CHAT_USERNAME
```

Replace `YOUR_BOT_TOKEN_HERE`, `YOUR_CHANNEL_USERNAME`, and `YOUR_CHAT_USERNAME` with the actual bot token, channel username, and chat username respectively.


## License

This project is licensed under the MIT No Attribution license, a 'do anything' license.
