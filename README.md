# tldrbot

## Commands:
/tldr : Summarises past 50 messages
/tldr x : Summarises past x messages
/dl x: Download videos at the link provided (e.g. TikTok, Youtube Shorts, Instagram Reels, etc.)

## Architecture:
```mermaid
graph TD
    A[User] -->|Interacts via Telegram| B[Bot]
    B --> C[CommandHandlers]
    B --> D[MessageHandlers]
    B --> E[TelegramService]
    C --> F[AIService]
    D --> F
    C --> G[MemoryStorage]
    D --> G
    F --> H[StrategyRegistry]
    H --> I[OpenAIStrategy]
    H --> J[GroqAIStrategy]
    E --> K[yt-dlp]
    G --> L[In-Memory Storage]

    subgraph Telegram Flow
        A -->|Sends Message| B
        B -->|Handles Command/Message| C
        B -->|Handles Message| D
    end

    subgraph AI Flow
        C --> F --> H
        D --> F --> H
        H --> I
        H --> J
    end

    subgraph Memory Flow
        B --> G --> L
    end

    subgraph Video Download Flow
        E --> K
    end

    B -->|Sends Message| A

```
