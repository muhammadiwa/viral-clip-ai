#!/bin/bash
# Quick setup script for Alembic migrations

set -e

echo "🔧 Setting up Alembic migration system..."

# Check if we're in the right directory
if [ ! -f "alembic.ini" ]; then
    echo "❌ Error: Please run this script from apps/api directory"
    exit 1
fi

# Check if alembic is installed
if ! python -c "import alembic" 2>/dev/null; then
    echo "📦 Installing alembic..."
    pip install alembic==1.13.2
fi

echo "✅ Alembic migration system is ready!"
echo ""
echo "📚 Available commands:"
echo "  make migrate              - Run all pending migrations"
echo "  make migrate-rollback     - Rollback last migration"
echo "  make migrate-status       - Show current status"
echo "  make migrate-history      - Show migration history"
echo "  make migrate-make name=X  - Create new migration"
echo ""
echo "📖 For more info, see: MIGRATIONS.md"
