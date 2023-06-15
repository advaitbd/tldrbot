from history import get_chat_history
from summarizer import get_summary
import asyncio

async def main():
    result = await get_chat_history()
    summary = get_summary(result)
    print(summary)

if __name__ == "__main__":
    asyncio.run(main())