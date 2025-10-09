from asyncio import sleep
from json import JSONDecodeError
from typing import Any

from aiohttp import ClientConnectorError, ContentTypeError

from src.cache import CacheManager
from src.session import SessionManager
from src.utils import Orderer, RepoNormalizer


class NPMService:
    def __init__(self):
        self.cache: CacheManager = CacheManager(manager="npm")
        self.BASE_URL = "https://registry.npmjs.org"
        self.REPLICATE_URL = "https://replicate.npmjs.com/_all_docs"
        self.orderer = Orderer("NPMService")
        self.repo_normalizer = RepoNormalizer()

    async def fetch_all_package_names(self) -> list[str]:
        cached = await self.cache.get_cache("all_npm_packages")
        if cached:
            return cached

        session = await SessionManager.get_session()
        package_names = []

        try:
            url = self.REPLICATE_URL
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                rows = data.get("rows", [])

                for row in rows:
                    package_id = row.get("id")
                    if package_id and not package_id.startswith("_design/"):
                        package_names.append(package_id)

                await self.cache.set_cache("all_npm_packages", package_names, ttl=3600)
                return package_names
      
        except (ClientConnectorError, TimeoutError, JSONDecodeError, ContentTypeError, Exception):
            return []

    async def fetch_package_metadata(self, package_name: str) -> dict[str, Any] | None:
        cached = await self.cache.get_cache(package_name)
        if cached:
            return cached

        url = f"{self.BASE_URL}/{package_name}"
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
        versions_data = metadata.get("versions", {})
        time_data = metadata.get("time", {})

        for version_name, version_info in versions_data.items():
            release_date = time_data.get(version_name)
            raw_versions.append({
                "name": version_name,
                "release_date": release_date
            })
            dependencies = version_info.get("dependencies", {})
            requirements.append(dependencies)

        return raw_versions, requirements

    async def get_versions_and_requirements(self, metadata: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not metadata:
            return [], []
        raw_versions, requirements = await self.extract_raw_versions_and_requirements(metadata)
        versions = await self.orderer.order_versions(raw_versions)
        return versions, requirements

    async def get_versions(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """Get ordered versions from metadata."""
        if not metadata:
            return []
        raw_versions, _ = await self.extract_raw_versions_and_requirements(metadata)
        return await self.orderer.order_versions(raw_versions)

    async def fetch_package_version_metadata(self, package_name: str, version_name: str) -> dict[str, Any] | None:
        """
        Fetch metadata for a specific version of a package.
        For NPM, we can extract this from the full package metadata.
        """
        metadata = await self.fetch_package_metadata(package_name)
        if not metadata:
            return None
        
        versions_data = metadata.get("versions", {})
        return versions_data.get(version_name)

    async def get_package_requirements(self, version_metadata: dict[str, Any]) -> dict[str, str]:
        """Get dependencies from a specific version metadata."""
        if not version_metadata:
            return {}
        return version_metadata.get("dependencies", {})

    async def get_repo_url(self, metadata: dict[str, Any]) -> str | None:
        if not metadata:
            return None

        raw_url = None
        repository = metadata.get("repository")
        if repository:
            if isinstance(repository, dict):
                raw_url = repository.get("url")
            else:
                raw_url = repository

            if raw_url:
                norm_url = await self.repo_normalizer.normalize(raw_url)
                if await self.repo_normalizer.check():
                    return norm_url

        homepage = metadata.get("homepage")
        if homepage:
            norm_url = await self.repo_normalizer.normalize(homepage)
            if await self.repo_normalizer.check():
                return norm_url

        bugs = metadata.get("bugs")
        if bugs and isinstance(bugs, dict):
            bugs_url = bugs.get("url")
            if bugs_url:
                norm_url = await self.repo_normalizer.normalize(bugs_url)
                if await self.repo_normalizer.check():
                    return norm_url

        return None
