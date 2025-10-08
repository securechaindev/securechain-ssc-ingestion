# SecureChain SSC Ingestion

Data pipeline for ingesting software packages from multiple ecosystems into SecureChain.

## Overview

This project extracts, processes, and ingests package data from six major software registries: PyPI (Python), NPM (Node.js), Maven (Java), Cargo (Rust), RubyGems (Ruby), and NuGet (.NET). The data is stored in Neo4j for dependency graph analysis and MongoDB for vulnerability information.

Built with Dagster for modern data orchestration, providing a clean asset-centric approach with automatic data lineage tracking and scheduling capabilities.

## Tech Stack

- **Dagster 1.11.13** - Modern data orchestrator
- **Python 3.12** - Runtime environment
- **Neo4j** - Graph database for package relationships
- **MongoDB** - Document database for vulnerability data
- **Docker** - Containerization platform
- **PostgreSQL** - Dagster metadata storage

## Quick Start

Get up and running in 3 steps:

```bash
# 1. Configure environment
cp template.env .env
nano .env  # Update passwords and connection strings

# 2. Start services
docker compose up -d

# 3. Access Dagster UI
# Open http://localhost:3000 in your browser
```

The Dagster UI will be available at http://localhost:3000 where you can monitor asset materializations, view logs, and manage schedules.

## Available Assets

Each asset represents a package ecosystem updater that runs on a daily schedule:

| Asset | Ecosystem | Schedule | Description |
|-------|-----------|----------|-------------|
| `pypi_packages` | Python | 10:00 AM | Updates Python packages from PyPI |
| `npm_packages` | Node.js | 12:00 PM | Updates JavaScript packages from NPM |
| `maven_packages` | Java | 2:00 PM | Updates Java packages from Maven Central |
| `cargo_packages` | Rust | 4:00 PM | Updates Rust crates from crates.io |
| `rubygems_packages` | Ruby | 6:00 PM | Updates Ruby gems from RubyGems |
| `nuget_packages` | .NET | 8:00 PM | Updates .NET packages from NuGet |

All schedules run daily and can be enabled/disabled individually from the Dagster UI.

## Useful Commands

### Managing Services

```bash
# View all service status
docker compose ps

# View logs from all services
docker compose logs -f

# View logs from specific service
docker compose logs -f dagster-webserver

# Restart services
docker compose restart

# Stop services (keep data)
docker compose down

# Stop and remove all data
docker compose down -v
```

### Running Assets

```bash
# Materialize a specific asset
docker compose exec dagster-webserver dagster asset materialize -m src.dagster_app -a pypi_packages

# List all available assets
docker compose exec dagster-webserver dagster asset list -m src.dagster_app

# View schedule status
docker compose exec dagster-webserver dagster schedule list -m src.dagster_app
```

### Development

```bash
# Access webserver container
docker compose exec dagster-webserver bash

# Rebuild images after code changes
docker compose up -d --build
```

## Project Structure

```
securechain-ssc-ingestion/
├── dagster_home/           # Dagster configuration
│   ├── dagster.yaml       # Storage & compute config
│   └── workspace.yaml     # Module loading config
├── src/
│   ├── dagster_app/       # Dagster application
│   │   ├── assets/        # Asset definitions (6 updaters)
│   │   ├── resources/     # Configurable resources
│   │   └── schedules.py   # Daily schedules
│   ├── processes/         # Business logic
│   ├── services/          # External API services
│   ├── schemas/           # Pydantic data models
│   └── utils/             # Helper functions
├── docker-compose.yml     # Service orchestration
├── Dockerfile             # Multi-stage container image
├── requirements.txt       # Python dependencies
└── .env                   # Environment configuration
```

## Configuration

Copy `template.env` to `.env` and configure:

- **Neo4j**: Update `GRAPH_DB_URI` and `GRAPH_DB_PASSWORD`
- **MongoDB**: Update `VULN_DB_URI` and `VULN_DB_PASSWORD`
- **PostgreSQL**: Update `POSTGRES_PASSWORD` for Dagster metadata

## License

See LICENSE file for details.
