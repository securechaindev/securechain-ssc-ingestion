from asyncio import sleep
from json import JSONDecodeError
from typing import Any

from aiohttp import ClientConnectorError, ContentTypeError

from src.cache import CacheManager
from src.session import SessionManager
from src.utils import Orderer, RepoNormalizer


class CargoService:
    def __init__(self):
        self.cache: CacheManager = CacheManager(manager="cargo")
        self.BASE_URL = "https://crates.io/api/v1/crates"
        self.orderer = Orderer("CargoService")
        self.repo_normalizer = RepoNormalizer()

    async def fetch_package_metadata(self, package_name: str) -> dict[str, Any] | None:
        cached = await self.cache.get_cache(package_name)
        if cached:
            return cached

        url = f"{self.BASE_URL}/{package_name}"
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

        url = f"{self.BASE_URL}/{package_name}/{version_name}/dependencies"
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
        for version_data in metadata.get("versions", []):
            version = version_data.get("num")
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

        crate_data = metadata.get("crate", {})
        raw_url = crate_data.get("repository")

        if raw_url:
            norm_url = await self.repo_normalizer.normalize(raw_url)
            if await self.repo_normalizer.check():
                return norm_url

        homepage = crate_data.get("homepage")
        if homepage:
            norm_url = await self.repo_normalizer.normalize(homepage)
            if await self.repo_normalizer.check():
                return norm_url

        return None

    async def get_package_requirements(self, metadata: dict[str, Any]) -> dict[str, Any]:
        requirements: dict[str, Any] = {}

        if not metadata:
            return requirements

        dependencies = metadata.get("dependencies", []) or []
        for dep in dependencies:
            crate_id = dep.get("crate_id")
            req = dep.get("req")
            if crate_id:
                requirements[crate_id.lower()] = req or ""

        return requirements
