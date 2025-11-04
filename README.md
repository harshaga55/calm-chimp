# Calm Chimp — AI-Powered Study Planner

Calm Chimp is a desktop-first study planner built with PyQt, Poetry, LangGraph, and FastMCP. It helps students avoid task-hopping by turning book outlines, lecture PDFs, or custom prompts into deterministic task plans that flow directly into a daily calendar. The agent-driven planner keeps focus on one task at a time while the MCP server and local HTTP API make the assistant accessible from automations or other chat UIs.

## ✨ Key Features

- **Calendar + Activity Dashboard**: PyQt interface with tabs for calendar views, recent activity timeline, and outline planning.
- **Right-Side Chatbot Panel**: Deterministic command bot orchestrates MCP tools for scheduling, overviews, and quick actions.
- **LangGraph Study Agent**: Deterministic plan generation from tables of contents or ad-hoc prompts, tuned for academic workflows.
- **Deterministic Local API**: 30+ single-purpose functions drive MCP tools and GUI actions with predictable behavior.
- **FastMCP Server Tools**: Automatically exposes every API function (minimum 25 tools) so the chatbot can operate the calendar.
- **JSON History Log**: Every change captured with snapshots so users can revert the planner to any previous state (stored under the OS app-support directory, e.g. `~/Library/Application Support/Calm Chimp/tasks.json` on macOS).
- **macOS Desktop App**: Packageable GUI (via `scripts/build_dmg.sh`) for DMG distribution.

## 🛠 Tech Stack

- Poetry-managed Python 3.11
- PyQt6 for the GUI
- LangChain Core + LangGraph for deterministic agents
- FastMCP for MCP server tooling (25+ tools auto-generated from the API)
- FastAPI + Hypercorn for the local HTTP service
- orjson + Pydantic for fast JSON handling

## 🚀 Getting Started

```bash
poetry install
poetry run calm-chimp gui       # launch the desktop planner (primary experience)
poetry run calm-chimp api       # optional: start http://127.0.0.1:8000 for local integrations
poetry run calm-chimp mcp       # optional: expose 25+ MCP tools at http://127.0.0.1:8765
```

### Planning From a Table of Contents
1. Launch the GUI (`poetry run calm-chimp gui`).
2. Paste or load outline lines (e.g. chapters from a PDF TOC) in the Planner tab.
3. Set the subject, due date, and hours per section.
4. Generate the plan to populate the calendar and history log at the same time.

### Using the MCP Tools
- Every function under `calm_chimp/api/` is exposed as an MCP tool automatically.
- Example tool names: `generate_plan_from_outline`, `calendar_tasks_for_day`, `list_overdue_tasks`, `revert_calendar_to_history_entry`.

Point your MCP-capable client at `http://127.0.0.1:8765/stream` (FastMCP default) to interact with the chatbot-friendly toolkit.

### HTTP API Quick Test

```bash
curl -X POST http://127.0.0.1:8000/api/functions/list_pending_tasks_ordered_by_due_date \
  -H "Content-Type: application/json" \
  -d '{ "arguments": {} }'
```

Use `GET /api/functions` to discover all available deterministic API calls.

### Azure OpenAI Configuration

Copy `.env.example` to `.env` and populate your Azure resource details:

```bash
cp .env.example .env
```

Required values:

- `AZURE_OPENAI_ENDPOINT`: e.g. `https://your-instance.openai.azure.com/`
- `AZURE_OPENAI_API_KEY`: the key from your Azure OpenAI resource
- `AZURE_OPENAI_DEPLOYMENT`: deployment name (defaults to `gpt-4o` in the example)
- `AZURE_OPENAI_API_VERSION`: the API version to target (no default; check the Azure OpenAI docs for the latest supported value)

When these variables are present the in-app chatbot will call your Azure-hosted model to decide which Calm Chimp API function (and MCP tool) to invoke. Leave them unset to fall back to local heuristics and slash commands.

If any of the variables are missing at runtime the GUI will show a notice and continue using the offline keyword heuristics instead of the Azure model.

### Supabase Authentication & Storage

Calm Chimp now supports Supabase-backed sign-in (email/password or Google) and persists calendar data per user. Configure the following environment variables in `.env`:

- `SUPABASE_URL` — your Supabase project URL, e.g. `https://abcd1234.supabase.co`
- `SUPABASE_ANON_KEY` — the anon public API key
- `SUPABASE_SERVICE_ROLE_KEY` *(optional)* — only required if you plan to run privileged maintenance scripts directly from the desktop app

In Supabase:

1. Enable Email auth (password or magic link) and the Google provider under **Authentication → Providers**.
2. Set the OAuth redirect URI to `http://localhost:52151/auth/callback` (adjust the port via `SUPABASE_REDIRECT_PORT` if needed).
3. Create the application tables with Row Level Security enabled. At minimum you’ll need:
   - `profiles` (primary key `id uuid references auth.users`, plus `email`, `full_name`, `avatar_url`, timestamps)
   - `user_subjects` (primary key `id uuid default gen_random_uuid()`, `user_id uuid references auth.users`, subject metadata)
   - `user_events` (primary key `id uuid`, `user_id uuid references auth.users`, task fields such as `title`, `due_date`, `status`, `notes`, `plan jsonb`)
   - `history_entries` (primary key `id text`, `user_id uuid`, `timestamp timestamptz`, `action`, `snapshot jsonb`, `metadata jsonb`)
4. Add RLS policies so authenticated users can CRUD only their own rows for each table.
5. (Optional) Attach the trigger from the setup guide so a matching `profiles` row is created automatically whenever a new `auth.users` entry appears.

With the environment and tables in place, launching the GUI will present a Supabase login dialog. Successful authentication wires all API calls to the Supabase-backed storage instead of the previous local JSON file.

### macOS App Bundle & DMG (Briefcase)

```bash
# One-time prerequisites (if not already available)
xcode-select --install           # install command line tools

# Build & package using Briefcase (Apple silicon arm64 by default)
bash scripts/package_macos.sh
```

The script wraps Briefcase's `create`, `build`, and `package` phases to produce a native `.app` bundle and DMG under `dist/macOS`. It performs ad-hoc signing so the DMG runs on your machine immediately; swap in your Apple developer identity when you are ready to distribute broadly. The generated DMG opens with the Applications shortcut on the left and a large Calm Chimp icon on the right. If you need an Intel build, rerun the underlying Briefcase commands with `--update --config macOS.universal_build=true` or build from Xcode targeting `x86_64`.

## 🗂 Project Structure

```
src/calm_chimp/
├── __init__.py               # default GUI entry-point
├── cli.py                    # CLI routes to GUI/API/MCP modes
├── agents/                   # LangGraph-based planners
│   └── planner.py
├── api/                      # deterministic function surface (drives MCP + GUI)
│   ├── calendar.py
│   ├── history.py
│   ├── planning.py
│   ├── registry.py
│   ├── subjects.py
│   └── tasks.py
├── core/                     # config, domain models, persistence, scheduling
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   └── scheduler.py
├── services/
│   ├── http/                 # FastAPI deterministic function bridge
│   │   └── server.py
│   └── mcp/                  # FastMCP tool server (auto-registers API functions)
│       └── server.py
└── ui/                       # PyQt desktop application
    └── gui.py
```

## 🚧 Roadmap

- ✅ LangGraph deterministic planner with JSON persistence
- ✅ PyQt GUI + MCP + streamable HTTP integrations
- ⏳ PDF ingestion helpers (outline extraction)
- ⏳ Focus timer & distraction log
- ⏳ Cloud sync + mobile companion
