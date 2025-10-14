# AI Agent Context - SecureChain SSC Ingestion

> **Purpose**: This document provides complete context for AI agents (Claude, ChatGPT, etc.) working on this project.

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

```
┌─────────────────────────────────────────────────────┐
│  Dagster (Orchestration)                            │
│  ├── Webserver (UI) - Port 3000                    │
│  ├── Daemon (Schedules/Sensors)                    │
│  └── PostgreSQL (Metadata Storage)                 │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  Application Layer (Python 3.13)                    │
│  ├── Package Manager: UV (10-100x faster than pip) │
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
├── src/                          # Source code
│   ├── dagster_app/              # Dagster application entry point
│   │   ├── __init__.py           # Definitions (main entry, exports `defs`)
│   │   ├── schedules.py          # 13 schedules (6 ingestion + 6 updates + 1 queue)
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
├── docker-compose.yml            # Service orchestration (4 services)
├── Dockerfile                    # Multi-stage build with UV (builder + runtime)
├── pyproject.toml                # Project config (dependencies, tools, metadata)
├── uv.lock                       # Lockfile for reproducible installs (auto-generated)
├── .env                          # Environment variables (gitignored)
├── template.env                  # Environment template
├── .gitignore                    # Git ignore rules
├── .dockerignore                 # Docker build optimization
├── README.md                     # User documentation
└── CLAUDE.md                     # This file (AI agent context)

EXTERNAL (not in repo, must exist):
├── Neo4j                         # Graph database (securechain network)
└── MongoDB                       # Vulnerability database (securechain network)
```
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
- **Endpoint**: `https://replicate.npmjs.com/_changes`
- **Method**: Changes feed with batch pagination
- **Volume**: ~3,000,000 packages
- **Batch Size**: 10,000 packages per request
- **Deduplication**: Uses `set` for efficient lookups
- **Pagination**: `since` parameter for sequential batches
- **Optimization**:
  - Parallel processing with `asyncio.gather()`
  - Set-based deduplication (O(1) lookup)
  - Filters deleted packages (`deleted: true`)
  - Single request per batch (vs multiple requests)
- **Cache Key**: `all_npm_packages` (1 hour TTL)

**NPM Changes Feed Example**:
```python
# Request: GET /_changes?since=0&limit=10000
# Response: {
#   "results": [
#     {"id": "package-name", "changes": [...], "deleted": false},
#     ...
#   ],
#   "last_seq": "10000-xxx"
# }
# Next request: GET /_changes?since=10000-xxx&limit=10000
```

### Maven Ingestion
- **Method**: Docker-based Lucene index extraction
- **Volume**: ~500,000-1,000,000 unique packages (from ~10M artifacts)
- **Container**: Ephemeral Docker container (`coady/pylucene:9`)
- **Process**:
  1. Downloads Maven Central index (`nexus-maven-repository-index.gz`, ~400-500 MB)
  2. Expands Lucene index using `indexer-cli` tool (~10-15 minutes)
  3. Reads index with PyLucene to extract `groupId:artifactId` combinations
  4. Deduplicates using `set` (O(1) lookup)
  5. Returns JSON array via stdout
- **Duration**: 80-90 minutes per execution
- **Optimization**: 
  - Set-based deduplication (O(1) vs O(n))
  - Runs in isolated Docker container with `--rm` (auto-cleanup)
  - No volume mounting (all processing inside container)
  - Progress logs every 100k documents
- **Cache Key**: `all_mvn_packages` (1 hour TTL)
- **Files**:
  - `src/utils/maven/Dockerfile.maven` - PyLucene + Java 17 image
  - `src/utils/maven/automate_maven_extraction.py` - Extraction script

**Maven Container Architecture**:
```python
# In maven_api.py
async def fetch_all_package_names(self) -> list[str]:
    # Build Docker image from Dockerfile.maven
    # Run ephemeral container: docker run --rm maven-extractor
    # Capture JSON output from stdout
    # Parse and return package list
    
# Container runs automate_maven_extraction.py which:
# 1. Downloads indexer-cli.jar (if needed)
# 2. Downloads nexus-maven-repository-index.gz (always fresh)
# 3. Expands index to /nexus-index-expanded
# 4. Extracts packages using PyLucene
# 5. Prints JSON to stdout (for parent process)
# 6. Logs to stderr (for debugging)
# 7. Cleans up temporary files
```

**No Shared Volumes**:
- All files stay inside container
- Container auto-deleted after completion (`--rm`)
- No artifacts left on host system
- Fresh index downloaded on each run

### NuGet Ingestion
- **Endpoint**: `https://api.nuget.org/v3/catalog0/index.json`
- **Method**: Catalog-based extraction with parallel page processing
- **Volume**: ~400,000 packages
- **Process**:
  1. Fetches catalog index containing page URLs
  2. Processes all pages in parallel with `asyncio.gather()`
  3. Each page contains package entries with commit timestamps
  4. Extracts package IDs from each entry
- **Concurrency**: Semaphore(50) to limit concurrent requests
- **Optimization**:
  - Parallel page fetching reduces total time significantly
  - Set-based deduplication for package IDs
  - Lock protection for thread-safe set operations
- **Special Features**:
  - Extracts vendor from package metadata
  - Fetches version-specific metadata via catalog service
  - Supports version listing and requirements extraction
- **Cache Key**: `all_nuget_packages` (1 hour TTL)

**NuGet Catalog Structure**:
```python
# Catalog Index: { "items": [{"@id": "page_url"}, ...] }
# Each Page: { "items": [{"nuget:id": "PackageName"}, ...] }
# Parallel processing: asyncio.gather(*[fetch_page(url) for url in pages])
```

### Cargo Ingestion
- **Endpoint**: `https://crates.io/api/v1/crates`
- **Method**: Page-based pagination (100 crates per page)
- **Volume**: ~150,000 crates
- **Deduplication**: Not needed (API returns unique crates)
- **Rate Limiting**: Crates.io requires User-Agent header
- **Note**: Uses page parameter instead of skip/limit
- **Cache Key**: `all_cargo_packages`

### RubyGems Ingestion
- **Endpoint**: `https://index.rubygems.org/names`
- **Method**: Single HTTP request for complete gem list
- **Volume**: ~180,000 gems
- **Format**: Plain text file with one gem name per line
- **Optimization**: 
  - Single request fetches all gems (no pagination needed)
  - Simple text parsing (split by newline)
  - Fastest method among all registries
- **Deduplication**: Not needed (index contains unique gems)
- **Cache Key**: `all_rubygems_packages` (1 hour TTL)

**RubyGems Names Index Example**:
```text
# Single GET request returns:
gem-name-1
gem-name-2
gem-name-3
...
(~180k lines)
```

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

## Import Names Extraction System

All six package ecosystems automatically extract **import_names** - the list of modules, classes, namespaces, or functions that can be imported from each package. This enables advanced dependency analysis, usage pattern detection, and API surface discovery.

### Architecture

**Consistent Pattern Across All Ecosystems**:
1. Download package file (`.tar.gz`, `.jar`, `.whl`, `.gem`, `.nupkg`, `.tgz`)
2. Extract and parse source files (`.rs`, `.class`, `.py`, `.rb`, `.dll`, `.js`)
3. Identify importable elements using ecosystem-specific strategies
4. Cache results for 7 days (604,800 seconds)
5. Store in Neo4j as `import_names` property on package nodes

### Implementation by Ecosystem

#### 1. Cargo (Rust)

**Files**: `src/schemas/cargo_package_schema.py`, `src/services/apis/cargo_api.py`, `src/processes/extractors/cargo_extractor.py`

**Strategy**:
- Downloads `.tar.gz` from crates.io
- Extracts all `.rs` files from `src/` directory
- Uses regex to find public Rust elements:
  - `pub mod`, `pub struct`, `pub enum`, `pub trait`
  - `pub fn`, `pub const`, `pub static`
  - `pub macro_rules!`, `pub type`
- Excludes test files (`tests/`, `benches/`)
- Format: `crate_name::module::Type`

**Example Output**:
```python
["serde", "serde::Serialize", "serde::Deserialize", "serde::de", "serde::ser"]
```

**Service Method**:
```python
async def extract_import_names(crate_name: str, version: str) -> list[str]:
    # Downloads from https://crates.io/api/v1/crates/{crate}/{version}/download
    # Extracts .tar.gz → searches src/**/*.rs
    # Cache: "import_names:{crate}:{version}", TTL: 7 days
```

#### 2. Maven (Java)

**Files**: `src/schemas/maven_package_schema.py`, `src/services/apis/maven_api.py`, `src/processes/extractors/maven_extractor.py`

**Strategy**:
- Downloads `.jar` file from Maven Central
- Opens JAR as ZIP archive
- Extracts package paths from `.class` files
- Applies intelligent deduplication:
  - If `com.example` exists, excludes `com.example.subpackage`
  - Keeps only root-level packages
- Format: `com.company.package`

**Example Output**:
```python
["org.springframework.boot", "org.springframework.web", "org.springframework.context"]
```

**Service Method**:
```python
async def extract_import_names(group_id: str, artifact_id: str, version: str) -> list[str]:
    # Downloads from Maven Central repository
    # Extracts .jar → .class files → package paths
    # Deduplicates: keeps only unique root packages
    # Cache: "import_names:{group_id}:{artifact_id}:{version}", TTL: 7 days
```

#### 3. NPM (JavaScript/TypeScript)

**Files**: `src/schemas/npm_package_schema.py`, `src/services/apis/npm_api.py`, `src/processes/extractors/npm_extractor.py`

**Strategy**:
- Downloads `.tgz` from NPM registry
- Extracts `.js`, `.mjs`, `.ts` files from package
- Maps file paths to module paths
- Excludes:
  - Test files (`test/`, `tests/`, `__tests__/`)
  - Node modules (`node_modules/`)
  - Build artifacts (`dist/`, `build/`)
  - Internal files (starts with `_`)
- Format: `package/lib/module` or `package.module`

**Example Output**:
```python
["express", "express/lib/router", "express/lib/application", "express/lib/request"]
```

**Service Method**:
```python
async def extract_import_names(package_name: str, version: str) -> list[str]:
    # Downloads from https://registry.npmjs.org/{package}/-/{package}-{version}.tgz
    # Extracts .tgz → .js/.mjs/.ts files → module paths
    # Cache: "import_names:{package}:{version}", TTL: 7 days
```

#### 4. RubyGems (Ruby)

**Files**: `src/schemas/rubygems_package_schema.py`, `src/services/apis/rubygems_api.py`, `src/processes/extractors/rubygems_extractor.py`

**Strategy**:
- Downloads `.gem` file from rubygems.org
- Opens `.gem` as tarball → extracts `data.tar.gz` → extracts `lib/` directory
- Finds all `.rb` files in `lib/`
- Converts file paths to Ruby module format:
  - `lib/my_gem/utils.rb` → `my_gem::utils`
- Excludes test files (`*_spec.rb`, `*_test.rb`)
- Format: `GemName::Module::Class` (Ruby `::` separator)

**Example Output**:
```python
["rails", "rails::application", "rails::engine", "rails::railtie"]
```

**Service Method**:
```python
async def extract_import_names(gem_name: str, version: str) -> list[str]:
    # Downloads from https://rubygems.org/downloads/{gem}-{version}.gem
    # Extracts .gem → data.tar.gz → lib/**/*.rb
    # Cache: "import_names:{gem}:{version}", TTL: 7 days
```

#### 5. NuGet (.NET)

**Files**: `src/schemas/nuget_package_schema.py`, `src/services/apis/nuget_api.py`, `src/processes/extractors/nuget_extractor.py`

**Strategy**:
- Downloads `.nupkg` file from NuGet.org
- Opens `.nupkg` as ZIP archive
- Finds `.dll` files in `lib/` directories (e.g., `lib/net6.0/`, `lib/netstandard2.0/`)
- Extracts namespace from DLL filename
- Reads `.nuspec` file for additional metadata
- Filters system libraries (`System`, `Microsoft.CSharp`, `netstandard`)
- Fallback: uses package name if no DLLs found
- Format: `Namespace.Subnamespace`

**Example Output**:
```python
["Newtonsoft.Json", "Newtonsoft.Json.Linq", "Newtonsoft.Json.Schema"]
```

**Service Method**:
```python
async def extract_import_names(package_name: str, version: str) -> list[str]:
    # Downloads from https://www.nuget.org/api/v2/package/{package}/{version}
    # Extracts .nupkg (ZIP) → lib/**/*.dll + *.nuspec
    # Cache: "import_names:{package}:{version}", TTL: 7 days
```

#### 6. PyPI (Python)

**Files**: `src/schemas/pypi_package_schema.py`, `src/services/apis/pypi_api.py`, `src/processes/extractors/pypi_extractor.py`

**Strategy**:
- Downloads wheel (`.whl`) or source distribution (`.tar.gz`, `.zip`)
- Prefers wheel for faster extraction
- For wheel: extracts `.py` files from package directories
- For sdist: finds `__init__.py` files to identify packages
- Maps file paths to Python import paths
- Excludes:
  - Test directories (`test/`, `tests/`)
  - Documentation (`docs/`)
  - Examples (`examples/`, `example/`)
- Normalizes package names (`my-package` → `my_package`)
- Fallback: uses normalized package name
- Format: `package.module.submodule`

**Example Output**:
```python
["requests", "requests.api", "requests.models", "requests.sessions", "requests.adapters"]
```

**Service Method**:
```python
async def extract_import_names(package_name: str, version: str) -> list[str]:
    # Downloads wheel or sdist from PyPI
    # Extracts .whl (ZIP) or .tar.gz → .py files → module paths
    # Cache: "import_names:{package}:{version}", TTL: 7 days
```

### Common Implementation Patterns

**All services follow this pattern**:

```python
# In API service (e.g., cargo_api.py)
class CargoService:
    async def extract_import_names(self, crate: str, version: str) -> list[str]:
        # 1. Check cache
        cache_key = f"import_names:{crate}:{version}"
        cached = await self.cache.get_cache(cache_key)
        if cached:
            return cached
        
        # 2. Download package file
        url = f"https://crates.io/api/v1/crates/{crate}/{version}/download"
        package_bytes = await download(url, timeout=30)
        
        # 3. Extract import_names (CPU-intensive, use thread pool)
        loop = asyncio.get_running_loop()
        import_names = await loop.run_in_executor(
            None, self._extract_sync, package_bytes
        )
        
        # 4. Cache for 7 days
        await self.cache.set_cache(cache_key, import_names, ttl=604800)
        return import_names
    
    def _extract_sync(self, package_bytes: bytes) -> list[str]:
        # Synchronous extraction (runs in thread pool)
        # Parse tarball/zip, extract source files, find imports
        ...
```

**In Extractor** (e.g., `cargo_extractor.py`):

```python
class CargoPackageExtractor(PackageExtractor):
    async def create_package(self, package_name: str, ...):
        # ... existing code ...
        
        # Extract import_names from latest version
        import_names = []
        if versions:
            latest_version = versions[-1].get("name")
            if latest_version:
                import_names = await self.cargo_service.extract_import_names(
                    package_name, latest_version
                )
        
        # Create package with import_names
        pkg = CargoPackageSchema(
            name=package_name,
            import_names=import_names,  # ← New field
            ...
        )
```

### Performance Optimizations

1. **7-Day Cache**: Import names rarely change, so 7-day TTL minimizes downloads
2. **Thread Pool**: CPU-intensive parsing runs in `asyncio.to_thread()` to avoid blocking
3. **Lazy Loading**: Only extracts for latest version during package creation
4. **Smart Filtering**: Excludes tests, examples, and internal files
5. **Fallback Strategy**: Uses package name if extraction fails (ensures field is never empty)
6. **Timeout Protection**: 30-second timeout for downloads
7. **Error Isolation**: Extraction failures don't block package creation

### Standalone Backfill Scripts

Located in `crawl_import_names/`:

| Script | Ecosystem | Features |
|--------|-----------|----------|
| `crawl_cargo_import_names.py` | Cargo | Batch: 100, dotenv config, statistics |
| `crawl_maven_import_names.py` | Maven | Deduplication, 30s timeout, stats |
| `crawl_npm_import_names.py` | NPM | Direct LIMIT, 30s timeout, stats |
| `crawl_rubygems_import_names.py` | RubyGems | 10 concurrent, dotenv, statistics |

**Common Features**:
- ✅ Dotenv configuration (no hardcoded credentials)
- ✅ LIMIT 100 (processes 100 packages per run)
- ✅ Comprehensive statistics (success, errors, no imports)
- ✅ Thread pool usage for CPU-intensive operations
- ✅ Proper error handling with specific exceptions
- ✅ Progress logging

**Usage**:
```bash
# Configure environment
cp template.env .env
nano .env  # Set NEO4J credentials

# Run script
python crawl_import_names/crawl_cargo_import_names.py

# Output example:
# ======================================================================
# 🚀 Iniciando extracción de import_names para Cargo
# ======================================================================
# 📊 Crates a procesar: 100
# ⚙️  Concurrencia máxima: 10
# ⏱️  Timeout: 30s
# ...
# ======================================================================
# 📊 RESUMEN DE EJECUCIÓN
# ======================================================================
# ✅ Exitosos:              87
# ⚠️  Sin imports:           5
# ❌ Errores descarga:       3
# ❌ Errores proceso:        5
# 📦 Total procesados:     100
# ⏱️  Tiempo total:      45.32s
# ⚡ Promedio:            0.45s/crate
# ======================================================================
```

### Neo4j Storage and Queries

**Schema Update**: All package schemas now include `import_names: list[str]` field.

**Storage**: Automatically stored by `PackageService.create_package_and_versions()`:
```cypher
MERGE (p:CargoPackage {name: $name})
ON CREATE SET 
    p.vendor = $vendor,
    p.repository_url = $repository_url,
    p.import_names = $import_names  ← Stored here
```

**Example Queries**:

```cypher
// Find packages by specific import
MATCH (p:PyPIPackage)
WHERE "requests.api" IN p.import_names
RETURN p.name, p.import_names

// Count most popular imports
MATCH (p:CargoPackage)
UNWIND p.import_names AS import_name
RETURN import_name, COUNT(*) AS packages_count
ORDER BY packages_count DESC
LIMIT 20

// Find packages with many exports
MATCH (p:NPMPackage)
WHERE SIZE(p.import_names) > 10
RETURN p.name, SIZE(p.import_names) AS export_count
ORDER BY export_count DESC

// Cross-ecosystem namespace analysis
MATCH (p)
WHERE p:PyPIPackage OR p:NPMPackage OR p:RubyGemsPackage
UNWIND p.import_names AS import_name
WITH import_name, labels(p)[0] AS ecosystem, COUNT(*) AS count
RETURN ecosystem, import_name, count
ORDER BY count DESC
LIMIT 100
```

### Use Cases

1. **API Surface Discovery**: Understand what's available to import from a package
2. **Dependency Analysis**: Map actual usage patterns vs declared dependencies
3. **Breaking Change Detection**: Compare import_names across versions
4. **Ecosystem Comparison**: Analyze naming patterns across languages
5. **Security Analysis**: Identify packages exposing sensitive APIs
6. **Documentation Generation**: Auto-generate import guides
7. **Code Migration**: Map old package imports to new ones

### Future Enhancements

**Potential improvements**:
- Parse docstrings/comments for additional metadata
- Extract function signatures and type hints
- Build call graphs from import relationships
- Detect deprecated imports
- Version-specific import_names (not just latest)
- Integration with IDE autocomplete systems

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

### Development Setup (Local)

**Using UV (10-100x faster than pip)**:
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Run Dagster locally
uv run dagster dev -m src.dagster_app
```

### Production Deployment (Docker)

**Starting Services**
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

### Development Tools

**UV Package Manager**:
- 🚀 **10-100x faster** than pip for installations
- 💾 **Intelligent caching** - reuses downloaded packages
- 🔒 **Better dependency resolution** - handles conflicts more gracefully
- 🐳 **Docker integration** - Dockerfile uses UV for faster builds
- 📦 **Native pyproject.toml** - no requirements.txt needed
- 🔐 **Lock file** - uv.lock ensures reproducible installs

**Quick Commands**:
```bash
uv sync                       # Install dependencies
uv add <package>             # Add dependency
uv remove <package>          # Remove dependency
uv run <command>             # Run command in environment
uv run dagster dev -m src.dagster_app  # Run Dagster
uv run pytest                # Run tests
uv run ruff check src/       # Run linter
```

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
3. **Dockerfile**: Multi-stage build (builder + runtime) with UV for faster dependency installation
4. **Git**: `.env` is gitignored, use `template.env` as reference
5. **Dagster Version**: Currently 1.11.13 (check pyproject.toml)
6. **Python Version**: 3.13 (specified in Dockerfile and pyproject.toml) - includes JIT compiler and performance improvements
7. **Volumes**: `/src` and `/dagster_home` are mounted for hot-reload during development
8. **Package Manager**: UV is the only package manager - no pip or requirements.txt
9. **Project Config**: `pyproject.toml` is the single source of truth for dependencies
10. **Lock File**: `uv.lock` ensures reproducible installations (auto-generated, commit to git)

## Migration History

**Previous**: Apache Airflow 3.1.0 (5 services, complex Task API, 48+ env vars)  
**Current**: Dagster 1.11.13 (3 services, simple setup, 16 env vars)  
**Reason**: Simpler architecture, better DX, native Pydantic support, asset-centric approach

All business logic from Airflow DAGs was preserved and refactored into Dagster assets.

## Testing

To test the setup:
```bash
# Local development with UV
uv run python -c "from src.dagster_app import defs; print('OK')"
uv run dagster asset list -m src.dagster_app
uv run dagster schedule list -m src.dagster_app

# Docker (production)
# 1. Verify Python imports work
docker compose exec dagster-webserver \
  python -c "from src.dagster_app import defs; print('OK')"

# 2. List assets (should show 13)
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
- **UV Package Manager**: https://github.com/astral-sh/uv
- **Ruff Linter**: https://github.com/astral-sh/ruff

---

**Last Updated**: October 10, 2025  
**Dagster Version**: 1.11.13  
**Python Version**: 3.13 (JIT compiler, improved async performance)  
**Package Manager**: UV (native, no pip/requirements.txt)  
**Recent Features**: 
- Python 3.13 upgrade for ~15-20% performance improvement
- UV package manager as sole dependency manager
- pyproject.toml as single source of truth
- uv.lock for reproducible installs
- Simplified development workflow (no scripts needed)
- Package ingestion assets for PyPI, NPM, and Maven with optimized deduplication and caching
- Redis queue processor for asynchronous package extraction
- **Import Names Extraction System**: Automatic extraction of importable modules/classes for all 6 ecosystems (Cargo, Maven, NPM, RubyGems, NuGet, PyPI) with 7-day caching, thread pool execution, and Neo4j storage

````
