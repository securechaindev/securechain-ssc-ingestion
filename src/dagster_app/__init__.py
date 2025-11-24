from dagster import Definitions, load_assets_from_modules

from src.dagster_app import assets
from src.dagster_app.schedules import all_schedules

all_assets = load_assets_from_modules([assets])

defs = Definitions(
    assets=all_assets,
    schedules=all_schedules,
)
