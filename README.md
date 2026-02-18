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

## Notes

- `STORAGE_PROVIDER=local|minio|supabase`
- Supabase storage uses S3-compatible settings (`S3_*` vars).
- Auth: JWT access + refresh.
- `scoringType=rasch` uses 1PL Rasch estimation (JML-style iterative fit) on objective items.
- If essay/short-answer questions exist, final score is composite:
  - Rasch objective component (0-100, weighted by objective points share)
  - Manual component (0-100, weighted by manual points share)
