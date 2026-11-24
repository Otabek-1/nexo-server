# Nexo Backend

## Run (dev)

```bash
cp .env.example .env
docker compose up --build
```

API root: `http://localhost:8000/api/v1`
Frontend env (`client/.env`): `VITE_API_BASE_URL=http://localhost:8000/api/v1`

## Migrations

```bash
alembic upgrade head
```

For databases created before Alembic version tracking, startup safely recognizes a complete schema through revision `20260409_0004`, records that baseline, and applies later migrations. It does not stamp incomplete or newer schemas.

After deploying backend changes that add database enum values or columns, run this command against the production database before creating tests that use those changes.

## Notes

- `STORAGE_PROVIDER=local|minio|supabase`
- Supabase storage uses S3-compatible settings (`S3_*` vars).
- Auth: JWT access + refresh.
- `scoringType=rasch` uses 1PL Rasch estimation (JML-style iterative fit) on objective items.
- `scoringType=irt` uses a 2PL IRT/EAP model with configurable item difficulty (`b`), discrimination (`a`) and guessing (`c`) parameters.
- IRT and SAT tests force Telegram registration and the configured attempt limit; participants must start the bot and share the registered phone number. After the test closes and the IRT score is finalized, the bot sends each registered participant their result.
- Tests can include ordered modules with `durationMinutes`, `breakAfterMinutes`, subject and adaptive routing metadata.
- IRT Reading and Writing / Math groups are mapped separately to 200-800 section scores and combined to an SAT-style 400-1600 total.
- Module routing is a Nexo heuristic: at least 75% module accuracy routes to a harder next module; otherwise it routes to an easier module. This is not a claim that Nexo reproduces College Board's proprietary SAT routing algorithm.
- If essay/short-answer questions exist, final score is composite:
  - Rasch objective component (0-100, weighted by objective points share)
  - Manual component (0-100, weighted by manual points share)
