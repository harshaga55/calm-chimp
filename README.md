# Calm Chimp — Supabase Calendar Copilot

Calm Chimp is a Supabase-first, multi-user calendar workspace. A streamlined PyQt desktop app, a lean GPT-5.2 tool-calling layer, and a deterministic API surface let every authenticated user plan events, manage categories, and chat with the assistant without losing momentum. The UI keeps the timeline, category controls, and chat side-by-side so the assistant never blocks your view of upcoming work.

## ✨ Highlights
- **Frontier model tool-calling**: the chat panel now uses GPT-5.2 (or any configured OpenAI model) with a single-step, single-tool prompt for reliable execution.
- **Supabase-native storage**: email/password or Google login is the first screen. The client hydrates one year back and one year forward on sign-in, then serves everything from the in-memory cache for speed.
- **Split-pane productivity UI**: left sidebar for profile & categories, center timeline for daily context, right assistant panel for thin-orchestrated chat. Each runs async through a task runner so Supabase calls never freeze the GUI.
- **Deterministic APIs → MCP tools**: a minimal API catalog (`events_for_day`, `upsert_event`, `list_categories`, and friends) powers the local FastAPI server, FastMCP streamable server, and the new OpenAI tool payloads.
- **Telemetry + verification**: every tool run is logged under `logs/agent_runs` with lightweight verifiers so you can replay or benchmark agent quality.

## 🧱 New Project Layout
```
src/calm_chimp/
├── __init__.py             # exposes run_gui()
├── cli.py                  # CLI entrypoint (gui/api/mcp)
├── api/                    # deterministic API + tool registry
│   ├── endpoints.py
│   ├── registry.py
│   ├── serializers.py
│   └── state.py
├── bootstrap/              # logging bootstrap
├── config/                 # settings + palette
├── data/                   # Supabase gateway, repositories, cache
├── domain/                 # calendar + category dataclasses
├── orchestrator/           # Lean OpenAI orchestration + verifiers
├── services/               # auth, calendar, categories, MCP/HTTP servers
├── ui/                     # PyQt login workflow & split-pane shell
└── utils/                  # Qt task runner helpers
```

## 🚀 Getting Started
```bash
poetry install
cp .env.example .env   # fill in Supabase + OpenAI values
poetry run calm-chimp gui
```

### Environment configuration
| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Required for Supabase auth + data |
| `SUPABASE_REDIRECT_PORT` | Optional, defaults to 52151 |
| `SUPABASE_EVENTS_TABLE` | Defaults to `calendar_events` |
| `SUPABASE_CATEGORIES_TABLE` | Defaults to `event_categories` |
| `SUPABASE_PROFILES_TABLE` | Defaults to `profiles` |
| `OPENAI_API_KEY`, `OPENAI_MODEL` (`gpt-5.2` default), `OPENAI_BASE_URL` (optional), `OPENAI_API_VERSION` (optional, e.g., Azure deployments) | Enable GPT orchestration |
| `CALM_CACHE_WINDOW_BEFORE_DAYS` / `CALM_CACHE_WINDOW_AFTER_DAYS` | Control cache horizon |

### Supabase schema snapshot
Create tables (UUID primary keys) and enable RLS so users see only their own data:
- `profiles`: `{ id uuid pk, email text, full_name text, avatar_url text, created_at timestamptz }`
- `event_categories`: `{ id uuid pk, user_id uuid fk auth.users, name text, color text, icon text, description text }`
- `calendar_events`: `{ id uuid pk, user_id uuid fk, title text, starts_at timestamptz, ends_at timestamptz, status text, category_id uuid, notes text, location text, metadata jsonb }`

### CLI commands
```bash
poetry run calm-chimp gui      # Launch the desktop application
poetry run calm-chimp api      # Expose /api/functions REST bridge
poetry run calm-chimp mcp      # Serve the MCP tool catalog over streamable HTTP
```

### API & MCP
The API registry auto-registers these core tools:
- `refresh_timeline(anchor?: str)`
- `events_for_day(day: str)`
- `events_between(start: str, end: str)`
- `upsert_event(...)`, `update_event_status(...)`, `delete_event(event_id: str)`
- `list_categories()`, `upsert_category(...)`, `delete_category(category_id: str)`
- `current_user_profile()`

The FastAPI bridge exposes them under `/api/functions/{name}`. The MCP server mirrors the list so LangGraph (or any MCP client) can call the same deterministic helpers.

### Desktop experience
1. **Login dialog** — email/password or Google OAuth. Authentication wires the Supabase session into the shared service context and clears stale caches.
2. **Timeline view** — calendar & event list stay visible while the assistant works. Cache hydrates ±365 days on first load.
3. **Assistant panel** — the GPT-5.2 tool caller executes exactly one function per turn; results flow both into the transcript and back to the timeline or category panes when relevant.
4. **Category & event editors** — quick dialogs keep optional metadata flexible while enforcing only the essentials (title & schedule).

## 🧪 Validation
- `poetry run calm-chimp mcp` spins up the MCP server with the tool catalog.
- `poetry run calm-chimp api` exposes the REST bridge for automation tests.
- `python -m compileall src/calm_chimp` ensures all modules import cleanly.

## 📌 Roadmap
- Rich event boards (Kanban/day density)
- Shared calendars & collaboration hints
- LangGraph playbooks for recurring meeting prep
- Real-time Supabase websocket updates
