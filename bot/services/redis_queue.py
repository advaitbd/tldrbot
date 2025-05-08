import redis.asyncio as redis
from config.settings import RedisConfig

QUEUE_NAME = "llm_job_queue"

class RedisQueue:
    def __init__(self):
        self.redis = redis.from_url(RedisConfig.URL)

    async def enqueue(self, job_data: dict):
        # Serialize job_data as JSON string
        import json
        await self.redis.rpush(QUEUE_NAME, json.dumps(job_data))

    async def dequeue(self, timeout: int = 0):
        # BLPOP returns (queue, data) or None
        import json
        result = await self.redis.blpop(QUEUE_NAME, timeout=timeout)
        if result:
            _, data = result
            return json.loads(data)
        return None 