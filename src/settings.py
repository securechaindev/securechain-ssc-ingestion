from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GRAPH_DB_URI: str = "bolt://localhost:7687"
    GRAPH_DB_USER: str = "neo4j"
    GRAPH_DB_PASSWORD: str = "neoSecureChain"
    VULN_DB_URI: str = "mongodb://mongoSecureChain:mongoSecureChain@localhost:27017/admin"
    VULN_DB_USER: str = "mongoSecureChain"
    VULN_DB_PASSWORD: str = "mongoSecureChain"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_STREAM: str = "package_extraction"
    REDIS_GROUP: str = "extractors"
    REDIS_CONSUMER: str = "package-consumer"


    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
