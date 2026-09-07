# Running and deploying Couplefins

The app is one container: FastAPI serves both the API and the built frontend
from the same origin, backed by Neon PostgreSQL.

- **Production**: <https://couplefins.fly.dev>
- **Platform**: Fly.io, one machine in `sjc`
- **Database**: Neon, `us-west-2` (unchanged by hosting — the same database the
  laptops already used)

## Local development

Unchanged. `pnpm dev` runs the API on :8001 and Vite on :5174, with Vite
proxying `/api` to the API. Nothing about hosting affects this loop: the static
mount is a no-op when `web/dist` does not exist.

## First-time Fly setup

```bash
fly auth login
fly launch --no-deploy --name couplefins --region sjc   # keeps the committed fly.toml
```

Set the secrets **before the first deploy**. `AUTH__JWT_SECRET` has a
development default that is long enough to pass validation, so an app deployed
without this would happily sign sessions with a value that is in the public
repository:

```bash
fly secrets set \
  DATABASE__URL='postgresql+asyncpg://USER:PASS@ep-xxxx-pooler.us-west-2.aws.neon.tech/DB?sslmode=require' \
  AUTH__JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

# Optional. Without it, chat is unavailable and nothing else changes.
fly secrets set CHAT__ANTHROPIC_API_KEY='sk-ant-...'
```

Two details in that database URL matter:

- **`+asyncpg`** — the app derives its migration URL by swapping this for
  `+psycopg`. A bare `postgresql://` makes SQLAlchemy reach for psycopg2, which
  is not installed.
- **the `-pooler` endpoint** — the app keys off that literal substring to switch
  to `NullPool` with the statement cache disabled, which PgBouncer's transaction
  pooling requires.

Then:

```bash
fly deploy
fly scale count 1     # assert a single machine; see below
```

Every `fly secrets set` restarts the machine, which re-runs migrations and
seeds. Batch them into one command.

## Deploying

Tagging is the deploy. `.github/workflows/release.yml` fires on a `v*` tag: it
extracts that version's section from `CHANGELOG.md` (failing if there isn't
one), publishes a GitHub Release, then runs `flyctl deploy --remote-only`.

```bash
git tag v1.14.1 && git push origin main --tags
```

Manual escape hatch: `fly deploy --ha=false`.

Always pass `--ha=false`. Fly otherwise provisions a second machine for high
availability — which is precisely what this app cannot have (see below). The
first deploy did exactly that and the extra machine had to be destroyed.

## Why exactly one machine

Not a cost decision. Two in-process singletons would split across instances:

- `src/infrastructure/events/event_bus.py` fans SSE out in-process, so a
  mutation on one machine would never reach a client connected to the other.
- `src/interface/api/rate_limit.py` is an in-process fixed-window counter.

`auto_stop_machines = 'off'` keeps Fly's proxy from stopping the machine on its
own, and `--ha=false` on every deploy stops Fly adding one. Verify with
`fly status` after any deploy: the Machines table must have exactly one row.

## Migrations

They run in the app's lifespan on every boot, not as a Fly `release_command`.
A failed migration fails startup, the health check never passes, and Fly aborts
the release with the previous machine still serving — the same protection as a
release command, without a second migration path to keep in step.

There is deliberately no `sqlalchemy.url` in `alembic.ini`: `alembic/env.py`
prefers that value and falls back to settings only when it is empty, so a value
there would send every CLI `alembic upgrade` to localhost regardless of
`DATABASE__URL`.

## Health checks

Two endpoints, for two audiences:

| Endpoint | Queries the DB | Used by |
|---|---|---|
| `/api/v1/health` | yes | the frontend's schema-version guard |
| `/api/v1/health/live` | no | the Fly health check |

The platform probe must not touch the database. At a 30-second interval it
would reset Neon's autosuspend timer permanently, and a brief database outage
would restart the machine into a startup path that needs that same database.

## Deploy characteristics worth knowing

- **A deploy with a browser tab open pauses for up to 30 seconds.**
  `/api/v1/events` is an SSE stream that never ends on its own, and uvicorn
  drains connections *before* running lifespan shutdown — so a shutdown signal
  from the app would arrive too late. `--timeout-graceful-shutdown 30` is the
  bound. It is not lower because a chat reply legitimately streams for tens of
  seconds; it is under Fly's 60s `kill_timeout` so shutdown always completes
  cleanly. The frontend's `EventSource` reconnects on its own.
- **Rotating `AUTH__JWT_SECRET` logs both people out**, since tokens are signed
  with it and last 7 days.
- **Logs are stdout only** (`fly logs`). `LOGGING__FILE_PATH` is unset in
  production on purpose — a rotating file on an ephemeral disk is write-only.

## Configuration reference

Non-secret values live in `fly.toml`'s `[env]` and are versioned with the code:
`LOGGING__OUTPUT=json`, `LOGGING__LEVEL=INFO`, `AUTH__COOKIE_SECURE=true`,
`AUTH__COOKIE_SAMESITE=lax`, `CORS_ORIGINS=[]`.

`CORS_ORIGINS` is empty because the frontend is served from the API's own
origin, so CORS never comes into play — and an empty list also stops the
development default (`http://localhost:5174`) from being a credentialed origin
against production.

Secrets live in `fly secrets` and are never committed. See `.env.example` for
the full variable surface.

## CI

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | push/PR to `main` | Python gate against a per-PR Neon branch, web gate, Docker build |
| `release.yml` | `v*` tag | GitHub Release from `CHANGELOG.md`, then `flyctl deploy` |
| `neon-cleanup.yml` | PR closed | Deletes that PR's Neon branch |

Required repository configuration: secrets `NEON_API_KEY` and `FLY_API_TOKEN`
(`fly tokens create deploy -x 999999h`), and variable `NEON_PROJECT_ID`.

The Docker build job exists because the Dockerfile would otherwise first be
built by `flyctl deploy` — which runs *after* the GitHub Release is published,
so a broken build would leave a public tag pointing at undeployable code.

## Testing the production image locally

Build and run what Fly builds, against a disposable database — never the
production branch, and not the `docker-compose.yml` test database if the
integration suite might run, since it truncates every table on teardown.

```bash
docker build --target runtime -t couplefins:local .
docker run --rm -p 8080:8000 \
  -e DATABASE__URL='postgresql+asyncpg://...' \
  -e AUTH__JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  -e AUTH__COOKIE_SECURE=false \
  -e LOGGING__OUTPUT=json \
  couplefins:local
```

`AUTH__COOKIE_SECURE=false` only because you will browse it over plain HTTP.

Worth checking, each catching a distinct failure: `/api/v1/health/live`
answers; `/api/v1/health` reports the expected `schema_current`;
`category_groups_seeded` appears in the logs (the fixture reached the image);
`/` and a deep link like `/settle-up` both return `index.html`;
`/api/v1/nope` returns 404 with an `error.code` envelope rather than the app
shell; and logging in works.
