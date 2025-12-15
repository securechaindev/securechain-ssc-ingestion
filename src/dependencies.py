from __future__ import annotations

from typing import ClassVar

from src.cache import CacheManager
from src.database import DatabaseManager
from src.services import (
    CargoService,
    MavenService,
    NPMService,
    NuGetService,
    PackageService,
    PyPIService,
    RubyGemsService,
    VersionService,
    VulnerabilityService,
)
from src.session import SessionManager
from src.utils import (
    Attributor,
    Orderer,
    PyPIConstraintsParser,
    RedisQueue,
    RepoNormalizer,
)


class ServiceContainer:
    instance: ServiceContainer | None = None
    db_manager: DatabaseManager | None = None
    session_manager: SessionManager | None = None
    cargo_service: CargoService | None = None
    maven_service: MavenService | None = None
    npm_service: NPMService | None = None
    nuget_service: NuGetService | None = None
    pypi_service: PyPIService | None = None
    rubygems_service: RubyGemsService | None = None
    package_service: PackageService | None = None
    version_service: VersionService | None = None
    vulnerability_service: VulnerabilityService | None = None
    redis_queue: RedisQueue | None = None
    attributor: Attributor | None = None
    repo_normalizer: RepoNormalizer | None = None
    pypi_constraints_parser: PyPIConstraintsParser | None = None
    cache_managers: ClassVar[dict[str, CacheManager]] = {}
    orderers: ClassVar[dict[str, Orderer]] = {}

    def __new__(cls) -> ServiceContainer:
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def get_db(self) -> DatabaseManager:
        if self.db_manager is None:
            self.db_manager = DatabaseManager()
        return self.db_manager

    def get_session_manager(self) -> SessionManager:
        if self.session_manager is None:
            self.session_manager = SessionManager()
        return self.session_manager

    def get_cache_manager(self, manager_name: str) -> CacheManager:
        if manager_name not in self.cache_managers:
            self.cache_managers[manager_name] = CacheManager(manager_name)
        return self.cache_managers[manager_name]

    def get_orderer(self, node_type: str) -> Orderer:
        if node_type not in self.orderers:
            self.orderers[node_type] = Orderer(node_type)
        return self.orderers[node_type]

    def get_repo_normalizer(self) -> RepoNormalizer:
        if self.repo_normalizer is None:
            self.repo_normalizer = RepoNormalizer()
        return self.repo_normalizer

    def get_pypi_constraints_parser(self) -> PyPIConstraintsParser:
        if self.pypi_constraints_parser is None:
            self.pypi_constraints_parser = PyPIConstraintsParser()
        return self.pypi_constraints_parser

    def get_attributor(self) -> Attributor:
        if self.attributor is None:
            self.attributor = Attributor(self.get_vulnerability_service())
        return self.attributor

    def get_cargo_service(self) -> CargoService:
        if self.cargo_service is None:
            self.cargo_service = CargoService()
        return self.cargo_service

    def get_maven_service(self) -> MavenService:
        if self.maven_service is None:
            self.maven_service = MavenService()
        return self.maven_service

    def get_npm_service(self) -> NPMService:
        if self.npm_service is None:
            self.npm_service = NPMService()
        return self.npm_service

    def get_nuget_service(self) -> NuGetService:
        if self.nuget_service is None:
            self.nuget_service = NuGetService()
        return self.nuget_service

    def get_pypi_service(self) -> PyPIService:
        if self.pypi_service is None:
            self.pypi_service = PyPIService()
        return self.pypi_service

    def get_rubygems_service(self) -> RubyGemsService:
        if self.rubygems_service is None:
            self.rubygems_service = RubyGemsService()
        return self.rubygems_service

    def get_package_service(self) -> PackageService:
        if self.package_service is None:
            self.package_service = PackageService(self.get_db())
        return self.package_service

    def get_version_service(self) -> VersionService:
        if self.version_service is None:
            self.version_service = VersionService(self.get_db())
        return self.version_service

    def get_vulnerability_service(self) -> VulnerabilityService:
        if self.vulnerability_service is None:
            self.vulnerability_service = VulnerabilityService(self.get_db())
        return self.vulnerability_service

    def get_redis_queue(self) -> RedisQueue:
        if self.redis_queue is None:
            self.redis_queue = RedisQueue.from_env()
        return self.redis_queue

def get_db() -> DatabaseManager:
    return ServiceContainer().get_db()


def get_cargo_service() -> CargoService:
    return ServiceContainer().get_cargo_service()


def get_maven_service() -> MavenService:
    return ServiceContainer().get_maven_service()


def get_session_manager() -> SessionManager:
    return ServiceContainer().get_session_manager()


def get_cache_manager(manager_name: str) -> CacheManager:
    return ServiceContainer().get_cache_manager(manager_name)


def get_orderer(node_type: str) -> Orderer:
    return ServiceContainer().get_orderer(node_type)


def get_repo_normalizer() -> RepoNormalizer:
    return ServiceContainer().get_repo_normalizer()


def get_pypi_constraints_parser() -> PyPIConstraintsParser:
    return ServiceContainer().get_pypi_constraints_parser()


def get_attributor() -> Attributor:
    return ServiceContainer().get_attributor()


def get_npm_service() -> NPMService:
    return ServiceContainer().get_npm_service()


def get_nuget_service() -> NuGetService:
    return ServiceContainer().get_nuget_service()


def get_pypi_service() -> PyPIService:
    return ServiceContainer().get_pypi_service()


def get_rubygems_service() -> RubyGemsService:
    return ServiceContainer().get_rubygems_service()


def get_package_service() -> PackageService:
    return ServiceContainer().get_package_service()


def get_version_service() -> VersionService:
    return ServiceContainer().get_version_service()


def get_vulnerability_service() -> VulnerabilityService:
    return ServiceContainer().get_vulnerability_service()


def get_redis_queue() -> RedisQueue:
    return ServiceContainer().get_redis_queue()
