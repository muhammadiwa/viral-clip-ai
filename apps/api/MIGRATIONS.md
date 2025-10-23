# Database Migrations

This project uses Alembic for database migrations, similar to Laravel's migration system.

## Quick Start

### Run All Pending Migrations
```bash
make migrate
# or
cd apps/api && python migrate.py migrate
```

### Create a New Migration
```bash
make migrate-make name=add_new_field
# or
cd apps/api && python migrate.py make add_new_field
```

### Rollback Last Migration
```bash
make migrate-rollback
# or
cd apps/api && python migrate.py rollback
```

### Check Migration Status
```bash
make migrate-status
# or
cd apps/api && python migrate.py status
```

### View Migration History
```bash
make migrate-history
# or
cd apps/api && python migrate.py history
```

## Migration Commands

| Command | Description |
|---------|-------------|
| `make migrate` | Run all pending migrations (upgrade to latest) |
| `make migrate-rollback` | Rollback the last migration |
| `make migrate-status` | Show current migration status |
| `make migrate-history` | Show all migration history |
| `make migrate-make name=X` | Create a new migration file |

## Direct Python Commands

You can also use the migration script directly:

```bash
cd apps/api

# Run migrations
python migrate.py migrate

# Rollback last migration
python migrate.py rollback

# Show status
python migrate.py status

# Show history
python migrate.py history

# Create new migration
python migrate.py make your_migration_name

# Upgrade to specific revision
python migrate.py upgrade <revision_id>

# Downgrade to specific revision
python migrate.py downgrade <revision_id>

# Show help
python migrate.py help
```

## Current Migrations

### 001_add_owned_org_id.py
- **Purpose**: Add `owned_org_id` field to users table for 1:1 user-organization ownership
- **Changes**:
  - Add `owned_org_id` column (UUID, nullable)
  - Add foreign key to `organizations` table
  - Add unique constraint (one org per owner)
  - Add index for performance

**Run this migration:**
```bash
make migrate
```

**Rollback this migration:**
```bash
make migrate-rollback
```

## Creating New Migrations

### Auto-generate from Model Changes
```bash
# 1. Update your SQLAlchemy models in apps/api/app/models/
# 2. Run migration creation (Alembic will detect changes)
make migrate-make name=add_new_column
```

### Manual Migration
```bash
# Create empty migration file
make migrate-make name=custom_changes

# Edit the generated file in apps/api/alembic/versions/
# Add your upgrade() and downgrade() logic
```

### Example Migration File

```python
"""add email_verified column

Revision ID: 002_add_email_verified
Revises: 001_add_owned_org_id
Create Date: 2025-10-22 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision: str = '002_add_email_verified'
down_revision: Union[str, None] = '001_add_owned_org_id'

def upgrade() -> None:
    op.add_column('users', 
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false')
    )
    op.create_index('ix_users_email_verified', 'users', ['email_verified'])

def downgrade() -> None:
    op.drop_index('ix_users_email_verified', table_name='users')
    op.drop_column('users', 'email_verified')
```

## Best Practices

1. **Always test migrations locally first**
   ```bash
   make migrate        # Apply migration
   make migrate-rollback  # Test rollback
   make migrate        # Re-apply
   ```

2. **Review auto-generated migrations**
   - Alembic auto-detects model changes, but review the generated SQL
   - Edit migration file if needed before running

3. **Never edit applied migrations**
   - Create a new migration instead
   - Keep migration history intact

4. **Use descriptive names**
   ```bash
   # Good
   make migrate-make name=add_user_avatar_field
   
   # Bad
   make migrate-make name=update
   ```

5. **Include rollback logic**
   - Always implement `downgrade()` function
   - Test rollback before deploying

## Troubleshooting

### Migration fails with "table already exists"
```bash
# Mark current state as migrated without running SQL
cd apps/api
alembic stamp head
```

### Reset all migrations (⚠️ WARNING: Deletes all data)
```bash
# Drop all tables
# Then run
make migrate
```

### Check Alembic version table
```sql
SELECT * FROM alembic_version;
```

## Environment Variables

Migrations use these environment variables from your `.env` file:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=viral_clip_ai
DB_USER=postgres
DB_PASSWORD=your_password
```

Make sure these are set correctly before running migrations.

## Production Deployment

For production deployments:

```bash
# 1. Backup database first!
pg_dump -U postgres viral_clip_ai > backup.sql

# 2. Run migrations
make migrate

# 3. Verify
make migrate-status
```

## Related Documentation

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://www.sqlalchemy.org/)
- [Database Schema](../../docs/31-data-model.md)
