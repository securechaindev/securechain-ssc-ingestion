from asyncio import run
from typing import Any

from dagster import AssetExecutionContext, MetadataValue, Output, asset

from src.dagster_app.resources import (
    AttributorResource,
    NuGetServiceResource,
    PackageServiceResource,
    VersionServiceResource,
)
from src.logger import logger
from src.processes.updaters import NuGetVersionUpdater


@asset(
    description="Updates NuGet (.NET) package versions in SecureChain graph",
    group_name="nuget",
    compute_kind="python",
)
def nuget_packages(
    context: AssetExecutionContext,
    nuget_service: NuGetServiceResource,
    package_service: PackageServiceResource,
    version_service: VersionServiceResource,
    attributor: AttributorResource,
) -> Output[dict[str, Any]]:
    try:
        logger.info("Starting NuGet package version update process")

        nuget_svc = nuget_service.get_service()
        package_svc = package_service.get_service()
        version_svc = version_service.get_service()
        attr = attributor.get_attributor()

        updater = NuGetVersionUpdater(nuget_svc, package_svc, version_svc, attr)

        async def _run():
            package_count = 0
            version_count = 0
            error_count = 0

            async for batch in package_svc.read_packages_in_batches("NuGetPackage", batch_size=100):
                for pkg in batch:
                    try:
                        await updater.update_package_versions(pkg)
                        package_count += 1

                        versions = await version_svc.count_number_of_versions_by_package(
                            "NuGetPackage", pkg['name']
                        )
                        version_count += versions

                        context.log.info(f"NuGet - Successfully updated {pkg['name']} (Total: {package_count})")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"NuGet - Error updating {pkg['name']}: {e}")

            logger.info(f"NuGet update process completed. Total packages: {package_count}")

            return {
                "packages_processed": package_count,
                "total_versions": version_count,
                "errors": error_count,
            }

        stats = run(_run())

        return Output(
            value=stats,
            metadata={
                "packages_processed": stats["packages_processed"],
                "total_versions": stats["total_versions"],
                "errors": stats["errors"],
                "success_rate": MetadataValue.float(
                    (stats["packages_processed"] / (stats["packages_processed"] + stats["errors"]) * 100)
                    if (stats["packages_processed"] + stats["errors"]) > 0 else 0
                ),
            }
        )

    except Exception as e:
        logger.error(f"NuGet - Fatal error in update process: {e}")
        raise
