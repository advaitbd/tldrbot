# TLDRBot

A powerful Telegram bot that enhances group productivity through AI-powered conversation management, bill splitting, and media handling. Built with Python and modern AI models, TLDRBot helps teams stay organized and efficient in their group chats.

## 🌟 Key Features

### 1. Smart Conversation Management
- **AI-Powered Summaries**: Use `/tldr` to get concise summaries of recent chat messages
  - Extracts key points, sentiment, and events
  - Configurable message range (default: 50, max: 400)
  - Supports multiple AI models for different quality/performance needs

### 2. Context-Aware Q&A
- Reply to any summary with questions
- Bot provides answers based on the conversation context
- Maintains conversation memory for accurate responses

### 3. Intelligent Bill Splitting
- **Receipt Processing**: Upload receipt photos with payment context
- **Smart OCR**: Uses Mistral AI for accurate text extraction
- **Flexible Payment Matching**:\
  Individual items: "Alice: Burger, Bob: Salad"\
  Shared items: "Shared: Drinks"\
  Automatic tax and service charge calculations
- **Interactive Flow**: Confirmation steps to ensure accuracy

### 4. Media Handling
- **Video Downloads**: `/dl` command for short-form videos
  - Supports TikTok, YouTube Shorts, Instagram Reels
  - Direct download in chat
  - Powered by yt-dlp for reliable downloads

### 5. Multi-Model AI Support
- Switch between different AI models:
  - OpenAI (GPT models)
  - Groq (Llama 3)
  - DeepSeek
- Use `/switch_model` to change models based on needs

## 🛠️ Technical Architecture

### Core Components

1. **Command Handlers**
   - Manages all bot commands
   - Implements conversation flows
   - Handles user interactions

2. **Message Handlers**
   - Processes regular messages
   - Manages context-aware responses
   - Handles reply chains

3. **AI Service**
   - Strategy pattern for multiple AI models
   - Handles summarization and Q&A
   - OCR processing for receipts

4. **Memory Storage**
   - In-memory message storage
   - Efficient chat history management
   - No persistent database required

5. **Bill Splitting System**
   - **Receipt Processing Pipeline**:
     - OCR using Mistral AI for text extraction
     - AI-powered receipt data structuring
     - Pydantic models for data validation
   
   - **Context Analysis**:
     - LLM-based payment context parsing
     - Smart item-to-person matching
     - Shared item detection
   
   - **Calculation Engine**:
     - Proportional tax and service charge distribution
     - Individual and shared item cost calculations
     - Validation against receipt totals
   
   - **Conversation Flow**:
     - Multi-step confirmation process
     - Error handling and recovery
     - User-friendly result formatting

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- Telegram Bot Token
- API keys for desired AI services

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/TeleBot.git
   cd TeleBot
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   # Required
   BOT_TOKEN=your_telegram_bot_token
   
   # Optional (based on AI models you want to use)
   OPENAI_API_KEY=your_openai_key
   GROQ_API_KEY=your_groq_key
   DEEPSEEK_API_KEY=your_deepseek_key
   MISTRAL_API_KEY=your_mistral_key
   
   # Optional (for webhook deployment)
   WEBHOOK_URL=your_webhook_url
   PORT=your_port
   ```

5. Run the bot:
   ```bash
   python -m bot.main
   ```

## 📝 Usage Guide

### Basic Commands
- `/help` - Show all available commands
- `/tldr [number]` - Summarize last N messages
- `/splitbill` - Start bill splitting process
- `/dl <url>` - Download short-form video
- `/switch_model <model>` - Change AI model
- `/cancel` - Cancel current operation

### Bill Splitting Flow
1. Send `/splitbill`
2. Upload receipt photo
3. Add caption with payment context
4. Confirm or cancel the split

### Model Switching
Available models:
- `openai` - OpenAI's GPT models
- `groq` - Groq's Llama 3
- `deepseek` - DeepSeek models

## 🔧 Development

### Project Structure
```
TeleBot/
├── bot/
│   ├── config/         # Configuration settings
│   ├── handlers/       # Command and message handlers
│   ├── services/       # Core services (AI, Telegram)
│   ├── utils/          # Utility functions
│   └── main.py         # Bot entry point
├── requirements.txt    # Dependencies
└── README.md          # Documentation
```

### Extending the Bot
1. **New Commands**:
   - Add handler in `bot/handlers/command_handlers.py`
   - Register in `bot/main.py`

2. **New AI Models**:
   - Implement strategy in `bot/services/ai/`
   - Add to strategy registry

3. **Persistent Storage**:
   - Replace `MemoryStorage` with database implementation
   - Update storage interface

## 🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

## 🚦 Background Job Queueing with Redis

**LLM-powered commands** (like `/tldr`) are now handled via a Redis-backed job queue for maximum responsiveness and reliability.

- When a user calls `/tldr`, the bot **immediately replies** that the summary is being prepared.
- The request is **queued in Redis**.
- A **background worker** (part of the bot process) picks up the job, runs the LLM, and sends the summary as a new message in the chat.
- This ensures the bot remains responsive, even if the LLM is slow or under heavy load.

#### Sample User Experience

```
User: /tldr 30

Bot (immediately): Summarizing... I'll send the summary here when it's ready! 📝

Bot (a few seconds later):
_Conversation summarized for the last 30 messages:_
Summary: ...
Sentiment: ...
Events: ...
```

## 📊 Analytics & Event Logging

- TLDRBot logs all user interactions and commands to a relational database for analytics and monitoring.
- Events are stored in a `user_events` table with user, chat, event type, and timestamp.
- This enables usage tracking, feature analytics, and debugging.

#### Environment Variable
- `DATABASE_URL` (required): SQLAlchemy-compatible database URL (e.g., for Postgres).

#### Setup
- The bot will automatically create the required table on startup if it does not exist.

#### Example Table Schema

| Column      | Type         | Description                |
|-------------|--------------|----------------------------|
| id          | Integer      | Primary key                |
| user_id     | BigInteger   | Telegram user ID           |
| username    | String       | Telegram username          |
| first_name  | String       | User's first name          |
| last_name   | String       | User's last name           |
| chat_id     | BigInteger   | Telegram chat ID           |
| event_type  | String       | Type of event/command      |
| timestamp   | DateTime     | When the event occurred    |
| extra       | Text         | Optional extra data (JSON) |

## 🏗️ System Flow

```mermaid
graph TD
    User["User"] -- Telegram --> TLDRBotApplication["TLDRBot"]

    subgraph TLDRBotApplication
        direction TB
        TelegramInterface["Telegram API Interface\n(python-telegram-bot)"]:::main

        TelegramInterface --> RequestRouter["Update Router"]:::main

        RequestRouter -- "/command" --> CommandHandlers["Command Handlers"]:::main
        CommandHandlers -- "LLM Job" --> RedisQueue["Redis Job Queue"]:::queue
        RedisQueue -- "Job" --> LLMWorker["Background LLM Worker"]:::worker
        LLMWorker -- "Summary" --> TelegramInterface

        RequestRouter -- "message" --> MessageHandlers["Message Handlers"]:::main
        MessageHandlers --> AIService
        MessageHandlers --> MemoryStorageService

        subgraph Services["Core Services"]
            direction LR
            AIService --> AIModels["AI Models\n(OpenAI, Groq, DeepSeek)"]:::ai
            MemoryStorageService --> InMemoryDataStore["In-Memory Data Store"]:::storage
        end

        CommandHandlers --> MemoryStorageService
        CommandHandlers --> VideoDownloadService
        CommandHandlers --> BillSplittingService
        CommandHandlers -- "Analytics Event" --> AnalyticsDB["Analytics Storage (SQL DB)"]:::analytics
        MessageHandlers -- "Analytics Event" --> AnalyticsDB
    end

    TelegramInterface -- Telegram --> User

    %% Color Classes
    classDef main fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#222;
    classDef ai fill:#ede7f6,stroke:#7b1fa2,stroke-width:2px,color:#222;
    classDef queue fill:#fffde7,stroke:#fbc02d,stroke-width:2px,color:#222;
    classDef worker fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#222;
    classDef storage fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#222;
    classDef analytics fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px,color:#222;
```

## ⚙️ Environment Variables (Updated)

Add to your `.env` or Railway variables:

```
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
DEEPSEEK_API_KEY=your_deepseek_key
MISTRAL_API_KEY=your_mistral_key
WEBHOOK_URL=your_webhook_url
PORT=your_port
REDIS_URL=redis://<host>:<port>/<db>
DATABASE_URL=postgresql://user:password@host:port/dbname
```

- On Railway, `REDIS_URL` is provided by the Redis plugin.
- `DATABASE_URL` is required for analytics logging (Postgres recommended).
- Locally, you can use a local Redis instance or a cloud Redis URL.

## 🏁 Getting Started (Updated)

1. **Provision a Redis instance** (e.g., Railway Redis plugin, or local Redis).
2. **Provision a Postgres (or compatible) database** for analytics.
3. **Set `REDIS_URL` and `DATABASE_URL`** in your environment.
4. **Run the bot as before.**
