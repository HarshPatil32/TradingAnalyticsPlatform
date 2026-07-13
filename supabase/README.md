# Supabase migrations

Schema changes live in `supabase/migrations/` and are the source of truth for the database. Local sample data is in `supabase/seed.sql` and is local-only.

## Prerequisites

Install the Supabase CLI and link to the **dev** hosted project. See [backend/README.md](../backend/README.md#supabase-cli) for one-time setup (`supabase login`, `supabase link`).

## Creating a migration

From the repo root:

```bash
supabase migration new <description>
```

The CLI creates `supabase/migrations/YYYYMMDDHHMMSS_<description>.sql`. Write schema changes as plain SQL in that file. One concern per migration (e.g. `create_profiles_table`, `add_type_tier_check_constraints`).

## Local reset

Requires Docker and a running local stack (`supabase start`).

```bash
supabase db reset
```

This drops and rebuilds the local database, replays every file in `supabase/migrations/` in order, then runs `supabase/seed.sql` (configured in `config.toml` under `[db.seed]`). Use this to test a new migration end-to-end or return to a clean known state.

## Applying to hosted dev

After linking to the dev project, push pending migrations:

```bash
supabase db push
```

This applies only migrations not yet recorded on the linked project. It does **not** run `seed.sql`. Seed data is for local development only.

## Migrations vs seed.sql

| | Migrations | `seed.sql` |
|---|---|---|
| Purpose | Schema (tables, indexes, triggers, constraints) | Local dev sample data |
| Committed | Yes | Yes |
| Applied on `db reset` | Yes | Yes |
| Applied on `db push` | Yes | No |
| Safe on hosted dev/prod | Yes (dev via `db push`; prod via deploy pipeline) | **No** |

`seed.sql` inserts `auth.users` rows with a shared known password (`devpassword123`). Never run it against a hosted project.

## Safety notes

- Never run `supabase db reset` against a hosted project. It is destructive and local-only.
- Do not push migrations to **prod** from a local machine unless that is an explicit, reviewed deployment step.
- Treat migrations as the source of truth for schema. Manual edits in the Supabase dashboard will drift and can conflict on the next `db push` or `db reset`.
- Before `supabase db push`, confirm the linked project with `supabase status` or your dev project ref. Use the dev project only, not prod.
