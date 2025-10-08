from asyncio import sleep
from json import JSONDecodeError
from typing import Any

from aiohttp import ClientConnectorError, ContentTypeError

from src.cache import CacheManager
from src.session import SessionManager
from src.utils import Orderer, RepoNormalizer


class MavenService:
    def __init__(self):
        self.cache: CacheManager = CacheManager(manager="maven")
        self.BASE_URL = "https://search.maven.org/solrsearch/select"
        self.CENTRAL_URL = "https://repo1.maven.org/maven2"
        self.orderer = Orderer("MavenService")
        self.repo_normalizer = RepoNormalizer()

    async def fetch_package_metadata(self, group_id: str, artifact_id: str) -> dict[str, Any] | None:
        package_name = f"{group_id}:{artifact_id}"
        cached = await self.cache.get_cache(package_name)
        if cached:
            return cached

        url = f"{self.BASE_URL}?q=g:{group_id}+AND+a:{artifact_id}&core=gav&rows=200&wt=json"
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

    async def fetch_package_version_metadata(self, group_id: str, artifact_id: str, version_name: str) -> dict[str, Any] | None:
        cache_key = f"{group_id}:{artifact_id}:{version_name}"
        cached = await self.cache.get_cache(cache_key)
        if cached:
            return cached

        group_path = group_id.replace(".", "/")
        url = f"{self.CENTRAL_URL}/{group_path}/{artifact_id}/{version_name}/{artifact_id}-{version_name}.pom"
        session = await SessionManager.get_session()

        for _ in range(3):
            try:
                async with session.get(url) as resp:
                    pom_content = await resp.text()
                    response = {"pom": pom_content}
                    await self.cache.set_cache(cache_key, response)
                    return response
            except (ClientConnectorError, TimeoutError):
                await sleep(5)
            except (JSONDecodeError, ContentTypeError):
                return None
        return None

    async def extract_raw_versions(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        raw_versions = []
        response = metadata.get("response", {})
        docs = response.get("docs", [])

        for doc in docs:
            version = doc.get("v")
            timestamp = doc.get("timestamp")
            if version:
                raw_versions.append({"name": version, "release_date": timestamp})
        return raw_versions

    async def get_versions(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        if not metadata:
            return []
        raw = await self.extract_raw_versions(metadata)
        return await self.orderer.order_versions(raw)

    async def get_repo_url(self, metadata: dict[str, Any]) -> str | None:
        if not metadata:
            return None

        response = metadata.get("response", {})
        docs = response.get("docs", [])

        if docs:
            latest_doc = docs[0]
            group_id = latest_doc.get("g")
            artifact_id = latest_doc.get("a")
            version = latest_doc.get("v")

            if group_id and artifact_id and version:
                pom_data = await self.fetch_package_version_metadata(group_id, artifact_id, version)
                if pom_data and pom_data.get("pom"):
                    pom_content = pom_data["pom"]
                    if "<scm>" in pom_content and "<url>" in pom_content:
                        try:
                            scm_start = pom_content.find("<scm>")
                            scm_end = pom_content.find("</scm>", scm_start)
                            scm_section = pom_content[scm_start:scm_end]

                            url_start = scm_section.find("<url>") + 5
                            url_end = scm_section.find("</url>", url_start)
                            raw_url = scm_section[url_start:url_end].strip()

                            if raw_url:
                                norm_url = await self.repo_normalizer.normalize(raw_url)
                                if await self.repo_normalizer.check():
                                    return norm_url
                        except Exception:
                            pass

        return None

    async def get_package_requirements(self, metadata: dict[str, Any]) -> dict[str, Any]:
        requirements: dict[str, Any] = {}

        if not metadata or not metadata.get("pom"):
            return requirements

        pom_content = metadata["pom"]

        if "<dependencies>" in pom_content:
            try:
                deps_start = pom_content.find("<dependencies>")
                deps_end = pom_content.find("</dependencies>", deps_start)
                deps_section = pom_content[deps_start:deps_end]

                dependency_blocks = []
                start = 0
                while True:
                    dep_start = deps_section.find("<dependency>", start)
                    if dep_start == -1:
                        break
                    dep_end = deps_section.find("</dependency>", dep_start)
                    if dep_end == -1:
                        break
                    dependency_blocks.append(deps_section[dep_start:dep_end + 13])
                    start = dep_end + 13

                for dep_block in dependency_blocks:
                    try:
                        group_start = dep_block.find("<groupId>") + 9
                        group_end = dep_block.find("</groupId>", group_start)
                        dep_group = dep_block[group_start:group_end].strip()

                        artifact_start = dep_block.find("<artifactId>") + 12
                        artifact_end = dep_block.find("</artifactId>", artifact_start)
                        dep_artifact = dep_block[artifact_start:artifact_end].strip()

                        version_start = dep_block.find("<version>")
                        if version_start != -1:
                            version_start += 9
                            version_end = dep_block.find("</version>", version_start)
                            dep_version = dep_block[version_start:version_end].strip()
                        else:
                            dep_version = ""

                        if dep_group and dep_artifact:
                            requirements[f"{dep_group}:{dep_artifact}".lower()] = dep_version
                    except Exception:
                        pass
            except Exception:
                pass

        return requirements
