from dagster import ConfigurableResource

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
from src.utils import Attributor


class PyPIServiceResource(ConfigurableResource):
    def get_service(self) -> PyPIService:
        return PyPIService()


class NPMServiceResource(ConfigurableResource):
    def get_service(self) -> NPMService:
        return NPMService()


class MavenServiceResource(ConfigurableResource):
    def get_service(self) -> MavenService:
        return MavenService()


class CargoServiceResource(ConfigurableResource):
    def get_service(self) -> CargoService:
        return CargoService()


class RubyGemsServiceResource(ConfigurableResource):
    def get_service(self) -> RubyGemsService:
        return RubyGemsService()


class NuGetServiceResource(ConfigurableResource):
    def get_service(self) -> NuGetService:
        return NuGetService()


class PackageServiceResource(ConfigurableResource):
    def get_service(self) -> PackageService:
        return PackageService()


class VersionServiceResource(ConfigurableResource):
    def get_service(self) -> VersionService:
        return VersionService()


class VulnerabilityServiceResource(ConfigurableResource):
    def get_service(self) -> VulnerabilityService:
        return VulnerabilityService()


class AttributorResource(ConfigurableResource):
    vuln_service: VulnerabilityServiceResource

    def get_attributor(self) -> Attributor:
        return Attributor(self.vuln_service.get_service())
