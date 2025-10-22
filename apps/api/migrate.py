#!/usr/bin/env python3
"""
Database migration management script.
Similar to Laravel's php artisan migrate.

Usage:
    python migrate.py migrate       # Run all pending migrations
    python migrate.py rollback      # Rollback last migration
    python migrate.py status        # Show migration status
    python migrate.py history       # Show migration history
    python migrate.py make <name>   # Create new migration
    python migrate.py upgrade <revision>   # Upgrade to specific revision
    python migrate.py downgrade <revision> # Downgrade to specific revision
"""

import sys
import os
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alembic.config import Config
from alembic import command


def get_alembic_config():
    """Get Alembic configuration."""
    # Path to alembic.ini
    alembic_ini = Path(__file__).parent / "alembic.ini"
    
    if not alembic_ini.exists():
        print(f"❌ Error: alembic.ini not found at {alembic_ini}")
        sys.exit(1)
    
    return Config(str(alembic_ini))


def migrate():
    """Run all pending migrations (upgrade to head)."""
    print("🚀 Running migrations...")
    config = get_alembic_config()
    command.upgrade(config, "head")
    print("✅ Migrations completed successfully!")


def rollback():
    """Rollback last migration (downgrade by 1)."""
    print("⏪ Rolling back last migration...")
    config = get_alembic_config()
    command.downgrade(config, "-1")
    print("✅ Rollback completed successfully!")


def status():
    """Show current migration status."""
    print("📊 Migration Status:")
    config = get_alembic_config()
    command.current(config)


def history():
    """Show migration history."""
    print("📜 Migration History:")
    config = get_alembic_config()
    command.history(config)


def make_migration(name: str):
    """Create a new migration file."""
    if not name:
        print("❌ Error: Migration name is required")
        print("Usage: python migrate.py make <migration_name>")
        sys.exit(1)
    
    print(f"📝 Creating new migration: {name}")
    config = get_alembic_config()
    command.revision(config, message=name, autogenerate=True)
    print("✅ Migration file created successfully!")


def upgrade_to(revision: str):
    """Upgrade to specific revision."""
    if not revision:
        print("❌ Error: Revision is required")
        sys.exit(1)
    
    print(f"🚀 Upgrading to revision: {revision}")
    config = get_alembic_config()
    command.upgrade(config, revision)
    print("✅ Upgrade completed successfully!")


def downgrade_to(revision: str):
    """Downgrade to specific revision."""
    if not revision:
        print("❌ Error: Revision is required")
        sys.exit(1)
    
    print(f"⏪ Downgrading to revision: {revision}")
    config = get_alembic_config()
    command.downgrade(config, revision)
    print("✅ Downgrade completed successfully!")


def show_help():
    """Show help message."""
    print(__doc__)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
    
    command_name = sys.argv[1].lower()
    
    commands = {
        'migrate': migrate,
        'rollback': rollback,
        'status': status,
        'history': history,
        'help': show_help,
        '--help': show_help,
        '-h': show_help,
    }
    
    if command_name in commands:
        commands[command_name]()
    elif command_name == 'make':
        name = sys.argv[2] if len(sys.argv) > 2 else None
        make_migration(name)
    elif command_name == 'upgrade':
        revision = sys.argv[2] if len(sys.argv) > 2 else 'head'
        upgrade_to(revision)
    elif command_name == 'downgrade':
        revision = sys.argv[2] if len(sys.argv) > 2 else '-1'
        downgrade_to(revision)
    else:
        print(f"❌ Unknown command: {command_name}")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
