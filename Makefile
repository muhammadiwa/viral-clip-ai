# Viral Clip AI — Environment-aware Makefile

DOCKER_CMD := ./docker-wrapper.sh
COMPOSE_CMD := $(DOCKER_CMD) compose
DEV_COMPOSE_FILE := docker-compose.dev.yml
PROD_COMPOSE_FILE := docker-compose.prod.yml
DEV_ENV_FILE := .env
DEV_ENV_TEMPLATE := .env.development
PROD_ENV_FILE := .env.production
PROD_ENV_TEMPLATE := .env.production.sample
API_DIR := apps/api

.PHONY: \
	dev-setup dev-build dev-up dev-down dev-restart dev-logs dev-status dev-clean \
	prod-setup prod-build prod-up prod-down prod-logs prod-status prod-clean \
	env-check migrate migrate-rollback migrate-status migrate-history migrate-make \
	help

dev-setup:
	@echo "Setting up development environment..."
	@if [ ! -f $(DEV_ENV_TEMPLATE) ]; then \
		echo "❌ $(DEV_ENV_TEMPLATE) is missing. Pull the latest repository."; \
		exit 1; \
	fi
	@if [ ! -f $(DEV_ENV_FILE) ]; then \
		cp $(DEV_ENV_TEMPLATE) $(DEV_ENV_FILE); \
		echo "✅ Copied $(DEV_ENV_TEMPLATE) -> $(DEV_ENV_FILE)"; \
	else \
		echo "ℹ️  $(DEV_ENV_FILE) already exists; skipping copy."; \
	fi
	@echo "📝 Update $(DEV_ENV_FILE) with any local overrides."

prod-setup:
	@echo "Preparing production environment file..."
	@if [ ! -f $(PROD_ENV_TEMPLATE) ]; then \
		echo "❌ $(PROD_ENV_TEMPLATE) is missing. Pull the latest repository."; \
		exit 1; \
	fi
	@if [ ! -f $(PROD_ENV_FILE) ]; then \
		cp $(PROD_ENV_TEMPLATE) $(PROD_ENV_FILE); \
		echo "✅ Copied $(PROD_ENV_TEMPLATE) -> $(PROD_ENV_FILE)"; \
	else \
		echo "ℹ️  $(PROD_ENV_FILE) already exists; skipping copy."; \
	fi
	@echo "🔐 Populate $(PROD_ENV_FILE) with secrets from your secret manager."

dev-build:
	@echo "Building development images..."
	@if [ ! -f $(DEV_ENV_FILE) ]; then \
		echo "❌ Missing $(DEV_ENV_FILE). Run 'make dev-setup' first."; \
		exit 1; \
	fi
	@$(COMPOSE_CMD) --env-file $(DEV_ENV_FILE) -f $(DEV_COMPOSE_FILE) build

dev-up:
	@echo "Starting development environment..."
	@if [ ! -f $(DEV_ENV_FILE) ]; then \
		echo "❌ Missing $(DEV_ENV_FILE). Run 'make dev-setup' first."; \
		exit 1; \
	fi
	@$(COMPOSE_CMD) --env-file $(DEV_ENV_FILE) -f $(DEV_COMPOSE_FILE) up -d
	@$(COMPOSE_CMD) --env-file $(DEV_ENV_FILE) -f $(DEV_COMPOSE_FILE) ps

dev-down:
	@echo "Stopping development environment..."
	@if [ ! -f $(DEV_ENV_FILE) ]; then \
		echo "⚠️  $(DEV_ENV_FILE) not found; continuing with default shell env."; \
	fi
	@$(COMPOSE_CMD) --env-file $(DEV_ENV_FILE) -f $(DEV_COMPOSE_FILE) down

dev-restart: dev-down dev-up


dev-logs:
	@$(COMPOSE_CMD) --env-file $(DEV_ENV_FILE) -f $(DEV_COMPOSE_FILE) logs -f


dev-status:
	@$(COMPOSE_CMD) --env-file $(DEV_ENV_FILE) -f $(DEV_COMPOSE_FILE) ps


dev-clean:
	@echo "Removing development containers, volumes, and orphans..."
	@$(COMPOSE_CMD) --env-file $(DEV_ENV_FILE) -f $(DEV_COMPOSE_FILE) down -v --remove-orphans


prod-build:
	@echo "Building production images..."
	@if [ ! -f $(PROD_ENV_FILE) ]; then \
		echo "❌ Missing $(PROD_ENV_FILE). Run 'make prod-setup' and fill in secrets."; \
		exit 1; \
	fi
	@$(COMPOSE_CMD) --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) build


prod-up:
	@echo "Starting production stack..."
	@if [ ! -f $(PROD_ENV_FILE) ]; then \
		echo "❌ Missing $(PROD_ENV_FILE). Run 'make prod-setup' and fill in secrets."; \
		exit 1; \
	fi
	@$(COMPOSE_CMD) --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) up -d
	@$(COMPOSE_CMD) --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) ps


prod-down:
	@echo "Stopping production stack..."
	@if [ ! -f $(PROD_ENV_FILE) ]; then \
		echo "⚠️  $(PROD_ENV_FILE) not found; continuing with default shell env."; \
	fi
	@$(COMPOSE_CMD) --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) down


prod-logs:
	@$(COMPOSE_CMD) --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) logs -f


prod-status:
	@$(COMPOSE_CMD) --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) ps


prod-clean:
	@echo "Removing production containers, volumes, and orphans..."
	@$(COMPOSE_CMD) --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) down -v --remove-orphans


env-check:
	@echo "Checking environment files..."
	@if [ -f $(DEV_ENV_TEMPLATE) ]; then \
		echo "✅ $(DEV_ENV_TEMPLATE) template present."; \
	else \
		echo "❌ Missing $(DEV_ENV_TEMPLATE)."; \
	fi
	@if [ -f $(PROD_ENV_TEMPLATE) ]; then \
		echo "✅ $(PROD_ENV_TEMPLATE) template present."; \
	else \
		echo "❌ Missing $(PROD_ENV_TEMPLATE)."; \
	fi
	@if [ -f $(DEV_ENV_FILE) ]; then \
		echo "✅ $(DEV_ENV_FILE) ready."; \
	else \
		echo "⚠️  $(DEV_ENV_FILE) missing. Run 'make dev-setup'."; \
	fi
	@if [ -f $(PROD_ENV_FILE) ]; then \
		if grep -q "<" $(PROD_ENV_FILE); then \
			echo "⚠️  $(PROD_ENV_FILE) still contains placeholder values (<>)."; \
		else \
			echo "✅ $(PROD_ENV_FILE) populated."; \
		fi; \
	else \
		echo "⚠️  $(PROD_ENV_FILE) missing. Run 'make prod-setup'."; \
	fi

# Database Migration Commands
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
	@echo "Viral Clip AI — Make targets"
	@echo ""
	@echo "Development workflow:"
	@echo "  make dev-setup    # copy $(DEV_ENV_TEMPLATE) -> $(DEV_ENV_FILE)"
	@echo "  make dev-build    # build dev images"
	@echo "  make dev-up       # start dev stack"
	@echo "  make dev-logs     # tail dev logs"
	@echo "  make dev-status   # list dev containers"
	@echo "  make dev-clean    # stop & remove dev containers/volumes"
	@echo ""
	@echo "Production workflow:"
	@echo "  make prod-setup   # copy $(PROD_ENV_TEMPLATE) -> $(PROD_ENV_FILE)"
	@echo "  make prod-build   # build prod images"
	@echo "  make prod-up      # start prod stack (requires populated env)"
	@echo "  make prod-logs    # tail prod logs"
	@echo "  make prod-status  # list prod containers"
	@echo "  make prod-clean   # stop & remove prod containers/volumes"
	@echo ""
	@echo "Environment helpers:"
	@echo "  make env-check    # report env file readiness"
	@echo ""
	@echo "Database migrations (local):"
	@echo "  make migrate"
	@echo "  make migrate-rollback"
	@echo "  make migrate-status"
	@echo "  make migrate-history"
	@echo "  make migrate-make name=<migration_name>"
	@echo ""
	@echo "Example: make dev-setup && make dev-up"


.DEFAULT_GOAL := help
