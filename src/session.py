from aiohttp import ClientSession, ClientTimeout


class SessionManager:
    session: ClientSession | None = None

    @classmethod
    async def get_session(cls) -> ClientSession:
        if cls.session is None or cls.session.closed:
            timeout = ClientTimeout(total=60, connect=10)
            cls.session = ClientSession(timeout=timeout)
        return cls.session

    @classmethod
    async def close(cls):
        if cls.session and not cls.session.closed:
            await cls.session.close()
