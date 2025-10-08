from typing import Any

from src.services.dbs import get_graph_db_driver


class VersionService:
    def __init__(self):
        self._driver = get_graph_db_driver()

    async def create_versions(
        self,
        node_type: str,
        package_name: str,
        versions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        query = f"""
        MATCH(p:{node_type}{{name:$package_name}})
        WITH p AS package
        UNWIND $versions AS version
        CREATE(v:Version{{
            name: version.name,
            serial_number: version.serial_number,
            mean: version.mean,
            weighted_mean: version.weighted_mean,
            vulnerabilities: version.vulnerabilities,
            release_date: version.release_date
        }})
        CREATE (package)-[:HAVE]->(v)
        RETURN collect({{name: v.name, id: elementid(v)}}) AS versions
        """
        async with self._driver.session() as session:
            result = await session.run(
                query,
                package_name=package_name,
                versions=versions,
            )
            record = await result.single()
        return record["versions"] if record else []

    async def read_versions_names_by_package(self, node_type: str, package_name: str) -> list[str]:
        query = f"""
        MATCH (p:{node_type}{{name:$package_name}})
        MATCH (p)-[:HAVE]->(v)
        RETURN collect(v.name) AS version_names
        """
        async with self._driver.session() as session:
            result = await session.run(query, package_name=package_name)
            record = await result.single()
        return record["version_names"] if record else None

    async def update_versions_serial_number(
        self,
        node_type: str,
        package_name: str,
        versions: list[dict[str, Any]],
    ) -> None:
        query = f"""
        MATCH (p:{node_type}{{name: $package_name}})-[:HAVE]->(v)
        WITH v, $versions AS input_versions
        UNWIND input_versions AS version
        WITH v, version
        WHERE v.name = version.name
        SET v.serial_number = version.serial_number
        """
        async with self._driver.session() as session:
            await session.run(
                query,
                package_name=package_name,
                versions=versions,
            )

    async def count_number_of_versions_by_package(self, node_type: str, package_name: str) -> int:
        query = f"""
        MATCH (p:{node_type}{{name:$package_name}})
        MATCH (p)-[r:HAVE]->(v: Version)
        RETURN count(v) AS version_count
        """
        async with self._driver.session() as session:
            result = await session.run(query, package_name=package_name)
            record = await result.single()
        return record["version_count"] if record else 0
