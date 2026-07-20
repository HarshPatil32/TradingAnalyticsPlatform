# MACD Trading Backend API

This is the backend API for the MACD Trading Strategy application, built with Flask.

## Deployment on Render

This backend is designed to be deployed on Render.com.

### Render Configuration:
- **Build Command**: `./build.sh`
- **Start Command**: `python app.py`
- **Environment**: Python 3.9+

## API Endpoints

- `GET /` - Health check
- `GET /config` - Server configuration (e.g. `max_upload_bytes`)
- `POST /webhookcallback` - Webhook callback
- `GET /MACD-strategy` - MACD trading strategy backtest with optimization
- `GET /spy-investment` - SPY investment comparison
- `POST /analyze-trades` - Upload a CSV trade log or summary report (max 5 MB)

### MACD Strategy Parameters:
- `stocks` - Comma-separated stock symbols (e.g., "AAPL,MSFT")
- `start_date` - Start date in YYYY-MM-DD format
- `end_date` - End date in YYYY-MM-DD format
- `initial_balance` - Initial investment amount (default: 100000)
- `optimize` - Whether to optimize parameters (default: true)

### SPY Investment Parameters:
- `start_date` - Start date in YYYY-MM-DD format
- `end_date` - End date in YYYY-MM-DD format
- `initial_balance` - Initial investment amount (default: 100000)

## Local Development

```bash
pip install -r requirements.txt
python app.py
```

The server will start on `http://localhost:5001`

## Environment Variables

Copy `backend/.env.example` to `backend/.env` for local development (`.env` is gitignored). On Render, set these in the dashboard instead.

At startup, `app.py` validates vars listed in `_ENV_VAR_MANIFEST`. Optional vars log INFO if missing; required vars log WARNING. When `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set, the app also runs a lightweight Supabase connection check (warn-only; logs WARNING on failure). The health check (`GET /`) includes an `env_status` summary and a `supabase_status` field (`configured`, `connected`).

| Variable | Required | Default | Description |
|---|---|---|---|
| `PORT` | No | `5001` | Port the server binds to. Injected automatically by Render. |
| `FLASK_DEBUG` | No | off | Set to `1` to enable Flask debug mode locally. |
| `ALLOWED_ORIGINS` | No | `*` (all) | Comma-separated CORS origins for production (e.g. your Vercel frontend URL). |
| `SUPABASE_URL` | No | — | Supabase project URL. Dashboard: Project Settings → API. |
| `SUPABASE_ANON_KEY` | No | — | Supabase anon/public key (client-safe, RLS-restricted). |
| `SUPABASE_SERVICE_ROLE_KEY` | No | — | Supabase service-role key. **Server-side only** — never expose to the frontend. |
| `SUPABASE_JWT_SECRET` | No | — | JWT secret for verifying Supabase-issued tokens on protected routes. Dashboard: Project Settings → API → JWT Settings → JWT Secret. |

Supabase vars are optional until auth/DB integration is wired up; the app boots without them.

Two Supabase projects are used: **dev** for local `backend/.env`, and **prod** for the Render and Vercel dashboards (not stored in this repo). Never commit real credentials — only the `.env.example` placeholders in git.

## Supabase CLI

The repo includes `supabase/config.toml` for local development and future migrations. Install the CLI once per machine:

```bash
brew install supabase/tap/supabase   # macOS; see https://supabase.com/docs/guides/cli
```

Then link to the **dev** project (one-time, interactive — requires your Supabase account):

```bash
supabase login
supabase link --project-ref <dev-project-ref>
```

`<dev-project-ref>` is the subdomain of your dev `SUPABASE_URL` (e.g. `https://xxxxx.supabase.co` → `xxxxx`). Do not link prod locally unless explicitly needed for a deployment workflow.

Local Postgres/Studio via Docker (run `supabase link` first):

```bash
supabase start   # from repo root
supabase stop
```
