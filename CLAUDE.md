# AI Agent Context - SecureChain SSC Ingestion

> **Purpose**: This document provides complete context for AI agents (Claude, ChatGPT, etc.) working on this project.

## Project Overview

**Name**: SecureChain SSC Ingestion  
**Type**: Data pipeline / ETL system  
**Framework**: Dagster 1.11.13  
**Language**: Python 3.12  
**Purpose**: Ingest software package data from multiple ecosystems into SecureChain's knowledge graph

### What This Project Does

1. **Extracts** package metadata from 6 software registries (PyPI, NPM, Maven, Cargo, RubyGems, NuGet)
2. **Processes** and validates data using Pydantic schemas
3. **Stores** package relationships in Neo4j (graph) and vulnerabilities in MongoDB
4. **Schedules** daily updates for each ecosystem at different times

## Architecture

### Technology Stack

```
┌─────────────────────────────────────────────────────┐
│  Dagster (Orchestration)                            │
│  ├── Webserver (UI) - Port 3000                    │
│  ├── Daemon (Schedules/Sensors)                    │
│  └── PostgreSQL (Metadata Storage)                 │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  Application Layer (Python 3.12)                    │
│  ├── Assets (6 package updaters)                   │
│  ├── Resources (API clients, DB connections)       │
│  ├── Processes (Extractors, Updaters)              │
│  └── Services (Neo4j, MongoDB, Registry APIs)      │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  Data Storage                                       │
│  ├── Neo4j (Package Graph)                         │
│  └── MongoDB (Vulnerability Data)                  │
└─────────────────────────────────────────────────────┘
```

### Docker Services

**3 services in docker-compose.yml:**

1. **dagster-postgres** (postgres:18)
   - Stores Dagster metadata (runs, events, schedules)
   - Port: 5432 (internal)
   - Health check enabled

2. **dagster-daemon**
   - Processes schedules and sensors
   - Command: `dagster-daemon run -m src.dagster_app`
   - No exposed ports

3. **dagster-webserver**
   - Web UI for monitoring and management
   - Command: `dagster-webserver -h 0.0.0.0 -p 3000 -m src.dagster_app`
   - Port: 3000 (exposed)

**External Network**: `securechain` (must exist, connects to Neo4j/MongoDB)

## Project Structure

```
securechain-ssc-ingestion/
├── src/
│   ├── dagster_app/              # Dagster application entry point
│   │   ├── __init__.py           # Definitions (main entry, exports `defs`)
│   │   ├── schedules.py          # 6 daily schedules (10AM-8PM, 2hr intervals)
│   │   ├── assets/               # Asset definitions (one per ecosystem)
│   │   │   ├── __init__.py       # Exports all assets
│   │   │   ├── pypi_assets.py
│   │   │   ├── npm_assets.py
│   │   │   ├── maven_assets.py
│   │   │   ├── cargo_assets.py
│   │   │   ├── rubygems_assets.py
│   │   │   └── nuget_assets.py
│   │   └── resources/            # ConfigurableResource definitions
│   │       └── __init__.py       # 10 resources (APIs, DB services, attributor)
│   ├── processes/                # Business logic (reusable, Dagster-agnostic)
│   │   ├── extractors/           # Package extractors
│   │   └── updaters/             # Version updaters
│   ├── services/                 # External service clients
│   │   ├── apis/                 # Registry API clients (PyPI, NPM, etc.)
│   │   ├── dbs/                  # Database services
│   │   ├── graph/                # Neo4j service
│   │   └── vulnerability/        # MongoDB service
│   ├── schemas/                  # Pydantic data models
│   ├── utils/                    # Helper functions
│   ├── logger.py                 # Custom logging
│   ├── session.py                # HTTP session management
│   ├── cache.py                  # Caching utilities
│   └── settings.py               # Configuration loader
├── dagster_home/                 # Dagster configuration
│   ├── dagster.yaml              # Storage, launcher, coordinator config
│   ├── workspace.yaml            # Module loading config
│   ├── storage/                  # Run data (gitignored)
│   ├── logs/                     # Compute logs (gitignored)
│   └── .telemetry/               # Telemetry data (gitignored)
├── docker-compose.yml            # Service orchestration
├── Dockerfile                    # Multi-stage build (builder + runtime)
├── requirements.txt              # Python dependencies
├── .env                          # Environment variables (gitignored)
├── template.env                  # Environment template
├── .gitignore                    # Git ignore rules
├── ruff.toml                     # Ruff linter config
├── README.md                     # User documentation
└── CLAUDE.md                     # This file

EXTERNAL (not in repo, must exist):
├── Neo4j                         # Graph database (securechain network)
└── MongoDB                       # Vulnerability database (securechain network)
```

## Key Files Explained

### src/dagster_app/__init__.py
**Critical file** - Main entry point that exports `defs`:
```python
from dagster import Definitions
from .assets import all_assets
from .schedules import all_schedules
from .resources import (
    pypi_service, npm_service, maven_service,
    cargo_service, rubygems_service, nuget_service,
    package_service, version_service,
    vulnerability_service, attributor
)

defs = Definitions(
    assets=all_assets,
    schedules=all_schedules,
    resources={
        "pypi_service": pypi_service,
        # ... other resources
    }
)
```

### dagster_home/dagster.yaml
Configures Dagster instance:
- **Storage**: PostgreSQL (metadata, events, runs)
- **Run Launcher**: DefaultRunLauncher
- **Run Coordinator**: QueuedRunCoordinator
- **Compute Logs**: LocalComputeLogManager
- **Artifact Storage**: LocalArtifactStorage

### dagster_home/workspace.yaml
```yaml
load_from:
  - python_module:
      module_name: src.dagster_app
      working_directory: /opt/dagster/app
```
Tells Dagster where to find the code.

## Assets (Data Products)

**6 assets, one per package ecosystem:**

| Asset Name | Registry | Schedule | Description |
|------------|----------|----------|-------------|
| `pypi_packages` | PyPI | Daily 10:00 AM | Python packages |
| `npm_packages` | NPM | Daily 12:00 PM | Node.js packages |
| `maven_packages` | Maven Central | Daily 2:00 PM | Java packages |
| `cargo_packages` | crates.io | Daily 4:00 PM | Rust packages |
| `rubygems_packages` | RubyGems | Daily 6:00 PM | Ruby packages |
| `nuget_packages` | NuGet | Daily 8:00 PM | .NET packages |

**Asset Structure** (example):
```python
@asset(
    description="Updates PyPI package versions",
    group_name="pypi"
)
def pypi_packages(
    pypi_service: PyPIServiceResource,
    package_service: PackageServiceResource,
    version_service: VersionServiceResource,
    vulnerability_service: VulnerabilityServiceResource,
    attributor: AttributorResource
) -> Output[dict]:
    # Business logic here
    updater = PyPIVersionUpdater(...)
    result = updater.update()
    return Output(result, metadata={...})
```

**Each asset returns metadata**:
- `packages_processed`: Number of packages updated
- `total_versions`: Total versions in system
- `errors`: Errors encountered
- `success_rate`: Percentage of successful updates

## Resources (Dependency Injection)

**10 ConfigurableResource classes** in `src/dagster_app/resources/__init__.py`:

1. **PyPIServiceResource** - PyPI API client
2. **NPMServiceResource** - NPM API client
3. **MavenServiceResource** - Maven Central API client
4. **CargoServiceResource** - crates.io API client
5. **RubyGemsServiceResource** - RubyGems API client
6. **NuGetServiceResource** - NuGet API client
7. **PackageServiceResource** - Neo4j package operations
8. **VersionServiceResource** - Neo4j version operations
9. **VulnerabilityServiceResource** - MongoDB vulnerability operations
10. **AttributorResource** - Dependency attribution logic

Resources are configured in `defs` and injected into assets.

## Environment Variables

**Required in .env:**

```bash
# Neo4j (Package Graph)
GRAPH_DB_URI='bolt://neo4j:7687'
GRAPH_DB_USER='neo4j'
GRAPH_DB_PASSWORD='your-password'

# MongoDB (Vulnerabilities)
VULN_DB_URI='mongodb://user:pass@mongo:27017/admin'
VULN_DB_USER='mongoSecureChain'
VULN_DB_PASSWORD='your-password'

# Dagster PostgreSQL
POSTGRES_USER=dagster
POSTGRES_PASSWORD=your-password
POSTGRES_DB=dagster
POSTGRES_HOST=dagster-postgres
POSTGRES_PORT=5432

# Dagster Configuration
DAGSTER_HOME=/opt/dagster/dagster_home

# Python
PYTHONPATH=/opt/dagster/app
```

## Common Operations

### Starting Services
```bash
docker compose up -d
```

### Viewing Logs
```bash
docker compose logs -f dagster-webserver
docker compose logs -f dagster-daemon
```

### Running Asset Manually
```bash
docker compose exec dagster-webserver \
  dagster asset materialize -m src.dagster_app -a pypi_packages
```

### Accessing UI
Open http://localhost:3000

### Rebuilding After Code Changes
```bash
docker compose up -d --build
```

### Stopping Services
```bash
docker compose down          # Keep data
docker compose down -v       # Remove data
```

## Development Guidelines

### When Modifying Code

1. **Assets** (`src/dagster_app/assets/*.py`):
   - Keep asset definitions clean
   - Delegate business logic to `src/processes/`
   - Return `Output` with metadata
   - Use type hints

2. **Resources** (`src/dagster_app/resources/__init__.py`):
   - Extend `ConfigurableResource`
   - Add type hints for all fields
   - Keep them stateless when possible

3. **Business Logic** (`src/processes/`, `src/services/`):
   - Keep Dagster-agnostic
   - Reusable across different contexts
   - Well-tested and documented

4. **Schemas** (`src/schemas/`):
   - Use Pydantic BaseModel
   - Add validators for data quality
   - Document expected formats

### When Adding New Package Ecosystem

1. Create API service in `src/services/apis/new_registry_service.py`
2. Create schema in `src/schemas/new_package_schema.py`
3. Create extractor in `src/processes/extractors/new_extractor.py`
4. Create updater in `src/processes/updaters/new_updater.py`
5. Create asset in `src/dagster_app/assets/new_assets.py`
6. Create resource in `src/dagster_app/resources/__init__.py`
7. Create schedule in `src/dagster_app/schedules.py`
8. Import asset in `src/dagster_app/assets/__init__.py`
9. Register resource and schedule in `src/dagster_app/__init__.py`

## Troubleshooting

### Services Won't Start

**Problem**: Daemon/webserver in "Restarting" state  
**Solution**: Check that commands include `-m src.dagster_app`

**Problem**: "No module named 'src'"  
**Solution**: Verify `PYTHONPATH=/opt/dagster/app` in .env

### Asset Import Errors

**Problem**: Assets not loading  
**Solution**: Verify import chain:
1. Asset defined in `src/dagster_app/assets/{ecosystem}_assets.py`
2. Exported in `src/dagster_app/assets/__init__.py`
3. Imported in `src/dagster_app/__init__.py` and added to `defs`

### Database Connection Errors

**Problem**: Can't connect to Neo4j/MongoDB  
**Solution**: 
1. Verify network: `docker network inspect securechain`
2. Check services are running
3. Verify .env URIs match actual service names

### Port 3000 Already in Use

**Solution**: Change port in docker-compose.yml:
```yaml
ports:
  - "3001:3000"  # Host:Container
```

## Important Notes for AI Agents

1. **Module Path**: Always use `-m src.dagster_app` when running Dagster commands
2. **Network**: `securechain` network is external (must exist before docker compose up)
3. **Dockerfile**: Multi-stage build (builder + runtime) for smaller image
4. **Git**: `.env` is gitignored, use `template.env` as reference
5. **Dagster Version**: Currently 1.11.13 (check requirements.txt)
6. **Python Version**: 3.12 (specified in Dockerfile)
7. **Volumes**: `/src` and `/dagster_home` are mounted for hot-reload during development

## Migration History

**Previous**: Apache Airflow 3.1.0 (5 services, complex Task API, 48+ env vars)  
**Current**: Dagster 1.11.13 (3 services, simple setup, 16 env vars)  
**Reason**: Simpler architecture, better DX, native Pydantic support, asset-centric approach

All business logic from Airflow DAGs was preserved and refactored into Dagster assets.

## Testing

To test the setup:
```bash
# 1. Verify Python imports work
docker compose exec dagster-webserver \
  python -c "from src.dagster_app import defs; print('OK')"

# 2. List assets
docker compose exec dagster-webserver \
  dagster asset list -m src.dagster_app

# 3. Check schedules
docker compose exec dagster-webserver \
  dagster schedule list -m src.dagster_app
```

## Links

- **Dagster Docs**: https://docs.dagster.io/
- **Dagster Assets**: https://docs.dagster.io/concepts/assets
- **Dagster Resources**: https://docs.dagster.io/concepts/resources
- **Dagster Schedules**: https://docs.dagster.io/concepts/automation/schedules

---

**Last Updated**: October 8, 2025  
**Dagster Version**: 1.11.13  
**Python Version**: 3.12
