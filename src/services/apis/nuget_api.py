from asyncio import sleep
from json import JSONDecodeError
from typing import Any

from aiohttp import ClientConnectorError, ContentTypeError

from src.cache import CacheManager
from src.session import SessionManager
from src.utils import Orderer, RepoNormalizer


class NuGetService:
    def __init__(self):
        self.cache: CacheManager = CacheManager(manager="nuget")
        self.BASE_URL = "https://api.nuget.org/v3/registration5-gz-semver2"
        self.orderer = Orderer("NuGetPackage")
        self.repo_normalizer = RepoNormalizer()

    async def fetch_page_versions(self, url: str) -> list[dict[str, Any]]:
        cached = await self.cache.get_cache(url)
        if cached:
            return cached

        session = await SessionManager.get_session()
        for _ in range(3):
            try:
                async with session.get(url) as resp:
                    if resp.status == 404:
                        return []
                    response = await resp.json()
                    items = response.get("items", [])
                    await self.cache.set_cache(url, items)
                    return items
            except (ClientConnectorError, TimeoutError):
                await sleep(5)
            except (JSONDecodeError, ContentTypeError):
                return []
        return []

    async def fetch_package_metadata(self, package_name: str) -> dict[str, Any] | None:
        cached = await self.cache.get_cache(package_name)
        if cached:
            return cached

        url = f"{self.BASE_URL}/{package_name}/index.json"
        session = await SessionManager.get_session()

        for _ in range(3):
            try:
                async with session.get(url) as resp:
                    if resp.status == 404:
                        return None
                    response = await resp.json()
                    await self.cache.set_cache(package_name, response)
                    return response
            except (ClientConnectorError, TimeoutError):
                await sleep(5)
            except (JSONDecodeError, ContentTypeError):
                return None
        return None

    async def extract_raw_versions_and_requirements(self, metadata: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        raw_versions = []
        requirements = []

        for item in metadata.get("items", []):
            subitems = item.get("items") or await self.fetch_page_versions(item.get("@id", ""))
            for version_item in subitems:
                catalog_entry = version_item.get("catalogEntry", {})
                name = catalog_entry.get("version")
                release_date = catalog_entry.get("published")

                if name:
                    raw_versions.append({"name": name, "release_date": release_date})

                    dependencies = {
                        dep.get("id"): dep.get("range")
                        for group in catalog_entry.get("dependencyGroups", [])
                        if "targetFramework" not in group
                        for dep in group.get("dependencies", [])
                    }
                    requirements.append(dependencies)

        return raw_versions, requirements

    async def get_versions_and_requirements(self, metadata: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not metadata:
            return [], []
        raw_versions, requirements = await self.extract_raw_versions_and_requirements(metadata)
        versions = await self.orderer.order_versions(raw_versions)
        return versions, requirements

    async def get_repo_url(self, metadata: dict[str, Any]) -> str | None:
        if not metadata:
            return None

        for item in metadata.get("items", []):
            subitems = item.get("items") or await self.fetch_page_versions(item.get("@id", ""))
            for version_item in subitems:
                catalog_entry = version_item.get("catalogEntry", {})
                raw_url = catalog_entry.get("repositoryUrl")

                if raw_url:
                    norm_url = await self.repo_normalizer.normalize(raw_url)
                    if norm_url and await self.repo_normalizer.check():
                        return norm_url

        return None
