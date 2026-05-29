# Findmyfiles

`findmyfiles` is a local-first file indexing and semantic search service for Windows-oriented desktop files. It scans configured folders, chunks supported text documents, stores embeddings in a local ChromaDB collection, and exposes a small FastAPI surface for search and index management.

This repository currently implements an MVP runtime:

- `config.toml`-driven configuration
- local persistent ChromaDB vector storage under `storage.chroma_dir`
- Gemini embeddings for indexed text chunks and queries
- basic support for PDF, DOCX, and XLSX extraction
- FastAPI endpoints for health, config, search, and manual indexing
- filesystem watcher wiring for incremental updates
- pytest coverage for store, indexer, and API behavior

## Project Layout

```text
src/findmyfiles/
  api.py
  config.py
  indexer.py
  main.py
  store.py
  watcher.py
  extractors/
tests/
config.toml
pyproject.toml
```

## Requirements

- Python `3.11+`
- Recommended: virtual environment
- Windows, if you want to use the current Flow Launcher UI integration
- `.NET 8 SDK`, if you want to build the Flow Launcher plugin from source
- `GEMINI_API_KEY` in your environment for runtime indexing and search

## Prerequisites

Before using the full local workflow, install:

- Python with `pip`
- Flow Launcher, if you want to use the current UI
- `.NET 8 SDK`, if you want to compile the Flow Launcher plugin yourself
- A Gemini API key exported as `GEMINI_API_KEY`

Important:

- This repository does not currently include a standalone desktop UI.
- The only shipped UI is the Flow Launcher plugin in `ui/flow-launcher-plugin`.
- If Flow Launcher is not installed, you can still run the backend API and use `http://127.0.0.1:7474/docs` directly.

## UI Prerequisite: Flow Launcher

If you want the launcher-based UI, install the Flow Launcher application first:

- Website: `https://www.flowlauncher.com/`
- Docs: `https://github.com/Flow-Launcher/docs`

After Flow Launcher is installed, build and install the plugin from this repository as described in `ui/flow-launcher-plugin/README.md`.

## Install

Create a virtual environment and install the project dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

If you do not want an editable install, you can still run the project by setting `PYTHONPATH` to `src`, but `pip install -e .` is the cleaner path for local development.

## Configuration

Edit `config.toml` before startup:

```toml
[watcher]
roots = ["C:/Users/you/OneDrive/Desktop", "C:/Users/you/Downloads"]
exclude_globs = [".git/**", "node_modules/**", "*.tmp", "*.log", "__pycache__/**"]
include_exts = [".txt", ".md", ".py", ".js", ".ts", ".pdf", ".docx", ".png", ".jpg"]

[indexer]
batch_size = 20
chunk_tokens = 500
chunk_overlap = 50
model = "models/gemini-embedding-2"

[api]
host = "127.0.0.1"
port = 7474

[storage]
chroma_dir = "~/.findmyfiles/chroma"
collection_name = "findmyfiles"
```

Notes:

- `watcher.roots` must point to real directories on your machine.
- `storage.chroma_dir` is where the embedded ChromaDB collection is persisted.
- `storage.collection_name` lets you isolate different local indexes inside the same Chroma directory.
- `GEMINI_API_KEY` is required at runtime. Startup will fail fast if it is missing and no custom embedder is injected.

## Startup

Set your Gemini key before startup:

```powershell
$env:GEMINI_API_KEY = "your-key-here"
```

The service starts the HTTP API immediately, then performs the initial scan in a background thread while the watcher stays active.

Run with the package entry point:

```powershell
findmyfiles
```

Or run the module directly during development:

```powershell
python -m findmyfiles.main
```

If you did not install the package, run with `PYTHONPATH=src` semantics:

```powershell
$env:PYTHONPATH = "src"
python -m findmyfiles.main
```

After startup, the API is available at:

- `http://127.0.0.1:7474/health`
- `http://127.0.0.1:7474/docs`

## Flow Launcher UI

To use the current UI:

1. Install the Flow Launcher desktop app.
2. Start the backend service from this repository.
3. Build the plugin:

```powershell
dotnet build ui\flow-launcher-plugin\Findmyfiles.csproj
```

4. Copy the plugin build output from:

```text
ui\flow-launcher-plugin\bin\Debug\net8.0-windows\
```

Into a Flow Launcher plugin folder such as:

```text
%APPDATA%\FlowLauncher\Plugins\Findmyfiles\
```

Use the `Roaming` plugin directory, not the versioned Flow Launcher install directory under `AppData\Local`.

Correct:

```text
C:\Users\you\AppData\Roaming\FlowLauncher\Plugins\Findmyfiles\
```

Wrong:

```text
C:\Users\you\AppData\Local\FlowLauncher\app-2.1.2\Plugins\Findmyfiles\
```

Why:

- `Roaming` is the user plugin/config area where Flow Launcher discovers custom plugins.
- `Local\FlowLauncher\app-*` is the application install/runtime area and can change on app updates.
- Putting the plugin in `Local\app-*` can prevent Flow Launcher from loading it as a user plugin.

5. Restart Flow Launcher.
6. Search with the action keyword:

```text
fmf invoice march
```

## API

### Health

```http
GET /health
```

Returns service status and index statistics.

### Config

```http
GET /config
```

Returns the active application configuration.

### Search

```http
POST /search
Content-Type: application/json
```

Request body:

```json
{
  "query": "invoice march project notes",
  "n_results": 10,
  "filters": {
    "mime": "text/plain",
    "path_prefix": "D:\\Documents",
    "mtime_from": 1700000000,
    "mtime_to": 1800000000
  }
}
```

### Manual indexing

```http
POST /index
Content-Type: application/json
```

```json
{
  "path": "D:\\Documents\\notes.txt"
}
```

### Remove indexed file

```http
DELETE /index
Content-Type: application/json
```

```json
{
  "path": "D:\\Documents\\notes.txt"
}
```

## Testing

Run the full test suite:

```powershell
python -m pytest
```

Current coverage includes:

- vector store upsert, query, delete, and stale detection
- indexer chunking, indexing, and unchanged-file skip behavior
- API health, search, index, and delete endpoints
- watcher startup behavior for missing and valid roots

## Current MVP Scope

The codebase now uses the planned core runtime integrations, but scope is still intentionally narrow.

- ChromaDB is the active local vector store.
- Gemini embeddings are the active runtime embedding provider for text content.
- Tests stay offline by injecting fake embedders instead of calling Gemini.
- Watcher wiring exists, but richer debounce and event handling can still be expanded.
- Image and video embeddings are not wired yet; non-text unsupported files still fall back to filename-only indexing.

That keeps the runtime aligned with the original design while keeping the test suite deterministic and fast.
