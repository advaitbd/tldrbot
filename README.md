# TLDRBot

A witty, slightly sarcastic Telegram bot for group chat summarization. Built with Python and OpenAI, TLDRBot helps teams catch up on conversations with personality.

## Features

### Conversation Summarization (`/tldr`)
Summarize the last N messages in a group chat with a snarky commentary.

```
/tldr      → Summarize last 50 messages
/tldr 100  → Summarize last 100 messages
```

### @Mention Replies
Tag the bot and it'll respond with its signature sarcasm.

```
@TLDRBot what's everyone talking about?
```

### Auto Video Downloads
Drop a TikTok, Instagram Reel, or YouTube Shorts link and the bot automatically downloads and shares the video.

### Rate Limiting
Each user gets 10 AI requests per day. The bot will let you know when you're running low (with attitude, of course).

## Personality Examples

**On /tldr:**
> "Summary complete. I'm basically your group's unpaid intern at this point."

**On @mention:**
> "You rang? I was busy judging other chats."

**On rate limit:**
> "Whoa there, chatty! You've used me 10 times today. I need a break."

## Getting Started

### Prerequisites
- Python 3.10+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- OpenAI API Key

### Installation

1. Clone the repository:
```bash
git clone https://github.com/advaitbd/tldrbot.git
cd tldrbot
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set environment variables:
```bash
# Required
export BOT_TOKEN="your_telegram_bot_token"
export OPENAI_API_KEY="your_openai_api_key"

# Optional
export AI_MODEL="gpt-4o-mini"      # Default: gpt-4o-mini
export DAILY_LIMIT="10"            # AI uses per user per day
export MAX_MESSAGES="400"          # Max messages to store per chat
export DATABASE_URL="postgresql://..."  # For analytics (optional)
```

5. Run the bot:
```bash
python -m bot.main
```

## Project Structure

```
bot/
├── main.py              # Entry point
├── config.py            # Configuration
├── core/
│   ├── bot.py           # Bot orchestration
│   ├── ai.py            # AI service with personality
│   └── rate_limiter.py  # Per-user rate limiting
├── plugins/
│   ├── help.py          # /help command
│   ├── summarize.py     # /tldr command
│   ├── mention_reply.py # @mention handler
│   └── auto_download.py # Video URL detection
└── storage/
    ├── memory.py        # In-memory message storage
    └── analytics.py     # Optional event logging
```

## Commands

| Command | Description | Rate Limited |
|---------|-------------|--------------|
| `/help` | Show help | No |
| `/tldr [n]` | Summarize last n messages | Yes |
| `@bot` mention | Reply with personality | Yes |
| Auto-download | Detect & download videos | No |

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | Yes | - | Telegram bot token |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `AI_MODEL` | No | gpt-4o-mini | OpenAI model to use |
| `DAILY_LIMIT` | No | 10 | AI uses per user per day |
| `MAX_MESSAGES` | No | 400 | Messages to store per chat |
| `DATABASE_URL` | No | - | PostgreSQL URL for analytics |

## Contributing

Contributions welcome! Feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.
