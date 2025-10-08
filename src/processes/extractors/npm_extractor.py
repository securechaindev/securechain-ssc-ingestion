from datetime import datetime, timedelta
from typing import Any

from src.schemas import NPMPackageSchema
from src.services import NPMService, PackageService, VersionService
from src.utils import Attributor

from .base import PackageExtractor


class NPMPackageExtractor(PackageExtractor):
    def __init__(
        self,
        package: NPMPackageSchema,
        package_service: PackageService,
        version_service: VersionService,
        npm_service: NPMService,
        attributor: Attributor,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.package = package
        self.package_service = package_service
        self.version_service = version_service
        self.npm_service = npm_service
        self.attributor = attributor

    async def run(self) -> None:
        await self.create_package(
            self.package.name,
            self.constraints,
            self.parent_id,
            self.parent_version_name,
        )

    async def generate_packages(
        self,
        requirement: dict[str, str],
        parent_id: str,
        parent_version_name: str | None = None,
    ) -> None:
        known_packages = []
        for package_name, constraints in requirement.items():
            package_name = package_name.lower()
            package = await self.package_service.read_package_by_name("NPMPackage", package_name)
            if package:
                package["parent_id"] = parent_id
                package["parent_version_name"] = parent_version_name
                package["constraints"] = constraints
                if package.get("moment") < datetime.now() - timedelta(days=10):
                    await self.search_new_versions(package)
                known_packages.append(package)
            else:
                await self.create_package(
                    package_name, constraints, parent_id, parent_version_name
                )
        await self.package_service.relate_packages("NPMPackage", known_packages)

    async def create_package(
        self,
        package_name: str,
        constraints: str | None = None,
        parent_id: str | None = None,
        parent_version_name: str | None = None,
    ) -> None:
        metadata = await self.npm_service.fetch_package_metadata(package_name)
        versions = await self.npm_service.get_versions(metadata)
        repository_url = await self.npm_service.get_repo_url(metadata)

        if not versions:
            return

        attributed_versions = [
            await self.attributor.attribute_vulnerabilities(package_name, version) for version in versions
        ]

        vendor = package_name.split("/")[0] if "@" in package_name else "n/a"

        pkg = NPMPackageSchema(
            name=package_name,
            vendor=vendor,
            repository_url=repository_url or "n/a",
            moment=datetime.now(),
        )

        created_versions = await self.package_service.create_package_and_versions(
            "NPMPackage",
            pkg.to_dict(),
            attributed_versions,
            constraints,
            parent_id,
            parent_version_name,
        )

        for created_version in created_versions:
            await self.extract_packages(package_name, created_version)

    async def extract_packages(self, parent_package_name: str, version: dict[str, Any]) -> None:
        metadata = await self.npm_service.fetch_package_version_metadata(parent_package_name, version.get("name"))
        requirement = await self.npm_service.get_package_requirements(metadata)
        if requirement:
            await self.generate_packages(requirement, version.get("id"), parent_package_name)
