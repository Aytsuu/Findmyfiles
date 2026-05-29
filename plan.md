# Searchable Memory for Windows Desktop Files

A local-first semantic search system that continuously indexes your Windows file system using the Gemini 2 multimodal embedding API, stores vectors in ChromaDB, and exposes results through a fast HTTP API consumed by a launcher UI (Flow Launcher / custom Flox extension).

## Architecture

```
[ Windows File System ]
       │
       ▼ (Background Watchdog)
[ Python Indexing Service ] ──(Gemini Embedding 2 API)──► [ Multimodal Vectors ]
       │                                                 │
       ▼                                                 ▼
[ ChromaDB (Local Storage) ] ◄───────────────────────────┘
       ▲
       │ (IPC / HTTP API)
[ Raycast / Flow Launcher Extension UI ]
```

---

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| File watching | `watchdog` (Python) | Cross-platform FS events; low overhead |
| Indexing service | Python 3.12, `asyncio` | Async batch embedding calls |
| Embedding model | `gemini-embedding-2` (Gemini Embedding 2) | Multimodal: text + image + PDF |
| Vector DB | ChromaDB (embedded mode) | Zero-server local storage, HNSW index |
| API server | FastAPI + Uvicorn | Lightweight, async, auto-docs at `/docs` |
| UI | Flow Launcher plugin (C#) or Electron tray app | Windows-native launcher integration |
| Config | `config.toml` | Human-editable, versioned |

---

## Components

### 1. File System Watchdog (`watcher.py`)

- Monitors configured root directories (e.g. `~/Desktop`, `~/Documents`, `D:\Projects`)
- Events handled: `created`, `modified`, `moved`, `deleted`
- Debounces rapid bursts (e.g. git checkout touching 1000 files) with a 2-second settle window
- Enqueues file paths to an async `asyncio.Queue` consumed by the indexer
- Filters by configurable include/exclude glob patterns (e.g. `*.tmp`, `.git/**` excluded)

### 2. Indexing Service (`indexer.py`)

Responsible for extracting content and generating embeddings.

**Supported file types & extraction strategy:**

| File Type | Extraction Method |
|---|---|
| `.txt`, `.md`, `.py`, `.js`, `.ts`, `.json`, `.yaml`, etc. | Read raw text, chunk by token limit |
| `.pdf` | `pdfplumber` → text per page; first page as image if text-sparse |
| `.docx`, `.xlsx` | `python-docx` / `openpyxl` → text extraction |
| `.png`, `.jpg`, `.webp`, `.gif` | Send raw bytes to Gemini multimodal embedding |
| `.mp4`, `.mov` | Extract keyframes via `ffmpeg`, embed as images |

**Chunking strategy:**
- Text files chunked to ~500 tokens with 50-token overlap
- Each chunk stored as a separate ChromaDB document with parent file metadata
- Images and short files stored as a single vector

**Embedding call:**
```python
genai.embed_content(
    model="models/gemini-embedding-2",
    content=chunk,          # text str or PIL.Image
    task_type="RETRIEVAL_DOCUMENT",
)
```

**Batch processing:**
- Up to 100 embeddings per API call to stay within rate limits
- Exponential backoff on `ResourceExhausted` errors

### 3. Vector Store (`store.py`)

Thin wrapper around ChromaDB's embedded client.

```
~/.findmyfiles/
  chroma/           ← ChromaDB persistent directory
  findmyfiles.log    ← rotating log
  config.toml       ← user configuration
```

**Collection schema:**

| Field | Type | Description |
|---|---|---|
| `id` | str | SHA256(filepath + chunk_index) |
| `embedding` | float[] | 768-dim Gemini Embedding 2 vector |
| `document` | str | Chunk text (or image description) |
| `metadata.path` | str | Absolute file path |
| `metadata.mtime` | float | File modified timestamp |
| `metadata.chunk` | int | Chunk index within file |
| `metadata.mime` | str | Detected MIME type |
| `metadata.size` | int | File size in bytes |

**Key operations:**
- `upsert(file_path, chunks, embeddings)` — idempotent, keyed by content hash
- `delete(file_path)` — removes all chunks for a deleted/moved file
- `query(query_embedding, n_results, filters)` — returns ranked results with metadata

### 4. HTTP API (`api.py`)

FastAPI application served on `http://localhost:7474`.

**Endpoints:**

```
GET  /health                    → service status + index stats
POST /search                    → semantic search
POST /index   (admin)           → manually trigger re-index of a path
DELETE /index (admin)           → remove a path from index
GET  /config                    → current config
```

**`POST /search` request body:**
```json
{
  "query": "invoice from acme corp march",
  "n_results": 10,
  "filters": {
    "mime": "application/pdf",
    "path_prefix": "D:\\Documents"
  }
}
```

**`POST /search` response:**
```json
{
  "results": [
    {
      "path": "D:\\Documents\\acme_invoice_2026-03.pdf",
      "score": 0.92,
      "chunk": 0,
      "snippet": "Invoice #4821 – Acme Corp – March 2026...",
      "mime": "application/pdf",
      "size": 48320,
      "mtime": 1748500000.0
    }
  ],
  "query_time_ms": 12
}
```

### 5. Configuration (`config.toml`)

```toml
[watcher]
roots = ["C:/Users/you/Desktop", "C:/Users/you/Documents", "D:/Projects"]
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
```

### 6. UI Integration

#### Option A — Flow Launcher Plugin (Recommended for Windows)
- C# plugin that calls `GET http://localhost:7474/search?q={query}` on each keypress
- Displays file icon, filename, snippet, and score
- Action: open file with default app, reveal in Explorer, copy path

#### Option B — Electron Tray App
- Minimal Electron app with a global hotkey (`Win+Space` or configurable)
- Renders a search bar + results list in a floating window
- Falls back gracefully if the Python service is not running

---

## Project File Structure

```
findmyfiles/
├── config.toml                  # User configuration
├── pyproject.toml               # Python project metadata & deps
├── README.md
├── src/
│   └── findmyfiles/
│       ├── __init__.py
│       ├── main.py              # Entry point: starts watcher + API
│       ├── watcher.py           # watchdog integration
│       ├── indexer.py           # Content extraction + embedding
│       ├── store.py             # ChromaDB wrapper
│       ├── api.py               # FastAPI app
│       ├── config.py            # Config loading (pydantic-settings)
│       └── extractors/
│           ├── __init__.py
│           ├── text.py          # Plain text / code chunking
│           ├── pdf.py           # pdfplumber extraction
│           ├── office.py        # docx / xlsx
│           └── image.py         # PIL image loading
├── ui/
│   └── flow-launcher-plugin/    # (Option A) C# Flow Launcher plugin
│       ├── Main.cs
│       ├── plugin.json
│       └── Findmyfiles.csproj
└── tests/
    ├── test_indexer.py
    ├── test_store.py
    └── test_api.py
```

---

## Python Dependencies (`pyproject.toml`)

```toml
[project]
name = "findmyfiles"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "google-generativeai>=0.8",
    "chromadb>=0.6",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "watchdog>=4.0",
    "pdfplumber>=0.11",
    "python-docx>=1.1",
    "openpyxl>=3.1",
    "Pillow>=10.0",
    "pydantic-settings>=2.0",
    "tomli>=2.0",
    "tenacity>=8.0",       # retry / backoff
    "tiktoken>=0.7",       # token counting for chunking
]

[project.scripts]
findmyfiles = "findmyfiles.main:run"
```

---

## Implementation Phases

### Phase 1 — Core Pipeline (MVP)
- [ ] `config.py` — load and validate `config.toml`
- [ ] `store.py` — ChromaDB init, upsert, delete, query
- [ ] `indexer.py` — text extraction, chunking, Gemini embedding, batch upsert
- [ ] `watcher.py` — watchdog events → indexer queue
- [ ] `main.py` — wire watcher + run initial full scan on startup

### Phase 2 — API & Search
- [ ] `api.py` — FastAPI with `/search`, `/health`, `/index` endpoints
- [ ] Query embedding via Gemini `RETRIEVAL_QUERY` task type
- [ ] Metadata filters (MIME type, path prefix, date range)
- [ ] Startup: re-index stale files (mtime changed since last embed)

### Phase 3 — UI
- [ ] Flow Launcher plugin skeleton (C#)
- [ ] Keypress → HTTP search → display results
- [ ] Open/reveal/copy actions
- [ ] Service health indicator in plugin

### Phase 4 — Polish
- [ ] Windows service wrapper (`pywin32` or NSSM) for auto-start
- [ ] Incremental re-index (skip files whose mtime + size unchanged)
- [ ] Tray icon with index progress / pause / re-index-all actions
- [ ] Unit tests for indexer, store, and API

---

## Open Questions

> [!IMPORTANT]
> **Gemini API Key**: Will the API key be stored in `config.toml` or pulled from the `GEMINI_API_KEY` environment variable? (Recommended: env var for security)

> [!IMPORTANT]
> **UI Choice**: Flow Launcher plugin (C#, deep Windows integration) vs. standalone Electron tray app (easier to iterate on)? Flow Launcher is recommended for a native feel.

> [!NOTE]
> **Video indexing**: Frame extraction via `ffmpeg` adds a heavy dependency. Should video files be excluded in the MVP scope?

> [!NOTE]
> **Rate limits**: `gemini-embedding-2` has free-tier limits. For large file collections (>10k files), consider a paid tier or a local fallback embedding model (e.g. `nomic-embed-text` via Ollama).
