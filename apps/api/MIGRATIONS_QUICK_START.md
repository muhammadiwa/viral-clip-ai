# 🚀 Quick Start - Database Migrations

## Setup (One Time)

```bash
# Install dependencies
cd apps/api
pip install -r requirements.txt

# Setup migrations (optional check)
bash setup-migrations.sh
```

## Running Migrations

### Using Makefile (Recommended)

```bash
# Run all pending migrations
make migrate

# Create new migration
make migrate-make name=add_new_field

# Rollback last migration
make migrate-rollback

# Check status
make migrate-status

# View history
make migrate-history
```

### Using Python Script Directly

```bash
cd apps/api

# Run migrations
python migrate.py migrate

# Create new migration
python migrate.py make add_new_field

# Rollback
python migrate.py rollback

# Status
python migrate.py status
```

## First Time Migration

```bash
# 1. Make sure your database is running
docker-compose up -d postgres

# 2. Run the migration
make migrate

# 3. Verify
make migrate-status
```

You should see:
```
✅ Migration: 001_add_owned_org_id (head)
```

## Current Migrations

### 001_add_owned_org_id
Adds `owned_org_id` field to users table for new authentication system.

**What it does:**
- Adds `owned_org_id` column (UUID, nullable, unique)
- Creates foreign key to `organizations` table
- Adds index for performance
- Supports new 1 user = 1 owned organization model

## Troubleshooting

### "alembic_version table doesn't exist"
This is normal for first-time setup. Just run:
```bash
make migrate
```

### "Migration already applied"
Check current status:
```bash
make migrate-status
```

### Need to rollback?
```bash
make migrate-rollback
```

## Full Documentation

See [MIGRATIONS.md](./MIGRATIONS.md) for complete guide.
