# AI Agent Context - SecureChain SSC Ingestion

> **Purpose**: This document provides complete context for AI agents (Claude, ChatGPT, etc.) working on this project.

## Document Guidelines

**⚠️ Maximum Length**: 500 lines - keep context strictly relevant  
**📋 Content Rules**:
- Focus on essential architecture, patterns, and frequently used information
- Remove redundant examples and verbose explanations
- Keep only critical code snippets and configurations
- Prioritize actionable information over documentation
- Update regularly to reflect current codebase state

## Project Overview

**Name**: SecureChain SSC Ingestion  
**Type**: Data pipeline / ETL system  
**Framework**: Dagster 1.11.13  
**Language**: Python 3.13  
**Purpose**: Ingest software package data from multiple ecosystems into SecureChain's knowledge graph

### What This Project Does

1. **Extracts** package metadata from 6 software registries (PyPI, NPM, Maven, Cargo, RubyGems, NuGet)
2. **Processes** and validates data using Pydantic schemas
3. **Extracts** import_names (importable modules/classes) from package files for dependency analysis
4. **Stores** package relationships in Neo4j (graph) and vulnerabilities in MongoDB
5. **Schedules** daily updates for each ecosystem at different times

## Architecture

### Technology Stack

**Core**: Dagster 1.11.13 + Python 3.13 + UV package manager  
**Orchestration**: Webserver (port 3000) + Daemon + PostgreSQL metadata  
**Storage**: Neo4j (graph) + MongoDB (vulnerabilities) + Redis (queue)  
**Assets**: 12 total (6 ingestion + 6 updates)

### Docker Services

1. **dagster-postgres** - Metadata storage (port 5432)
2. **redis** - Queue for async extraction (port 6379, AOF persistence)
3. **dagster-daemon** - Schedules processor
4. **dagster-webserver** - UI (port 3000)

**Network**: `securechain` (external, must exist)

## Project Structure

```
src/
├── dagster_app/         # Main entry (defs), assets/, schedules.py, resources/
├── processes/           # extractors/, updaters/ (Dagster-agnostic)
├── services/            # apis/, dbs/, graph/, vulnerability/
├── schemas/             # Pydantic models
├── utils/               # Helpers
└── settings.py          # Config loader
dagster_home/            # dagster.yaml, workspace.yaml
docker-compose.yml       # 4 services
Dockerfile               # Multi-stage UV build
pyproject.toml           # Dependencies + config
```

## Key Files

- `src/dagster_app/__init__.py` - Exports `defs` (Definitions with assets, schedules, resources)
- `dagster_home/dagster.yaml` - PostgreSQL storage, launchers, coordinators
- `dagster_home/workspace.yaml` - Module loading: `src.dagster_app`

## Assets (Data Products)

**12 assets total: 6 ingestion assets + 6 update assets (one per package ecosystem):**

### Ingestion Assets (Weekly, STOPPED)
**PyPI** (500k), **NPM** (3M), **Maven** (500k-1M) - Process new packages only

### Update Assets (Daily, RUNNING)
**PyPI** 10AM, **NPM** 12PM, **Maven** 2PM, **Cargo** 4PM, **RubyGems** 6PM, **NuGet** 8PM

### Asset Pattern

**Ingestion**: Fetch all → Check exists → Extract new → Return metrics  
**Updates**: Batch read → Update versions → Return metrics  
**Metrics**: total, new/processed, skipped, errors, rate

## Registry Implementation

| Registry | Method | Volume | Key Details |
|----------|--------|--------|-------------|
| PyPI | HTML parse | 500k | Simple index |
| NPM | Changes feed | 3M | Batch 10k, pagination |
| Maven | Docker+Lucene | 1M | 80min, ephemeral container |
| NuGet | Catalog API | 400k | Parallel pages |
| Cargo | Paginated API | 150k | 100/page |
| RubyGems | Single request | 180k | Plain text |

## Redis Queue Processor

**Asset**: `redis_queue_processor` (every 5min, RUNNING)  
**Purpose**: Async package extraction from Redis stream  
**Process**: Read batch (100) → Validate → Route to extractor → ACK/DLQ  
**Message**: `{node_type, package, vendor?, repository_url?, constraints?, ...}`  
**Config**: Stream `package_extraction`, group `extractors`, consumer `package-consumer`

## Resources

10 ConfigurableResource classes in `src/dagster_app/resources/__init__.py`:  
6 API services (PyPI, NPM, Maven, Cargo, RubyGems, NuGet)  
3 DB services (PackageService, VersionService, VulnerabilityService)  
1 AttributorResource (dependency attribution)



## Import Names Extraction

**Purpose**: Extract importable modules/classes from packages for dependency analysis  
**Cache**: 7 days TTL  
**Storage**: Neo4j `import_names` property  

| Ecosystem | Strategy | Format |
|-----------|----------|--------|
| Cargo | Parse `.rs` for `pub` items | `crate::module::Type` |
| Maven | Extract `.class` packages | `com.company.package` |
| NPM | Map `.js/.ts` to modules | `package/lib/module` |
| RubyGems | Parse `lib/*.rb` | `gem::module` |
| NuGet | Extract `.dll` namespaces | `Namespace.Sub` |
| PyPI | Parse `.py` in wheel/sdist | `package.module` |

**Pattern**: Download → Extract → Parse (thread pool) → Cache → Store

## Environment Variables (.env)

```bash
# Neo4j
GRAPH_DB_URI='bolt://neo4j:7687'
GRAPH_DB_USER='neo4j'
GRAPH_DB_PASSWORD='password'

# MongoDB
VULN_DB_URI='mongodb://user:pass@mongo:27017/admin'
VULN_DB_USER='mongoSecureChain'
VULN_DB_PASSWORD='password'

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_STREAM=package_extraction
REDIS_GROUP=extractors

# Dagster PostgreSQL
POSTGRES_USER=dagster
POSTGRES_PASSWORD=password
POSTGRES_DB=dagster
POSTGRES_HOST=dagster-postgres

# Dagster
DAGSTER_HOME=/opt/dagster/dagster_home
PYTHONPATH=/opt/dagster/app
```

## Quick Commands

```bash
# UV (local dev)
uv sync                              # Install dependencies
uv run dagster dev -m src.dagster_app  # Run Dagster

# Docker (production)
docker compose up -d                 # Start services
docker compose up -d --build         # Rebuild
docker compose logs -f dagster-webserver
docker compose down                  # Stop (keep data)
docker compose down -v               # Stop (remove data)

# Dagster commands
dagster asset materialize -m src.dagster_app -a pypi_packages
dagster asset list -m src.dagster_app
dagster schedule list -m src.dagster_app

# UI: http://localhost:3000
```

## Development Guidelines

### When Modifying

**Assets**: Keep clean, delegate to `processes/`, return `Output` with metadata  
**Resources**: Extend `ConfigurableResource`, stateless  
**Business Logic**: Keep in `processes/`/`services/`, Dagster-agnostic  
**Schemas**: Pydantic BaseModel with validators

### Adding New Ecosystem

1. API service in `services/apis/` (implement `fetch_all_package_names()`, `extract_import_names()`)
2. Schema in `schemas/` (Pydantic, include `import_names: list[str]`)
3. Extractor in `processes/extractors/` (extend `PackageExtractor`)
4. Updater in `processes/updaters/`
5. Assets in `dagster_app/assets/` (ingestion + update)
6. Resource in `dagster_app/resources/__init__.py`
7. Schedules in `dagster_app/schedules.py` (weekly STOPPED + daily RUNNING)
8. Import in `dagster_app/assets/__init__.py`
9. Register in `dagster_app/__init__.py`

## Troubleshooting

**Services won't start**: Check `-m src.dagster_app` in commands, verify `PYTHONPATH=/opt/dagster/app`  
**Assets not loading**: Verify import chain: asset file → `assets/__init__.py` → `__init__.py` defs  
**DB connection errors**: Check `docker network inspect securechain`, verify .env URIs  
**Port 3000 in use**: Change `ports: ["3001:3000"]` in docker-compose.yml

## Important Notes

- Always use `-m src.dagster_app` for Dagster commands
- Network `securechain` must exist before `docker compose up`
- `.env` is gitignored, use `template.env`
- Dagster 1.11.13, Python 3.13, UV package manager
- Volumes `/src` and `/dagster_home` mounted for hot-reload
- `pyproject.toml` is single source of truth, `uv.lock` for reproducibility

## Testing Setup

```bash
# Local
uv run python -c "from src.dagster_app import defs; print('OK')"
uv run dagster asset list -m src.dagster_app  # Should show 12

# Docker
docker compose exec dagster-webserver python -c "from src.dagster_app import defs; print('OK')"
docker compose exec dagster-webserver dagster asset list -m src.dagster_app
```

---

**Last Updated**: Nov 24, 2025 | Dagster 1.11.13 | Python 3.13 | UV Package Manager
