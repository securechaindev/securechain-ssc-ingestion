# SecureChain SSC Ingestion

Data pipeline for ingesting and updating software packages from multiple ecosystems into SecureChain.

## Overview

This project extracts, processes, and ingests package data from six major software registries: PyPI (Python), NPM (Node.js), Maven (Java), Cargo (Rust), RubyGems (Ruby), and NuGet (.NET). The data is stored in Neo4j for dependency graph analysis and MongoDB for vulnerability information.

Built with **Dagster 1.11.13** for modern data orchestration, providing a clean asset-centric approach with automatic data lineage tracking, scheduling capabilities, and comprehensive monitoring.

## Key Features

- 🔄 **Dual Operation Modes**:
  - **Ingestion**: One-time bulk import of all packages from registries (~5M total packages)
  - **Updates**: Daily incremental updates for existing packages

- 📊 **6 Package Ecosystems**: PyPI, NPM, Maven, NuGet, Cargo, RubyGems
- 🗄️ **Graph Storage**: Neo4j for package relationships and dependency graphs
- 🔐 **Vulnerability Tracking**: MongoDB for security advisories
- ⚡ **Performance Optimized**: Set-based deduplication, caching (1hr TTL), batch processing
- 📅 **Smart Scheduling**: Staggered execution times to avoid resource conflicts
- 📈 **Rich Metrics**: Ingestion rates, error tracking, success rates per ecosystem

## Tech Stack

- **Dagster 1.11.13** - Modern data orchestrator with web UI
- **Python 3.12** - Runtime environment
- **Neo4j** - Graph database for package relationships
- **MongoDB** - Document database for vulnerability data
- **Redis** - Queue management for package extraction
- **PostgreSQL** - Dagster metadata storage
- **Docker** - Containerization platform

## Before Start

First, create a Docker network for containers:

```bash
docker network create securechain
```

Then, download the zipped [data dumps](https://doi.org/10.5281/zenodo.17131401) from Zenodo for graphs and vulnerabilities information. Once you have unzipped the dumps, run:

```bash
docker compose up -d
```

The containerized databases will be seeded automatically.

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

### Ingestion Assets (Weekly - STOPPED by default)

One-time bulk ingestion of all packages from registries. Run these manually when you need to populate the graph with new ecosystems or rebuild from scratch.

| Asset | Ecosystem | Schedule | Volume | Description |
|-------|-----------|----------|--------|-------------|
| `pypi_package_ingestion` | Python | Sun 2:00 AM | ~500k | Ingests all PyPI packages |
| `npm_package_ingestion` | Node.js | Sun 3:00 AM | ~3M | Ingests all NPM packages |
| `maven_package_ingestion` | Java | Sun 4:00 AM | ~500k-1M | Ingests unique Maven artifacts |
| `nuget_package_ingestion` | .NET | Sun 5:00 AM | ~400k | Ingests all NuGet packages |
| `cargo_package_ingestion` | Rust | Sun 6:00 AM | ~150k | Ingests all Cargo crates |
| `rubygems_package_ingestion` | Ruby | Sun 7:00 AM | ~180k | Ingests all RubyGems |

**Total Packages**: ~5.73 million packages across all ecosystems

### Update Assets (Daily - RUNNING by default)

Daily incremental updates for existing packages in the graph. These run automatically to keep package versions current.

| Asset | Ecosystem | Schedule | Description |
|-------|-----------|----------|-------------|
| `pypi_packages_updates` | Python | Daily 10:00 AM | Updates Python packages from PyPI |
| `npm_packages_updates` | Node.js | Daily 12:00 PM | Updates JavaScript packages from NPM |
| `maven_packages_updates` | Java | Daily 2:00 PM | Updates Java packages from Maven Central |
| `cargo_packages` | Rust | Daily 4:00 PM | Updates Rust crates from crates.io |
| `rubygems_packages` | Ruby | Daily 6:00 PM | Updates Ruby gems from RubyGems |
| `nuget_packages` | .NET | Daily 8:00 PM | Updates .NET packages from NuGet |

All schedules can be enabled/disabled individually from the Dagster UI (`Automation` tab).

## Architecture

### Data Flow

```
┌─────────────────┐
│ Package Registry│  (PyPI, NPM, Maven, NuGet, Cargo, RubyGems)
└────────┬────────┘
         │ HTTP API
         ↓
┌─────────────────┐
│  Dagster Asset  │  (Fetch all packages / Batch read existing)
└────────┬────────┘
         │
         ├─→ Ingestion: Check if exists in Neo4j → Extract if new
         │
         └─→ Update: Fetch latest versions → Update existing nodes
         │
         ↓
┌─────────────────┐
│ Redis Queue     │  (Package extraction messages)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Neo4j + MongoDB │  (Graph storage + Vulnerabilities)
└─────────────────┘
```

### Registry-Specific Implementation

Each ecosystem has unique characteristics handled by specialized API clients:

- **PyPI**: HTML parsing with regex (`/simple/` endpoint)
- **NPM**: JSON document listing (`/_all_docs` endpoint)  
- **Maven**: Solr pagination with set-based deduplication (10M artifacts → ~500k-1M packages)
- **NuGet**: Search API with skip-based pagination
- **Cargo**: Page-based pagination (100 per page)
- **RubyGems**: Sequential pagination with rate limiting

## Useful Commands

### Managing Services

```bash
# View all service status
docker compose ps

# View logs from all services
docker compose logs -f

# View logs from specific service
docker compose logs -f dagster-webserver
docker compose logs -f dagster-daemon

# Restart services
docker compose restart

# Stop services (keep data)
docker compose down

# Stop and remove all data
docker compose down -v
```

### Running Assets

```bash
# Materialize a specific update asset
docker compose exec dagster-webserver \
  dagster asset materialize -m src.dagster_app -a pypi_packages_updates

# Run a bulk ingestion asset (Warning: can take hours!)
docker compose exec dagster-webserver \
  dagster asset materialize -m src.dagster_app -a pypi_package_ingestion

# List all available assets
docker compose exec dagster-webserver \
  dagster asset list -m src.dagster_app

# View schedule status
docker compose exec dagster-webserver \
  dagster schedule list -m src.dagster_app
```

### Development

```bash
# Access webserver container
docker compose exec dagster-webserver bash

# Rebuild images after code changes
docker compose up -d --build

# Run Python shell in container
docker compose exec dagster-webserver python

# Test imports
docker compose exec dagster-webserver \
  python -c "from src.dagster_app import defs; print('OK')"
```

## Project Structure

```
securechain-ssc-ingestion/
├── dagster_home/           # Dagster configuration
│   ├── dagster.yaml       # Storage & compute config
│   ├── workspace.yaml     # Module loading config
│   └── storage/           # Run history and event logs
├── src/
│   ├── dagster_app/       # Dagster application
│   │   ├── __init__.py    # Main definitions (exports `defs`)
│   │   ├── assets/        # Asset definitions
│   │   │   ├── pypi_assets.py       # PyPI ingestion + updates
│   │   │   ├── npm_assets.py        # NPM ingestion + updates
│   │   │   ├── maven_assets.py      # Maven ingestion + updates
│   │   │   ├── nuget_assets.py      # NuGet ingestion + updates
│   │   │   ├── cargo_assets.py      # Cargo ingestion + updates
│   │   │   └── rubygems_assets.py   # RubyGems ingestion + updates
│   │   ├── resources/     # ConfigurableResource definitions
│   │   │   └── __init__.py          # 10 resources (APIs, DB services)
│   │   └── schedules.py   # 12 schedules (6 ingestion + 6 updates)
│   ├── processes/         # Business logic (Dagster-agnostic)
│   │   ├── extractors/    # Package extractors for each ecosystem
│   │   └── updaters/      # Version updaters for each ecosystem
│   ├── services/          # External service clients
│   │   ├── apis/          # Registry API clients (PyPI, NPM, etc.)
│   │   ├── dbs/           # Database service abstractions
│   │   ├── graph/         # Neo4j service (package storage)
│   │   └── vulnerability/ # MongoDB service (CVE data)
│   ├── schemas/           # Pydantic data models
│   │   ├── pypi_package_schema.py
│   │   ├── npm_package_schema.py
│   │   ├── maven_package_schema.py
│   │   ├── nuget_package_schema.py
│   │   ├── cargo_package_schema.py
│   │   └── rubygems_package_schema.py
│   ├── utils/             # Helper functions
│   │   ├── redis_queue.py          # Redis stream management
│   │   ├── repo_normalizer.py      # URL normalization
│   │   └── pypi_constraints_parser.py
│   ├── logger.py          # Custom logging configuration
│   ├── session.py         # HTTP session management
│   ├── cache.py           # Caching utilities (1hr TTL)
│   └── settings.py        # Pydantic Settings (env vars)
├── docker-compose.yml     # 3 services (postgres, daemon, webserver)
├── Dockerfile             # Multi-stage build (builder + runtime)
├── requirements.txt       # Python dependencies
├── template.env           # Environment variable template
├── .env                   # Local configuration (gitignored)
└── CLAUDE.md              # AI agent context documentation
```

## Configuration

### Environment Variables

Copy `template.env` to `.env` and configure the following sections:

#### Database Connections
```bash
# Neo4j (Graph database)
GRAPH_DB_URI='bolt://neo4j:7687'
GRAPH_DB_USER='neo4j'
GRAPH_DB_PASSWORD='your-secure-password'  # Change in production!

# MongoDB (Vulnerability database)
VULN_DB_URI='mongodb://user:pass@mongo:27017/admin'
VULN_DB_USER='mongoSecureChain'
VULN_DB_PASSWORD='your-secure-password'  # Change in production!
```

#### Redis Queue
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_STREAM=package_extraction
REDIS_GROUP=extractors
REDIS_CONSUMER=package-consumer
```

#### Dagster PostgreSQL
```bash
POSTGRES_USER=dagster
POSTGRES_PASSWORD=your-secure-password  # Change in production!
POSTGRES_DB=dagster
POSTGRES_HOST=dagster-postgres
POSTGRES_PORT=5432
```

#### Application Settings
```bash
DAGSTER_HOME=/opt/dagster/dagster_home
PYTHONPATH=/opt/dagster/app
```

All configuration is managed through the `Settings` class in `src/settings.py` using Pydantic Settings for validation and type safety.

## Performance Considerations

### Ingestion Assets
- **Duration**: Each ingestion can take several hours depending on registry size
- **Network**: Requires stable internet connection
- **Rate Limiting**: Built-in delays to respect API limits
- **Memory**: Maven deduplication uses set-based approach for efficiency
- **Caching**: 1-hour TTL on package listings to reduce API calls

### Update Assets
- **Duration**: Typically completes in minutes to hours
- **Batch Size**: Processes packages in configurable batches
- **Concurrency**: Async operations for improved throughput
- **Error Handling**: Individual package failures don't stop the entire run

## Monitoring

### Dagster UI (http://localhost:3000)

Access real-time monitoring and management:

- **Assets**: View materialization history, metadata, and dependencies
- **Runs**: Monitor active runs, view logs, inspect failures
- **Schedules**: Enable/disable schedules, view next execution times
- **Sensors**: (Future) Event-driven execution triggers
- **Dagit Logs**: Detailed execution traces with timestamps

### Metrics Tracked

Each asset reports comprehensive metrics:

**Ingestion Assets**:
- `total_in_registry`: Total packages found in registry
- `new_packages_ingested`: New packages added to graph
- `skipped_existing`: Packages already in graph
- `errors`: Failed ingestions
- `ingestion_rate`: Percentage of new packages

**Update Assets**:
- `packages_processed`: Total packages updated
- `total_versions`: New versions added
- `errors`: Failed updates
- `success_rate`: Percentage of successful updates

## Troubleshooting

### Common Issues

**Services won't start**
```bash
# Check logs
docker compose logs dagster-daemon
docker compose logs dagster-webserver

# Verify network exists
docker network inspect securechain

# Rebuild containers
docker compose up -d --build
```

**Assets not appearing in UI**
```bash
# Verify imports
docker compose exec dagster-webserver \
  python -c "from src.dagster_app import defs; print(len(defs.get_asset_graph().get_all_asset_keys()))"

# Should print 12 (6 ingestion + 6 update assets)
```

**Database connection errors**
```bash
# Check .env file matches docker-compose.yml service names
# For dockerized: use service names (neo4j, mongo, dagster-postgres)
# For local: use localhost
```

**Port 3000 already in use**
```yaml
# In docker-compose.yml, change port mapping:
ports:
  - "3001:3000"  # Access UI at http://localhost:3001
```

**Redis consumer group errors**
```bash
# If you changed REDIS_CONSUMER, recreate the group:
redis-cli XGROUP DESTROY package_extraction extractors
redis-cli XGROUP CREATE package_extraction extractors 0 MKSTREAM
```

## Development Workflow

### Making Changes

1. **Edit code** in `src/` directory
2. **Rebuild containers**: `docker compose up -d --build`
3. **Verify in UI**: Check assets appear at http://localhost:3000
4. **Test manually**: Materialize asset to verify behavior
5. **Monitor logs**: Watch for errors in webserver logs

### Adding New Package Ecosystem

See `CLAUDE.md` for detailed instructions on adding support for new package registries. Summary:

1. Create API service in `src/services/apis/`
2. Create schema in `src/schemas/`
3. Create extractor in `src/processes/extractors/`
4. Create updater in `src/processes/updaters/`
5. Create assets in `src/dagster_app/assets/`
6. Create resource in `src/dagster_app/resources/`
7. Add schedules in `src/dagster_app/schedules.py`
8. Update imports in `__init__.py` files

## Contributing

Contributions are welcome! Please ensure:

- Code follows existing patterns and structure
- Assets return proper `Output` with metadata
- Business logic stays in `src/processes/`, not in assets
- Type hints are used throughout
- Documentation is updated (README.md + CLAUDE.md)

## Additional Resources

- **CLAUDE.md**: Comprehensive AI agent context with detailed architecture and implementation notes
- **Dagster Documentation**: https://docs.dagster.io/
- **Project Repository**: https://github.com/securechaindev/securechain-ssc-ingestion
- **Data Dumps**: https://doi.org/10.5281/zenodo.17131401

## License

See LICENSE file for details.
