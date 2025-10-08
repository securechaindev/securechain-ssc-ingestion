from asyncio import sleep
from json import JSONDecodeError
from typing import Any

from aiohttp import ClientConnectorError, ContentTypeError

from src.cache import CacheManager
from src.session import SessionManager
from src.utils import Orderer, RepoNormalizer


class RubyGemsService:
    def __init__(self):
        self.cache: CacheManager = CacheManager(manager="rubygems")
        self.BASE_V1_URL = "https://rubygems.org/api/v1/versions"
        self.BASE_V2_URL = "https://rubygems.org/api/v2/rubygems"
        self.orderer = Orderer("RubyGemsPackage")
        self.repo_normalizer = RepoNormalizer()

    async def fetch_package_metadata(self, package_name: str) -> dict[str, Any] | None:
        cached = await self.cache.get_cache(package_name)
        if cached:
            return cached

        url = f"{self.BASE_V1_URL}/{package_name}.json"
        session = await SessionManager.get_session()

        for _ in range(3):
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    await self.cache.set_cache(package_name, response)
                    return response
            except (ClientConnectorError, TimeoutError):
                await sleep(5)
            except (JSONDecodeError, ContentTypeError):
                return None
        return None

    async def fetch_package_version_metadata(self, package_name: str, version_name: str) -> dict[str, Any] | None:
        cache_key = f"{package_name}:{version_name}"
        cached = await self.cache.get_cache(cache_key)
        if cached:
            return cached

        url = f"{self.BASE_V2_URL}/{package_name}/versions/{version_name}.json"
        session = await SessionManager.get_session()

        for _ in range(3):
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    await self.cache.set_cache(cache_key, response)
                    return response
            except (ClientConnectorError, TimeoutError):
                await sleep(5)
            except (JSONDecodeError, ContentTypeError):
                return None
        return None

    async def extract_raw_versions(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        raw_versions = []
        if isinstance(metadata, list):
            for version_data in metadata:
                version = version_data.get("number")
                created_at = version_data.get("created_at")
                if version:
                    raw_versions.append({"name": version, "release_date": created_at})
        return raw_versions

    async def get_versions(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        if not metadata:
            return []
        raw = await self.extract_raw_versions(metadata)
        return await self.orderer.order_versions(raw)

    async def get_repo_url(self, metadata: dict[str, Any]) -> str | None:
        if not metadata:
            return None

        if isinstance(metadata, list):
            for version_data in metadata:
                version_metadata = version_data.get("metadata", {})
                raw_url = (version_metadata.get("source_code_uri") or
                          version_metadata.get("homepage_uri") or
                          version_metadata.get("bug_tracker_uri"))

                if raw_url:
                    norm_url = await self.repo_normalizer.normalize(raw_url)
                    if norm_url and await self.repo_normalizer.check():
                        return norm_url

        return None

    async def get_package_requirements(self, metadata: dict[str, Any]) -> dict[str, Any]:
        requirements: dict[str, Any] = {}

        if not metadata:
            return requirements

        dependencies = metadata.get("dependencies", {})
        runtime_deps = dependencies.get("runtime", []) or []

        for dep in runtime_deps:
            name = dep.get("name")
            req = dep.get("requirements")
            if name:
                requirements[name.lower()] = req or ""

        return requirements
