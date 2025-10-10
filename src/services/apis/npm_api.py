from asyncio import sleep, to_thread
from io import BytesIO
from json import JSONDecodeError
from tarfile import ReadError
from tarfile import open as open_tarfile
from typing import Any

from aiohttp import ClientConnectorError, ContentTypeError

from src.cache import CacheManager
from src.logger import logger
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

    async def extract_import_names(self, package_name: str, version: str) -> list[str]:
        cache_key = f"import_names:{package_name}:{version}"
        cached = await self.cache.get_cache(cache_key)
        if cached:
            return cached

        metadata_url = f"{self.BASE_URL}/{package_name.replace('/', '%2F')}"
        session = await SessionManager.get_session()

        try:
            async with session.get(metadata_url, timeout=30) as resp:
                if resp.status != 200:
                    logger.warning(f"NPM - Failed to get metadata for {package_name}@{version}: HTTP {resp.status}")
                    return []

                metadata = await resp.json()

                versions = metadata.get("versions", {})
                version_data = versions.get(version)

                if not version_data:
                    logger.warning(f"NPM - Version {version} not found for {package_name}")
                    return []

                tarball_url = version_data.get("dist", {}).get("tarball")

                if not tarball_url:
                    logger.warning(f"NPM - No tarball URL found for {package_name}@{version}")
                    return []

            async with session.get(tarball_url, timeout=30) as resp:
                if resp.status != 200:
                    logger.warning(f"NPM - Failed to download {package_name}@{version}: HTTP {resp.status}")
                    return []

                tgz_bytes = await resp.read()
                import_names = await to_thread(self.extract_from_tarball, package_name, tgz_bytes)

                await self.cache.set_cache(cache_key, import_names, ttl=604800)
                return import_names

        except Exception as e:
            logger.error(f"NPM - Error extracting import_names for {package_name}@{version}: {e}")
            return []

    def extract_from_tarball(self, package_name: str, tgz_bytes: bytes) -> list[str]:
        import_names = set()

        try:
            with open_tarfile.open(fileobj=BytesIO(tgz_bytes), mode="r:gz") as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        name = member.name
                        if name.endswith(('.js', '.mjs', '.ts')) and name.startswith('package/'):
                            path = name[len("package/"):]

                            if path.startswith("node_modules") or path.startswith("test") or "internal" in path:
                                continue

                            if path.endswith("index.js"):
                                import_names.add(package_name)
                            else:
                                for ext in ['.js', '.mjs', '.ts']:
                                    if path.endswith(ext):
                                        module = path[:-len(ext)]
                                        break
                                else:
                                    module = path

                                import_name = f"{package_name}/{module}"
                                import_names.add(import_name.replace("\\", "/"))

            return sorted(import_names)

        except ReadError:
            logger.warning(f"NPM - Bad tarball file for {package_name}")
            return []
        except Exception as e:
            logger.error(f"NPM - Unexpected error extracting {package_name}: {e}")
            return []
