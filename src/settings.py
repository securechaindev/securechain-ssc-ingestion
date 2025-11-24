from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

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

    # Database Configuration
    DB_MIN_POOL_SIZE: int = 10
    DB_MAX_POOL_SIZE: int = 100
    DB_MAX_IDLE_TIME_MS: int = 60000
    DB_DEFAULT_QUERY_TIMEOUT_MS: int = 30000
    DB_SMTS_COLLECTION: str = "smts"
    DB_OPERATION_RESULT_COLLECTION: str = "operation_results"
    DB_API_KEY_COLLECTION: str = "api_keys"
    DB_VULNERABILITIES_COLLECTION: str = "vulnerabilities"

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
