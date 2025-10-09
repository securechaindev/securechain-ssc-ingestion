from dagster import DefaultScheduleStatus, ScheduleDefinition

from src.dagster_app.assets import (
    cargo_packages,
    maven_packages,
    npm_packages,
    nuget_packages,
    pypi_package_ingestion,
    pypi_packages_updates,
    rubygems_packages,
)

pypi_ingestion_schedule = ScheduleDefinition(
    name="pypi_weekly_ingestion",
    target=pypi_package_ingestion,
    cron_schedule="0 2 * * 0",
    default_status=DefaultScheduleStatus.STOPPED,
    description="Ingests new PyPI packages weekly on Sundays at 2:00 AM",
)

pypi_schedule = ScheduleDefinition(
    name="pypi_daily_update",
    target=pypi_packages_updates,
    cron_schedule="0 10 * * *",
    default_status=DefaultScheduleStatus.RUNNING,
    description="Updates PyPI packages daily at 10:00 AM",
)

npm_schedule = ScheduleDefinition(
    name="npm_daily_update",
    target=npm_packages,
    cron_schedule="0 12 * * *",
    default_status=DefaultScheduleStatus.RUNNING,
    description="Updates NPM packages daily at 12:00 PM",
)

maven_schedule = ScheduleDefinition(
    name="maven_daily_update",
    target=maven_packages,
    cron_schedule="0 14 * * *",
    default_status=DefaultScheduleStatus.RUNNING,
    description="Updates Maven packages daily at 2:00 PM",
)

cargo_schedule = ScheduleDefinition(
    name="cargo_daily_update",
    target=cargo_packages,
    cron_schedule="0 16 * * *",
    default_status=DefaultScheduleStatus.RUNNING,
    description="Updates Cargo packages daily at 4:00 PM",
)

rubygems_schedule = ScheduleDefinition(
    name="rubygems_daily_update",
    target=rubygems_packages,
    cron_schedule="0 18 * * *",
    default_status=DefaultScheduleStatus.RUNNING,
    description="Updates RubyGems packages daily at 6:00 PM",
)

nuget_schedule = ScheduleDefinition(
    name="nuget_daily_update",
    target=nuget_packages,
    cron_schedule="0 20 * * *",
    default_status=DefaultScheduleStatus.RUNNING,
    description="Updates NuGet packages daily at 8:00 PM",
)

all_schedules = [
    pypi_ingestion_schedule,
    pypi_schedule,
    npm_schedule,
    maven_schedule,
    cargo_schedule,
    rubygems_schedule,
    nuget_schedule,
]
