from asyncio import sleep
from json import JSONDecodeError
from typing import Any

from aiohttp import ClientConnectorError, ContentTypeError
from regex import findall

from src.cache import CacheManager
from src.session import SessionManager
from src.utils import (
    Orderer,
    PyPIConstraintsParser,
    RepoNormalizer,
)


class PyPIService:
    def __init__(self):
        self.cache: CacheManager = CacheManager(manager="pypi")
        self.BASE_URL = "https://pypi.python.org/pypi"
        self.SIMPLE_URL = "https://pypi.org/simple"
        self.orderer = Orderer("PyPIPackage")
        self.repo_normalizer = RepoNormalizer()
        self.pypi_constraints_parser = PyPIConstraintsParser()

    async def fetch_all_package_names(self) -> list[str]:
        cached = await self.cache.get_cache("all_pypi_packages")
        if cached:
            return cached

        url = f"{self.SIMPLE_URL}/"
        session = await SessionManager.get_session()

        try:
            async with session.get(url) as resp:
                html = await resp.text()
                pattern = r'<a href="[^"]*">([^<]+)</a>'
                package_names = findall(pattern, html)
                await self.cache.set_cache("all_pypi_packages", package_names, ttl=3600)
                return package_names
        except (ClientConnectorError, TimeoutError, Exception) as _:
            return []

    async def fetch_package_metadata(self, package_name: str) -> dict[str, Any] | None:
        cached = await self.cache.get_cache(package_name)
        if cached:
            return cached

        url = f"{self.BASE_URL}/{package_name}/json"
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

        url = f"{self.BASE_URL}/{package_name}/{version_name}/json"
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
        for version, files in (metadata.get("releases") or {}).items():
            upload_time = None
            if files:
                f = files[0]
                upload_time = f.get("upload_time_iso_8601") or f.get("upload_time")
            raw_versions.append({"name": version, "release_date": upload_time})
        return raw_versions

    async def get_versions(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        if not metadata:
            return []
        raw = await self.extract_raw_versions(metadata)
        return await self.orderer.order_versions(raw)

    async def get_repo_url(self, metadata: dict[str, Any]) -> str | None:
        if not metadata:
            return None

        info = metadata.get("info", {})
        raw_url = info.get("home_page")
        norm_url = await self.repo_normalizer.normalize(raw_url)
        if await self.repo_normalizer.check():
            return norm_url

        project_urls = info.get("project_urls") or {}
        for _, raw_url in project_urls.items():
            norm_url = await self.repo_normalizer.normalize(raw_url)
            if await self.repo_normalizer.check():
                return norm_url

        return None

    async def get_package_requirements(self, metadata: dict[str, Any]) -> dict[str, Any]:
        requirements: dict[str, Any] = {}

        for dependency in metadata.get("info", {}).get("requires_dist", []) or []:
            data = dependency.split(";")

            if "python-version" in data[0]:
                continue
            if len(data) > 1 and "extra" in data[1]:
                continue
            if len(data) > 1:
                python_version = any(
                    sub in data[1]
                    for sub in [
                        '== "3.10"', '<= "3.10"', '>= "3.10"',
                        '>= "3"', '<= "3"', '>= "2', '> "2'
                    ]
                )
                if "python_version" in data[1] and not python_version:
                    continue

            if "[" in data[0]:
                pos_1 = await self.pypi_constraints_parser.get_first_position(data[0], ["["])
                pos_2 = await self.pypi_constraints_parser.get_first_position(data[0], ["]"]) + 1
                data[0] = data[0][:pos_1] + data[0][pos_2:]

            data = data[0].replace("(", "").replace(")", "").replace(" ", "").replace("'", "")
            pos = await self.pypi_constraints_parser.get_first_position(data, ["<", ">", "=", "!", "~"])
            requirements[data[:pos].lower()] = await self.pypi_constraints_parser.parse(data[pos:])

        return requirements
