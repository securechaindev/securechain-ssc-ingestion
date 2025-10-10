import io
import re
import tarfile
from asyncio import sleep, to_thread
from json import JSONDecodeError
from typing import Any

from aiohttp import ClientConnectorError, ContentTypeError

from src.cache import CacheManager
from src.logger import logger
from src.session import SessionManager
from src.utils import Orderer, RepoNormalizer


class CargoService:
    def __init__(self):
        self.cache: CacheManager = CacheManager(manager="cargo")
        self.BASE_URL = "https://crates.io/api/v1/crates"
        self.orderer = Orderer("CargoService")
        self.repo_normalizer = RepoNormalizer()

    async def fetch_all_package_names(self) -> list[str]:
        cached = await self.cache.get_cache("__all_packages__")
        if cached:
            return cached

        session = await SessionManager.get_session()
        all_package_names = []

        try:
            page = 1
            per_page = 100

            while True:
                url = f"{self.BASE_URL}?page={page}&per_page={per_page}"

                try:
                    async with session.get(url, timeout=30) as resp:
                        if resp.status != 200:
                            break

                        data = await resp.json()
                        crates = data.get("crates", [])

                        if not crates:
                            break

                        for crate in crates:
                            crate_name = crate.get("name")
                            if crate_name:
                                all_package_names.append(crate_name)

                        if page % 1000 == 0:
                            logger.info(f"Cargo - Fetched {len(all_package_names)} crates so far (page={page})")

                        meta = data.get("meta", {})
                        total = meta.get("total", 0)
                        if len(all_package_names) >= total:
                            break

                        page += 1
                        await sleep(0.1)

                except Exception as e:
                    logger.warning(f"Cargo - Error fetching page {page}: {e}")
                    page += 1
                    continue

            logger.info(f"Cargo - Completed fetching {len(all_package_names)} crates")
            await self.cache.set_cache("__all_packages__", all_package_names, ttl=3600)
            return all_package_names

        except Exception as e:
            logger.error(f"Cargo - Fatal error in fetch_all_package_names: {e}")
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

    async def extract_import_names(self, crate_name: str, version: str) -> list[str]:
        cache_key = f"import_names:{crate_name}:{version}"
        cached = await self.cache.get_cache(cache_key)
        if cached:
            return cached

        download_url = f"https://crates.io/api/v1/crates/{crate_name}/{version}/download"
        session = await SessionManager.get_session()

        try:
            async with session.get(download_url, timeout=30) as resp:
                if resp.status != 200:
                    logger.warning(f"Cargo - Failed to download {crate_name}@{version}: HTTP {resp.status}")
                    return []

                crate_bytes = await resp.read()
                import_names = await to_thread(self.extract_from_tarball, crate_name, crate_bytes)

                await self.cache.set_cache(cache_key, import_names, ttl=604800)
                return import_names

        except Exception as e:
            logger.error(f"Cargo - Error extracting import_names for {crate_name}@{version}: {e}")
            return []

    def extract_from_tarball(self, crate_name: str, crate_bytes: bytes) -> list[str]:
        import_names = set()

        try:
            with tarfile.open(fileobj=io.BytesIO(crate_bytes), mode="r:gz") as tar:
                rs_files = [m for m in tar.getmembers() if m.name.endswith(".rs")]

                for member in rs_files:
                    try:
                        file_data = tar.extractfile(member).read().decode("utf-8", errors="replace")

                        import_names.update(self.extract_public_items(crate_name, file_data))

                    except UnicodeDecodeError:
                        logger.warning(f"Cargo - Unicode decode error in {member.name}")
                        continue
                    except Exception as e:
                        logger.warning(f"Cargo - Error processing {member.name}: {e}")
                        continue

            import_names.add(crate_name)
            return sorted(import_names)

        except tarfile.ReadError as e:
            logger.error(f"Cargo - Error reading tarball for {crate_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Cargo - Unexpected error extracting {crate_name}: {e}")
            return []

    def extract_public_items(self, crate_name: str, file_data: str) -> set[str]:
        items = set()

        pub_mods = re.findall(r'\bpub\s+mod\s+(\w+)', file_data)
        for mod in pub_mods:
            items.add(f"{crate_name}::{mod}")

        pub_uses = re.findall(r'\bpub\s+use\s+(?:[\w:]+::)?(\w+)', file_data)
        for name in pub_uses:
            items.add(f"{crate_name}::{name}")

        pub_structs = re.findall(r'\bpub\s+struct\s+(\w+)', file_data)
        for struct in pub_structs:
            items.add(f"{crate_name}::{struct}")

        pub_enums = re.findall(r'\bpub\s+enum\s+(\w+)', file_data)
        for enum in pub_enums:
            items.add(f"{crate_name}::{enum}")

        pub_traits = re.findall(r'\bpub\s+trait\s+(\w+)', file_data)
        for trait in pub_traits:
            items.add(f"{crate_name}::{trait}")

        pub_fns = re.findall(r'^\s*pub\s+(?:const\s+|async\s+|unsafe\s+)*fn\s+(\w+)', file_data, re.MULTILINE)
        for fn in pub_fns:
            items.add(f"{crate_name}::{fn}")

        pub_consts = re.findall(r'\bpub\s+const\s+(\w+)', file_data)
        for const in pub_consts:
            items.add(f"{crate_name}::{const}")

        pub_statics = re.findall(r'\bpub\s+static\s+(\w+)', file_data)
        for static in pub_statics:
            items.add(f"{crate_name}::{static}")

        pub_macro_rules = re.findall(r'#\[macro_export\]\s*macro_rules!\s+(\w+)', file_data)
        for macro in pub_macro_rules:
            items.add(f"{crate_name}::{macro}")

        pub_macros = re.findall(r'\bpub\s+macro\s+(\w+)', file_data)
        for macro in pub_macros:
            items.add(f"{crate_name}::{macro}")

        pub_types = re.findall(r'\bpub\s+type\s+(\w+)', file_data)
        for type_alias in pub_types:
            items.add(f"{crate_name}::{type_alias}")

        return items
