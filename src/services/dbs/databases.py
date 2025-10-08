from functools import lru_cache

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
)
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.settings import settings


@lru_cache
def get_graph_db_driver() -> AsyncDriver:
    return AsyncGraphDatabase.driver(
        uri=settings.GRAPH_DB_URI,
        auth=(settings.GRAPH_DB_USER, settings.GRAPH_DB_PASSWORD),
    )


@lru_cache
def get_vulnerabilities_collection() -> AsyncIOMotorCollection:
    client: AsyncIOMotorClient = AsyncIOMotorClient(settings.VULN_DB_URI)
    return client.get_database("vulnerabilities").get_collection("vulnerabilities")
