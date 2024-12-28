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
    C --> F[OpenAIService]
    D --> F
    C --> G[MemoryStorage]
    D --> G
    F --> H[OpenAI API]
    E --> I[yt-dlp]
    G --> J[In-Memory Storage]
    
    subgraph Telegram Flow
        A -->|Sends Message| B
        B -->|Handles Command/Message| C
        B -->|Handles Message| D
    end

    subgraph OpenAI Flow
        C --> F --> H
        D --> F --> H
    end

    subgraph Memory Flow
        B --> G --> J
    end

    subgraph Video Download Flow
        E --> I
    end

    B -->|Sends Message| A

```

