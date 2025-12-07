# TLDRBot Architecture

## Overview

TLDRBot is a lightweight, plugin-based Telegram bot focused on group chat summarization with a snarky personality. The architecture emphasizes simplicity, extensibility, and maintainability.

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      Telegram API                         │
└─────────────────────────┬────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────┐
│                     TLDRBot                             │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                    Core Layer                        │ │
│  │  ┌──────────┐  ┌───────────┐  ┌────────────────┐   │ │
│  │  │   Bot    │  │ AIService │  │  RateLimiter   │   │ │
│  │  └──────────┘  └───────────┘  └────────────────┘   │ │
│  └─────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                   Plugin Layer                       │ │
│  │  ┌────────┐ ┌──────────┐ ┌─────────┐ ┌───────────┐ │ │
│  │  │  Help  │ │ Summarize│ │ Mention │ │ AutoDownl │ │ │
│  │  └────────┘ └──────────┘ └─────────┘ └───────────┘ │ │
│  └─────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                  Storage Layer                       │ │
│  │  ┌────────────────┐  ┌────────────────────────────┐ │ │
│  │  │ MemoryStorage  │  │ Analytics (Optional DB)    │ │ │
│  │  └────────────────┘  └────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. Core Layer (`core/`)

#### Bot (`bot.py`)
- Main orchestrator that registers plugins
- Manages application lifecycle
- Sets up Telegram command menu

#### AIService (`ai.py`)
- Single OpenAI integration with personality baked in
- Generates snarky summaries and mention responses
- Includes curated list of witty remarks

#### RateLimiter (`rate_limiter.py`)
- Per-user daily rate limiting (default: 10/day)
- Resets at midnight UTC
- Returns snarky messages when limit exceeded

### 2. Plugin Layer (`plugins/`)

Each plugin is self-contained and implements the `Plugin` interface:

```python
class Plugin(ABC):
    name: str                              # For logging
    commands: List[Tuple[str, str]]        # For bot menu
    def register(self, app: Application)   # Register handlers
```

#### HelpPlugin (`help.py`)
- `/help` and `/start` commands
- Displays bot capabilities with personality

#### SummarizePlugin (`summarize.py`)
- `/tldr [n]` command
- Fetches messages from memory storage
- Generates AI summary with snarky remark
- Shows progress indicator while processing

#### MentionReplyPlugin (`mention_reply.py`)
- Handles @bot mentions
- Handles replies to bot messages
- Uses chat context for relevant responses

#### AutoDownloadPlugin (`auto_download.py`)
- Detects video URLs (TikTok, Reels, Shorts)
- Automatically downloads and shares videos
- Uses yt-dlp for downloads

### 3. Storage Layer (`storage/`)

#### MemoryStorage (`memory.py`)
- In-memory message storage per chat
- Configurable message limit (default: 400)
- Stores summary context for follow-ups

#### Analytics (`analytics.py`)
- Optional PostgreSQL integration
- Logs user events for analytics
- Gracefully degrades if not configured

## Data Flow

### /tldr Command

```
User: /tldr 50
    │
    ▼
┌────────────────┐
│ Rate Limiter   │ ─ Check if user has remaining uses
└───────┬────────┘
        │ (allowed)
        ▼
┌────────────────┐
│ Memory Storage │ ─ Get last 50 messages
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ AI Service     │ ─ Generate summary with personality
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Send Response  │ ─ Summary + snarky remark
└────────────────┘
```

### Auto-Download

```
User sends: "Check this out https://tiktok.com/..."
    │
    ▼
┌────────────────┐
│ URL Detection  │ ─ Match against patterns
└───────┬────────┘
        │ (match)
        ▼
┌────────────────┐
│ React 🎬       │ ─ Show processing
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ yt-dlp         │ ─ Download video
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Send Video     │ ─ With snarky caption
└────────────────┘
```

## Directory Structure

```
bot/
├── main.py              # Entry point (~60 lines)
├── config.py            # Configuration (~30 lines)
├── core/
│   ├── __init__.py
│   ├── bot.py           # Bot orchestration (~60 lines)
│   ├── ai.py            # AI with personality (~100 lines)
│   └── rate_limiter.py  # Rate limiting (~50 lines)
├── plugins/
│   ├── __init__.py      # Plugin base class
│   ├── help.py          # ~40 lines
│   ├── summarize.py     # ~90 lines
│   ├── mention_reply.py # ~100 lines
│   └── auto_download.py # ~90 lines
└── storage/
    ├── __init__.py
    ├── memory.py        # ~50 lines
    └── analytics.py     # ~80 lines
```

**Total: ~750 lines** (down from ~2000+ in previous version)

## Extending the Bot

### Adding a New Plugin

1. Create a new file in `plugins/`:

```python
from plugins import Plugin
from telegram.ext import Application, CommandHandler

class MyPlugin(Plugin):
    @property
    def name(self) -> str:
        return "my_plugin"
    
    @property
    def commands(self):
        return [("mycommand", "Does something cool")]
    
    def register(self, app: Application) -> None:
        app.add_handler(CommandHandler("mycommand", self.handler))
    
    async def handler(self, update, context):
        await update.message.reply_text("Hello!")
```

2. Register in `main.py`:

```python
from plugins import MyPlugin
bot.register_plugin(MyPlugin())
```

### Adding Personality

Edit `core/ai.py` to add:
- New remarks to `SNARKY_SUMMARY_REMARKS`
- New intros to `SNARKY_MENTION_INTROS`
- Modify `SYSTEM_PROMPT` for behavior changes

## Design Decisions

1. **Plugin Architecture**: Each feature is isolated, making it easy to add/remove capabilities.

2. **No Redis**: Removed Redis dependency. Python-telegram-bot handles async well, and rate limiting uses in-memory storage (resets on restart, which is acceptable).

3. **Single AI Provider**: Removed multi-provider support. Simpler to maintain, and OpenAI is reliable enough.

4. **Personality Baked In**: Snarky remarks are part of the AI service, not an afterthought.

5. **Optional Analytics**: Database is optional. Bot works fine without it.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | Yes | - | Telegram bot token |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `AI_MODEL` | No | gpt-4o-mini | Model to use |
| `DAILY_LIMIT` | No | 10 | Uses per user per day |
| `MAX_MESSAGES` | No | 400 | Messages per chat |
| `DATABASE_URL` | No | - | PostgreSQL for analytics |
