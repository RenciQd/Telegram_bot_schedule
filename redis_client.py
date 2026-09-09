import os

from dotenv import load_dotenv

load_dotenv()

import redis.asyncio as redis_lib

REDIS_URL = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_REST_URL")
if not REDIS_URL:
    raise RuntimeError(
        "Не задана переменная окружения REDIS_URL (или UPSTASH_REDIS_REST_URL). "
        "Скопируй .env.example в .env и заполни его."
    )

redis = redis_lib.from_url(REDIS_URL, decode_responses=True)
