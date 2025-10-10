from aiohttp import ClientSession, ClientTimeout


class SessionManager:
    _session: ClientSession | None = None

    @classmethod
    async def get_session(cls) -> ClientSession:
        if cls._session is None or cls._session.closed:
            timeout = ClientTimeout(total=60, connect=10)
            cls._session = ClientSession(timeout=timeout)
        return cls._session

    @classmethod
    async def close(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
