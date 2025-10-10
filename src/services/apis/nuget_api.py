from asyncio import get_running_loop, sleep
from io import BytesIO
from json import JSONDecodeError
from typing import Any
from zipfile import BadZipFile, ZipFile

from aiohttp import ClientConnectorError, ContentTypeError
from regex import search

from src.cache import CacheManager
from src.logger import logger
from src.session import SessionManager
from src.utils import Orderer, RepoNormalizer


class NuGetService:
    def __init__(self):
        self.cache: CacheManager = CacheManager(manager="nuget")
        self.BASE_URL = "https://api.nuget.org/v3/registration5-gz-semver2"
        self.SEARCH_URL = "https://azuresearch-usnc.nuget.org/query"
        self.DOWNLOAD_URL = "https://www.nuget.org/api/v2/package"
        self.orderer = Orderer("NuGetPackage")
        self.repo_normalizer = RepoNormalizer()

    async def fetch_all_package_names(self) -> list[str]:
        cached = await self.cache.get_cache("__all_packages__")
        if cached:
            return cached

        session = await SessionManager.get_session()
        all_package_names = []

        try:
            skip = 0
            take = 1000

            while True:
                url = f"{self.SEARCH_URL}?skip={skip}&take={take}"

                try:
                    async with session.get(url, timeout=30) as resp:
                        if resp.status != 200:
                            break

                        data = await resp.json()
                        packages = data.get("data", [])

                        if not packages:
                            break

                        for package in packages:
                            package_id = package.get("id")
                            if package_id:
                                all_package_names.append(package_id)

                        if skip % 10000 == 0 and skip > 0:
                            logger.info(f"NuGet - Fetched {len(all_package_names)} packages so far (skip={skip})")

                        total_hits = data.get("totalHits", 0)
                        if skip + take >= total_hits:
                            break

                        skip += take
                        await sleep(0.1)

                except Exception as e:
                    logger.warning(f"NuGet - Error fetching batch at skip={skip}: {e}")
                    skip += take
                    continue

            logger.info(f"NuGet - Completed fetching {len(all_package_names)} packages")
            await self.cache.set_cache("__all_packages__", all_package_names, ttl=3600)
            return all_package_names

        except Exception as e:
            logger.error(f"NuGet - Fatal error in fetch_all_package_names: {e}")
            return []

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

    async def extract_import_names(self, package_name: str, version: str) -> list[str]:
        cache_key = f"import_names:{package_name}:{version}"
        cached = await self.cache.get_cache(cache_key)
        if cached:
            logger.info(f"NuGet - import_names para {package_name}@{version} obtenidos de cache")
            return cached

        try:
            logger.info(f"NuGet - Extrayendo import_names de {package_name}@{version}")

            url = f"{self.DOWNLOAD_URL}/{package_name}/{version}"
            session = await SessionManager.get_session()

            async with session.get(url, timeout=30) as resp:
                if resp.status != 200:
                    logger.warning(f"NuGet - No se pudo descargar {package_name}@{version}: HTTP {resp.status}")
                    return []

                nupkg_bytes = await resp.read()

            loop = get_running_loop()
            import_names = await loop.run_in_executor(
                None, self.extract_from_nupkg_sync, nupkg_bytes, package_name
            )

            if import_names:
                await self.cache.set_cache(cache_key, import_names, ttl=604800)
                logger.info(f"NuGet - {len(import_names)} import_names extraídos de {package_name}@{version}")
            else:
                logger.warning(f"NuGet - No se encontraron import_names en {package_name}@{version}")

            return import_names

        except TimeoutError:
            logger.error(f"NuGet - Timeout al descargar {package_name}@{version}")
            return []
        except Exception as e:
            logger.error(f"NuGet - Error extrayendo import_names de {package_name}@{version}: {e}")
            return []

    def extract_from_nupkg_sync(self, nupkg_bytes: bytes, package_name: str) -> list[str]:
        import_names = set()

        try:
            with ZipFile(BytesIO(nupkg_bytes)) as nupkg_zip:
                for file_info in nupkg_zip.namelist():
                    if file_info.startswith("lib/") and file_info.endswith(".dll"):
                        dll_name = file_info.split("/")[-1][:-4]
                        if dll_name in ["System", "Microsoft.CSharp", "netstandard", "mscorlib"]:
                            continue
                        import_names.add(dll_name)

                for file_info in nupkg_zip.namelist():
                    if file_info.endswith(".nuspec"):
                        try:
                            nuspec_content = nupkg_zip.read(file_info).decode("utf-8")
                            id_match = search(r"<id>([^<]+)</id>", nuspec_content)
                            if id_match:
                                package_id = id_match.group(1)
                                import_names.add(package_id)
                        except Exception:
                            pass

            if not import_names and package_name:
                import_names.add(package_name)

            return sorted(import_names)

        except BadZipFile as e:
            logger.error(f"NuGet - Error de ZIP: {e}")
            return []
        except Exception as e:
            logger.error(f"NuGet - Error inesperado en extracción: {e}")
            return []
