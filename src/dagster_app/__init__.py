from dagster import Definitions, load_assets_from_modules

from src.dagster_app import assets
from src.dagster_app.resources import (
    AttributorResource,
    CargoServiceResource,
    MavenServiceResource,
    NPMServiceResource,
    NuGetServiceResource,
    PackageServiceResource,
    PyPIServiceResource,
    RubyGemsServiceResource,
    VersionServiceResource,
    VulnerabilityServiceResource,
)
from src.dagster_app.schedules import all_schedules

all_assets = load_assets_from_modules([assets])

vuln_service = VulnerabilityServiceResource()

resources = {
    "pypi_service": PyPIServiceResource(),
    "npm_service": NPMServiceResource(),
    "maven_service": MavenServiceResource(),
    "cargo_service": CargoServiceResource(),
    "rubygems_service": RubyGemsServiceResource(),
    "nuget_service": NuGetServiceResource(),
    "package_service": PackageServiceResource(),
    "version_service": VersionServiceResource(),
    "vulnerability_service": vuln_service,
    "attributor": AttributorResource(vuln_service=vuln_service),
}

defs = Definitions(
    assets=all_assets,
    schedules=all_schedules,
    resources=resources,
)
