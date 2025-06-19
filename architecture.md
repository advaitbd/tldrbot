# TeleBot Architecture

## Overview

TeleBot is a modular, AI-powered Telegram bot designed for group productivity, featuring conversation summarization, bill splitting, and media handling. The architecture emphasizes extensibility, separation of concerns, and support for multiple AI providers.

---

## High-Level Architecture

```mermaid
flowchart TD
    subgraph Telegram
        User1(User)
        User2(User)
    end

    subgraph Bot
        Main[Main Entrypoint]
        CommandHandlers
        MessageHandlers
        TelegramService
        BillSplitter
        AIService
        MemoryStorage
        AnalyticsStorage
        RedisQueue
    end

    subgraph AI_Providers
        OpenAI
        Groq
        DeepSeek
    end

    User1 -- Telegram API --> Main
    User2 -- Telegram API --> Main

    Main --> CommandHandlers
    Main --> MessageHandlers
    Main --> TelegramService
    Main --> RedisQueue

    CommandHandlers --> BillSplitter
    CommandHandlers --> AIService
    CommandHandlers --> MemoryStorage
    CommandHandlers --> AnalyticsStorage
    CommandHandlers --> RedisQueue

    MessageHandlers --> AIService
    MessageHandlers --> MemoryStorage

    BillSplitter --> AIService

    AIService --> OpenAI
    AIService --> Groq
    AIService --> DeepSeek

    TelegramService --> Main

    MemoryStorage --> Main
    AnalyticsStorage --> Main
    RedisQueue --> Main
```

---

## Component Breakdown

### 1. Main Entrypoint (`main.py`)

- Initializes all core services and handlers.
- Registers command and message handlers with the Telegram application.
- Manages the event loop and background workers (e.g., for LLM jobs).

### 2. Command Handlers

- Handle bot commands (e.g., `/tldr`, `/split`, `/dl`, `/switch_model`).
- Orchestrate conversation flows and interact with services.
- Log analytics events.

### 3. Message Handlers

- Process regular chat messages and replies.
- Manage context-aware responses (e.g., follow-up questions on summaries).
- Interface with memory storage for chat history.

### 4. AI Service (Strategy Pattern)

- Abstracts multiple AI providers (OpenAI, Groq, DeepSeek).
- Selects and switches models dynamically per user or chat.
- Handles summarization, context parsing, and OCR tasks.

```mermaid
classDiagram
    class AIService {
        - AIModelStrategy _strategy
        + set_strategy(strategy)
        + get_response(prompt)
        + get_current_model()
    }
    class AIModelStrategy {
        <<interface>>
        + get_response(prompt)
        + get_current_model()
    }
    class OpenAIStrategy
    class GroqAIStrategy
    class DeepSeekStrategy

    AIService --> AIModelStrategy
    AIModelStrategy <|.. OpenAIStrategy
    AIModelStrategy <|.. GroqAIStrategy
    AIModelStrategy <|.. DeepSeekStrategy
```

### 5. Memory Storage

- In-memory storage of recent messages per chat (up to 400).
- Stores summary context for follow-up Q&A.
- Fast, ephemeral; not persisted across restarts.

### 6. Analytics Storage

- SQLAlchemy-based persistent logging of user events.
- Stores command usage, LLM model used, and metadata for analytics.

### 7. Bill Splitting System

- **Receipt Processing Pipeline**:
    - Receives image uploads.
    - Uses OCR (OpenAI GPT-4o) to extract text.
    - Parses payment context using LLM.
    - Calculates and formats split results.
- Interactive confirmation flow with users.

```mermaid
sequenceDiagram
    participant User
    participant Bot
    participant BillSplitter
    participant AIService
    participant OCR
    User->>Bot: /split + receipt image
    Bot->>BillSplitter: extract_receipt_data_from_image
    BillSplitter->>OCR: OCR image
    OCR-->>BillSplitter: Text data
    BillSplitter->>AIService: parse_payment_context_with_llm
    AIService-->>BillSplitter: Parsed assignments
    BillSplitter->>Bot: calculate_split, format_split_results
    Bot->>User: Show split, ask for confirmation
```

### 8. Telegram Service

- Handles media downloads (e.g., TikTok videos).
- Sends files and messages back to users.

### 9. Redis Queue

- Asynchronous job queue for LLM tasks.
- Decouples heavy AI processing from main event loop.

---

## Data Flow: Conversation Summarization

```mermaid
sequenceDiagram
    participant User
    participant TelegramAPI
    participant Bot
    participant MemoryStorage
    participant AIService
    User->>TelegramAPI: /tldr
    TelegramAPI->>Bot: Command update
    Bot->>MemoryStorage: get_recent_messages
    MemoryStorage-->>Bot: Last N messages
    Bot->>AIService: get_response (summarize prompt)
    AIService-->>Bot: Summary text
    Bot->>TelegramAPI: Send summary
    TelegramAPI->>User: Summary message
```

---

## Data Flow: Model Switching

```mermaid
sequenceDiagram
    participant User
    participant Bot
    participant CommandHandlers
    participant AIService
    User->>Bot: /switch_model groq
    Bot->>CommandHandlers: handle_switch_model
    CommandHandlers->>AIService: set_strategy(GroqAIStrategy)
    AIService-->>CommandHandlers: Confirmation
    CommandHandlers->>User: Model switched message
```

---

## Data Flow: Analytics Logging

```mermaid
sequenceDiagram
    participant User
    participant Bot
    participant AnalyticsStorage
    User->>Bot: /tldr
    Bot->>AnalyticsStorage: log_user_event (user_id, chat_id, event_type, llm_name, ...)
    AnalyticsStorage-->>Bot: Success
```

---

## Extensibility

- **AI Providers**: Add new strategies by implementing `AIModelStrategy` and registering in `StrategyRegistry`.
- **Commands**: Add new command handlers in `handlers/command_handlers.py`.
- **Persistence**: Swap in-memory storage for persistent DB by extending `MemoryStorage`.
- **Analytics**: Extend `UserEvent` model for richer analytics.

---

## Environment & Configuration

- All secrets and config are loaded from environment variables (see `config/settings.py`).
- Supports BYOK (Bring Your Own Key) for user-specific LLM API keys.

---

## Directory Structure (Key Parts)

```
TeleBot/
  bot/
    main.py                # Entrypoint
    handlers/              # Command and message handlers
    services/
      ai/                  # AI strategies and service
      bill_splitter.py     # Bill splitting logic
      telegram_service.py  # Media handling
      redis_queue.py       # Async job queue
    utils/
      memory_storage.py    # In-memory chat storage
      analytics_storage.py # Persistent analytics
      text_processor.py    # Markdown/text helpers
      user/                # User API key management
    config/
      settings.py          # Environment/config management
    data/
      database.sqlite      # SQLite DB (if used)
```

---

## Summary

TeleBot's architecture is modular, extensible, and designed for robust group chat productivity. The use of strategy patterns, clear separation of concerns, and asynchronous processing ensures maintainability and scalability for future features and AI integrations.