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

**4 services in docker-compose.yml:**

1. **dagster-postgres** (postgres:18)
   - Stores Dagster metadata (runs, events, schedules)
   - Port: 5432 (internal)
   - Volume: `dagster_postgres_data`
   - Health check enabled

2. **redis** (redis:7-alpine)
   - Message queue for asynchronous package extraction
   - Port: 6379 (exposed)
   - Volume: `redis_data`
   - Command: `redis-server --appendonly yes` (AOF persistence)
   - Health check enabled

3. **dagster-daemon**
   - Processes schedules and sensors
   - Command: `dagster-daemon run -m src.dagster_app`
   - Depends on: postgres, redis
   - No exposed ports

4. **dagster-webserver**
   - Web UI for monitoring and management
   - Command: `dagster-webserver -h 0.0.0.0 -p 3000 -m src.dagster_app`
   - Port: 3000 (exposed)
   - Depends on: postgres, redis, daemon

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
│   │   │   ├── nuget_assets.py
│   │   │   └── redis_queue_assets.py
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

**12 assets total: 6 ingestion assets + 6 update assets (one per package ecosystem):**

### Ingestion Assets (Weekly - Sundays)
Process new packages that don't exist in the graph. State: **STOPPED** (manual activation required).

| Asset Name | Registry | Schedule | Time | Description |
|------------|----------|----------|------|-------------|
| `pypi_package_ingestion` | PyPI | Weekly | 2:00 AM | Ingests new Python packages (~500k packages) |
| `npm_package_ingestion` | NPM | Weekly | 3:00 AM | Ingests new Node.js packages (~3M packages) |
| `maven_package_ingestion` | Maven Central | Weekly | 4:00 AM | Ingests new Java packages (~500k-1M unique) |

### Update Assets (Daily)
Update existing packages with new versions. State: **RUNNING** (active by default).

| Asset Name | Registry | Schedule | Time | Description |
|------------|----------|----------|------|-------------|
| `pypi_packages_updates` | PyPI | Daily | 10:00 AM | Updates Python package versions |
| `npm_packages_updates` | NPM | Daily | 12:00 PM | Updates Node.js package versions |
| `maven_packages` | Maven Central | Daily | 2:00 PM | Updates Java package versions |
| `cargo_packages` | crates.io | Daily | 4:00 PM | Updates Rust package versions |
| `rubygems_packages` | RubyGems | Daily | 6:00 PM | Updates Ruby package versions |
| `nuget_packages` | NuGet | Daily | 8:00 PM | Updates .NET package versions |

### Ingestion Asset Architecture

**Purpose**: Discover and extract ALL packages from registries, adding only those that don't exist in the graph.

**Process Flow**:
```
Registry API → Fetch All Package Names → Check Graph → Extract if New → Store
     ↓                ↓                        ↓              ↓           ↓
  PyPI/NPM/      List of all           read_package    Extractor    Neo4j
   Maven         package names          _by_name()      .run()      Graph
  (~500k-3M)                              
```

**Key Features**:
- **Incremental**: Only processes packages not in graph
- **Efficient**: Uses caching (1 hour TTL) and set-based deduplication
- **Observable**: Logs every 100 new packages, every 1000 skipped
- **Resilient**: Continues on errors, reports statistics
- **Resource-aware**: STOPPED by default due to intensive nature

**Ingestion Asset Structure** (example - PyPI):
```python
@asset(
    description="Ingests new PyPI packages from the Python Package Index",
    group_name="pypi",
    compute_kind="python",
)
def pypi_package_ingestion(
    context: AssetExecutionContext,
    pypi_service: PyPIServiceResource,
    package_service: PackageServiceResource,
    version_service: VersionServiceResource,
    attributor: AttributorResource,
) -> Output[dict[str, Any]]:
    # 1. Fetch all package names from registry
    all_package_names = await pypi_svc.fetch_all_package_names()
    
    # 2. Check each package
    for package_name in all_package_names:
        existing = await package_svc.read_package_by_name("PyPIPackage", package_name)
        
        if not existing:
            # 3. Create and run extractor for new packages
            extractor = PyPIPackageExtractor(...)
            await extractor.run()
    
    # 4. Return metrics
    return Output(value=stats, metadata={...})
```

**Ingestion Metrics**:
- `total_in_registry`: Total packages in the registry
- `new_packages_ingested`: New packages added to graph
- `skipped_existing`: Packages already in graph
- `errors`: Errors encountered
- `ingestion_rate`: Percentage of new packages

### Update Asset Structure

**Update Asset Structure** (example - PyPI):
```python
@asset(
    description="Updates PyPI package versions",
    group_name="pypi"
)
def pypi_packages_updates(
    pypi_service: PyPIServiceResource,
    package_service: PackageServiceResource,
    version_service: VersionServiceResource,
    attributor: AttributorResource
) -> Output[dict]:
    # Business logic here
    updater = PyPIVersionUpdater(...)
    result = updater.update()
    return Output(result, metadata={...})
```

**Update Metrics**:
- `packages_processed`: Number of packages updated
- `total_versions`: Total versions in system
- `errors`: Errors encountered
- `success_rate`: Percentage of successful updates

## Registry-Specific Implementation Details

### PyPI Ingestion
- **Endpoint**: `https://pypi.org/simple/`
- **Method**: HTML parsing with regex extraction
- **Volume**: ~500,000 packages
- **Deduplication**: Not needed (Simple index returns unique packages)
- **Cache Key**: `all_pypi_packages`

### NPM Ingestion
- **Endpoint**: `https://replicate.npmjs.com/_all_docs`
- **Method**: JSON document listing
- **Volume**: ~3,000,000 packages
- **Deduplication**: Filters `_design/` documents
- **Normalization**: Converts to lowercase
- **Cache Key**: `all_npm_packages`

### Maven Ingestion
- **Endpoint**: `https://search.maven.org/solrsearch/select?q=*:*`
- **Method**: Solr pagination (1000 per batch)
- **Volume**: ~10,000,000 artifacts → ~500,000-1,000,000 unique packages
- **Deduplication**: Uses `set` for O(1) lookup (group_id:artifact_id combinations)
- **Note**: Each version is a separate artifact, we extract unique group_id:artifact_id pairs
- **Optimization**: 
  - Set-based deduplication (O(1) vs O(n))
  - Progress logs every 10k artifacts
  - 0.1s delay between batches to avoid rate limiting
- **Cache Key**: `all_mvn_packages`

**Maven Deduplication Example**:
```python
seen_packages = set()  # O(1) lookup
for doc in docs:
    package_key = f"{group_id}:{artifact_id}"
    if package_key not in seen_packages:
        seen_packages.add(package_key)
        all_packages.append({...})
```

### NuGet Ingestion
- **Endpoint**: `https://azuresearch-usnc.nuget.org/query`
- **Method**: Search API with pagination (1000 per batch, skip-based)
- **Volume**: ~400,000 packages
- **Deduplication**: Not needed (Search API returns unique packages)
- **Rate Limiting**: 0.5s delay between requests
- **Special Features**:
  - Extracts vendor from `authors` field (first author)
  - Fetches version-specific metadata via catalog service
  - Supports version listing and requirements extraction
- **Cache Key**: `all_nuget_packages`

### Cargo Ingestion
- **Endpoint**: `https://crates.io/api/v1/crates`
- **Method**: Page-based pagination (100 crates per page)
- **Volume**: ~150,000 crates
- **Deduplication**: Not needed (API returns unique crates)
- **Rate Limiting**: Crates.io requires User-Agent header
- **Note**: Uses page parameter instead of skip/limit
- **Cache Key**: `all_cargo_packages`

### RubyGems Ingestion
- **Endpoint**: `https://rubygems.org/api/v1/gems.json`
- **Method**: Sequential page-based pagination
- **Volume**: ~180,000 gems
- **Deduplication**: Not needed (API returns unique gems)
- **Rate Limiting**: 0.2s delay between requests
- **Termination**: Continues until empty response
- **Cache Key**: `all_rubygems_packages`

## Redis Queue Processor Asset

The `redis_queue_processor` asset reads package extraction messages from Redis and processes them using the appropriate extractor based on `node_type`.

### Purpose

This asset enables **asynchronous package processing** by consuming messages from a Redis stream. Instead of directly calling extractors, other parts of the system can queue package extraction requests to Redis, and this asset will process them periodically.

### How It Works

1. **Reads messages** from Redis stream in batches (100 messages per run)
2. **Validates** each message using `PackageMessageSchema`
3. **Routes** to the appropriate extractor based on `node_type`:
   - `PyPIPackage` → `PyPIPackageExtractor`
   - `NPMPackage` → `NPMPackageExtractor`
   - `MavenPackage` → `MavenPackageExtractor`
   - `NuGetPackage` → `NuGetPackageExtractor`
   - `CargoPackage` → `CargoPackageExtractor`
   - `RubyGemsPackage` → `RubyGemsPackageExtractor`
4. **Acknowledges** successful processing or moves failed messages to dead-letter queue
5. **Reports** metrics: total_processed, successful, failed, validation_errors, unsupported_types

### Message Format

Messages must conform to `PackageMessageSchema`:

```python
{
    "node_type": "PyPIPackage",           # Required: Package manager type
    "package": "requests",                 # Required: Package name
    "vendor": "Kenneth Reitz",             # Optional: Package vendor
    "repository_url": "https://...",       # Optional: Repository URL
    "constraints": ">=2.0.0,<3.0.0",      # Optional: Version constraints
    "parent_id": "abc123",                 # Optional: Parent package ID
    "parent_version": "1.0.0",             # Optional: Parent version
    "refresh": false,                      # Optional: Force refresh
    "moment": "2025-10-09T10:00:00Z"      # Auto: Timestamp
}
```

### Error Handling

- **JSON Decode Errors**: Message moved to dead-letter queue (`package_extraction-dlq`)
- **Validation Errors**: Invalid schema, moved to DLQ
- **Unsupported Types**: Unknown `node_type`, moved to DLQ
- **Processing Errors**: Extractor failures, moved to DLQ with error details

### Schedule

- **Frequency**: Every 5 minutes (`*/5 * * * *`)
- **Status**: RUNNING by default
- **Batch Size**: 100 messages per run
- **Block Time**: 1 second (waits up to 1s for messages)

### Metrics

- `total_processed`: Total messages read from queue
- `successful`: Successfully processed messages
- `failed`: Failed processing (moved to DLQ)
- `validation_errors`: Messages with invalid schema
- `unsupported_types`: Messages with unknown node_type
- `success_rate`: Percentage of successful processing

### Use Cases

1. **Dependency Discovery**: When analyzing a package, queue its dependencies for extraction
2. **On-Demand Ingestion**: External systems can request package extraction via Redis
3. **Retry Mechanism**: Failed extractions can be re-queued for retry
4. **Load Distribution**: Distribute extraction work across multiple consumers

### Redis Configuration

Configured via `Settings` class (`src/settings.py`):

```python
REDIS_HOST=redis              # Redis service name in docker-compose
REDIS_PORT=6379               # Redis server port
REDIS_DB=0                    # Redis database number
REDIS_STREAM=package_extraction    # Stream name
REDIS_GROUP=extractors        # Consumer group name
REDIS_CONSUMER=package-consumer    # Consumer name (generic, not ecosystem-specific)
```

**Redis runs as a Docker service** with:
- Image: redis:7-alpine
- Persistence: AOF (Append Only File) enabled
- Volume: `redis_data` for data persistence
- Health checks enabled
- Accessible at `redis:6379` from other containers

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

## API Services Enhancement

### New Methods for Package Ingestion

**PyPI Service** (`src/services/apis/pypi_api.py`):
```python
async def fetch_all_package_names(self) -> list[str]:
    """Fetches all package names from PyPI Simple index"""
    # Returns ~500k package names
    # Uses HTML parsing + regex
    # Cache: 1 hour
```

**NPM Service** (`src/services/apis/npm_api.py`):
```python
async def fetch_all_package_names(self) -> list[str]:
    """Fetches all package names from NPM registry"""
    # Returns ~3M package names
    # Uses _all_docs endpoint
    # Cache: 1 hour

async def get_versions(self, metadata: dict) -> list[dict]:
    """Extract ordered versions from metadata"""

async def fetch_package_version_metadata(self, package_name: str, version: str) -> dict:
    """Fetch metadata for specific version"""

async def get_package_requirements(self, version_metadata: dict) -> dict[str, str]:
    """Get dependencies from version metadata"""
```

**Maven Service** (`src/services/apis/maven_api.py`):
```python
async def fetch_all_packages(self) -> list[dict[str, str]]:
    """
    Fetches all unique packages (group_id:artifact_id) from Maven Central.
    
    Key Points:
    - Maven has ~10M artifacts (each version counts)
    - Returns ~500k-1M unique packages
    - Uses set-based deduplication (O(1) lookup)
    - Batch size: 1000 per request
    - No artificial limit (processes all)
    - Progress logs every 10k artifacts
    - Cache: 1 hour
    
    Returns: [{"group_id": "...", "artifact_id": "...", "name": "..."}]
    """
```

**Performance Optimizations**:
- **Caching**: 1-hour TTL reduces repeated API calls
- **Set-based deduplication**: O(1) vs O(n) for Maven uniqueness
- **Batch processing**: 1000 items per request for optimal throughput
- **Rate limiting**: 0.1s delay between Maven requests
- **Progress logging**: Every 10k items for observability

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

# Redis Configuration (Queue Management)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_STREAM=package_extraction
REDIS_GROUP=extractors
REDIS_CONSUMER=package-consumer

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

**Note**: All environment variables are managed through the `Settings` class in `src/settings.py` using Pydantic Settings for validation and type safety.

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

1. **Create API service** in `src/services/apis/new_registry_service.py`
   - Implement `fetch_all_package_names()` or `fetch_all_packages()` for ingestion
   - Implement version fetching and metadata retrieval methods
   - Add caching with appropriate TTL

2. **Create schema** in `src/schemas/new_package_schema.py`
   - Use Pydantic BaseModel
   - Include all required fields (name, vendor, repository_url, etc.)

3. **Create extractor** in `src/processes/extractors/new_extractor.py`
   - Extend `PackageExtractor` base class
   - Implement package creation and dependency extraction

4. **Create updater** in `src/processes/updaters/new_updater.py`
   - Implement version update logic
   - Handle package metadata updates

5. **Create ingestion asset** in `src/dagster_app/assets/new_assets.py`
   - Create `new_package_ingestion` for initial bulk ingestion
   - Follow the pattern: fetch all → check existence → extract if new
   - Return ingestion metrics (total, new, skipped, errors)

6. **Create update asset** in `src/dagster_app/assets/new_assets.py`
   - Create `new_packages_updates` for daily version updates
   - Follow the pattern: batch read → update → report metrics

7. **Create resource** in `src/dagster_app/resources/__init__.py`
   - Extend `ConfigurableResource`
   - Create factory method to instantiate service

8. **Create schedules** in `src/dagster_app/schedules.py`
   - Create ingestion schedule (weekly, STOPPED by default)
   - Create update schedule (daily, RUNNING by default)
   - Space out timing to avoid conflicts

9. **Import assets** in `src/dagster_app/assets/__init__.py`
   - Import both ingestion and update assets
   - Add to `__all__` list

10. **Register in main module** in `src/dagster_app/__init__.py`
    - Add resource to resources dict
    - Schedules auto-discovered from `all_schedules`

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

**Last Updated**: October 9, 2025  
**Dagster Version**: 1.11.13  
**Python Version**: 3.12  
**New Features**: Package ingestion assets for PyPI, NPM, and Maven with optimized deduplication and caching
