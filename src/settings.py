from functools import lru_cache

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    # Database connections (required)
    GRAPH_DB_URI: str = Field(..., alias="GRAPH_DB_URI")
    GRAPH_DB_USER: str = Field(..., alias="GRAPH_DB_USER")
    GRAPH_DB_PASSWORD: str = Field(..., alias="GRAPH_DB_PASSWORD")
    VULN_DB_URI: str = Field(..., alias="VULN_DB_URI")

    # Redis Configuration
    REDIS_HOST: str = Field("localhost", alias="REDIS_HOST")
    REDIS_PORT: int = Field(6379, alias="REDIS_PORT")
    REDIS_DB: int = Field(0, alias="REDIS_DB")
    REDIS_STREAM: str = Field("package-extraction", alias="REDIS_STREAM")
    REDIS_GROUP: str = Field("extractors", alias="REDIS_GROUP")
    REDIS_CONSUMER: str = Field("package-consumer", alias="REDIS_CONSUMER")

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
