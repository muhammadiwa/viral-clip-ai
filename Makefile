# Viral Clip AI - Development Makefile

DOCKER_CMD := ./docker-wrapper.sh
DEV_COMPOSE_FILE := docker-compose.dev.yml
API_DIR := apps/api

.PHONY: dev-setup dev-build dev-up dev-down dev-logs dev-status dev-clean
.PHONY: migrate migrate-rollback migrate-status migrate-history migrate-make
.PHONY: help

dev-setup:
	@echo "Setting up development environment..."
	@if [ ! -f .env ]; then cp .env.template .env; echo "✅ Created .env file"; fi
	@echo "📝 Edit .env file with your configurations"
	@echo "🚀 Then run: make dev-build && make dev-up"

dev-build:
	@echo "Building development images..."
	$(DOCKER_CMD) compose -f $(DEV_COMPOSE_FILE) build

dev-up:
	@echo "Starting development environment..."
	$(DOCKER_CMD) compose -f $(DEV_COMPOSE_FILE) up -d
	@echo "✅ Development services started!"

dev-down:
	@echo "Stopping development environment..."
	$(DOCKER_CMD) compose -f $(DEV_COMPOSE_FILE) down

dev-logs:
	$(DOCKER_CMD) compose -f $(DEV_COMPOSE_FILE) logs -f

dev-status:
	$(DOCKER_CMD) compose -f $(DEV_COMPOSE_FILE) ps

dev-clean:
	@echo "Cleaning development environment..."
	$(DOCKER_CMD) compose -f $(DEV_COMPOSE_FILE) down -v --remove-orphans

# Database Migration Commands (Laravel-style)
migrate:
	@echo "🚀 Running database migrations..."
	@cd $(API_DIR) && python migrate.py migrate

migrate-rollback:
	@echo "⏪ Rolling back last migration..."
	@cd $(API_DIR) && python migrate.py rollback

migrate-status:
	@echo "📊 Checking migration status..."
	@cd $(API_DIR) && python migrate.py status

migrate-history:
	@echo "📜 Showing migration history..."
	@cd $(API_DIR) && python migrate.py history

migrate-make:
	@if [ -z "$(name)" ]; then \
		echo "❌ Error: Migration name required"; \
		echo "Usage: make migrate-make name=your_migration_name"; \
		exit 1; \
	fi
	@echo "📝 Creating new migration: $(name)"
	@cd $(API_DIR) && python migrate.py make $(name)

help:
	@echo "Viral Clip AI - Development Commands"
	@echo ""
	@echo "Development:"
	@echo "  dev-setup  : Setup development environment"
	@echo "  dev-build  : Build development images" 
	@echo "  dev-up     : Start development services"
	@echo "  dev-down   : Stop development services"
	@echo "  dev-logs   : Show service logs"
	@echo "  dev-status : Check service status"
	@echo "  dev-clean  : Clean up everything"
	@echo ""
	@echo "Database Migrations:"
	@echo "  migrate              : Run all pending migrations"
	@echo "  migrate-rollback     : Rollback last migration"
	@echo "  migrate-status       : Show current migration status"
	@echo "  migrate-history      : Show migration history"
	@echo "  migrate-make name=X  : Create new migration"
	@echo ""
	@echo "Example:"
	@echo "  make migrate"
	@echo "  make migrate-make name=add_new_field"

.DEFAULT_GOAL := help
