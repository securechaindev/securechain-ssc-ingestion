import os

import redis

STREAM = os.getenv("REDIS_STREAM", "package_extraction")
GROUP = os.getenv("REDIS_GROUP", "extractors")
CONSUMER = os.getenv("REDIS_CONSUMER", "pypi-consumer")

class RedisQueue:
    def __init__(self, host: str, port: int, db: int = 0):
        self.r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        try:
            self.r.xgroup_create(STREAM, GROUP, id="0-0", mkstream=True)
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    @classmethod
    def from_env(cls) -> "RedisQueue":
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))
        return cls(host, port, db)

    def read_batch(self, count: int = 20, block_ms: int | None = None) -> list[tuple[str, str]]:
        """
        Devuelve lista de (msg_id, raw_json) desde el consumer group.
        """
        resp = self.r.xreadgroup(GROUP, CONSUMER, {STREAM: ">"}, count=count, block=block_ms)
        if not resp:
            return []
        entries = resp[0][1]
        result = []
        for msg_id, fields in entries:
            raw = fields.get("data")
            if raw:
                result.append((msg_id, raw))
        return result

    def ack(self, msg_id: str) -> None:
        self.r.xack(STREAM, GROUP, msg_id)

    def dead_letter(self, msg_id: str, raw: str, error: str) -> None:
        self.r.xadd(f"{STREAM}-dlq", {"data": raw, "error": error})
        self.ack(msg_id)
