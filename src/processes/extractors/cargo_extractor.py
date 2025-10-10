from datetime import datetime
from typing import Any

from src.schemas import CargoPackageSchema
from src.services import CargoService, PackageService, VersionService
from src.utils import Attributor

from .base import PackageExtractor


class CargoPackageExtractor(PackageExtractor):
    def __init__(
        self,
        package: CargoPackageSchema,
        package_service: PackageService,
        version_service: VersionService,
        cargo_service: CargoService,
        attributor: Attributor,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.package = package
        self.package_service = package_service
        self.version_service = version_service
        self.cargo_service = cargo_service
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
            package = await self.package_service.read_package_by_name("CargoPackage", package_name)
            if package:
                package["parent_id"] = parent_id
                package["parent_version_name"] = parent_version_name
                package["constraints"] = constraints
                known_packages.append(package)
            else:
                await self.create_package(package_name, constraints, parent_id, parent_version_name)

        await self.package_service.relate_packages("CargoPackage", known_packages)

    async def create_package(
        self,
        package_name: str,
        constraints: str | None = None,
        parent_id: str | None = None,
        parent_version_name: str | None = None,
    ) -> None:
        metadata = await self.cargo_service.fetch_package_metadata(package_name)
        versions = await self.cargo_service.get_versions(metadata)
        repository_url = await self.cargo_service.get_repo_url(metadata)
        vendor = repository_url.split("/")[-2] if repository_url else None

        if not versions:
            return

        attributed_versions = [
            await self.attributor.attribute_vulnerabilities(package_name, version) for version in versions
        ]

        if not vendor:
            vendor = package_name.split("/")[0] if "/" in package_name else "n/a"

        import_names = []
        if versions:
            latest_version = versions[-1].get("name")
            if latest_version:
                import_names = await self.cargo_service.extract_import_names(package_name, latest_version)

        pkg = CargoPackageSchema(
            name=package_name,
            vendor=vendor or "n/a",
            repository_url=repository_url or "n/a",
            moment=datetime.now(),
            import_names=import_names,
        )

        created_versions = await self.package_service.create_package_and_versions(
            "CargoPackage",
            pkg.to_dict(),
            attributed_versions,
            constraints,
            parent_id,
            parent_version_name,
        )

        for created_version in created_versions:
            await self.extract_packages(package_name, created_version)

        await self.version_service.update_versions_serial_number("CargoPackage", package_name, versions)
        await self.package_service.update_package_moment("CargoPackage", package_name)

    async def extract_packages(self, parent_package_name: str, version: dict[str, Any]) -> None:
        metadata = await self.cargo_service.fetch_package_version_metadata(parent_package_name, version.get("name"))
        requirement = await self.cargo_service.get_package_requirements(metadata)
        if requirement:
            await self.generate_packages(requirement, version.get("id"), parent_package_name)
