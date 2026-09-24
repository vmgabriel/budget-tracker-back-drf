SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE ?= docker compose
ENV_FILE := .env

.PHONY: help install check-env build up repair down stop logs migrate makemigrations shell superuser \
	test test-unit test-integration lint format check clean

help: ## Show the available commands
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make <target>\n\nTargets:\n"} \
		/^[a-zA-Z_-]+:.*?##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Create .env from the checked-in template
	@test ! -e $(ENV_FILE) || { echo "$(ENV_FILE) already exists; leaving it unchanged."; exit 0; }
	@cp .env.example $(ENV_FILE)
	@echo "Created $(ENV_FILE). Replace DJANGO_SECRET_KEY before production use."

check-env: ## Ensure the local environment file exists
	@test -f $(ENV_FILE) || { echo "Missing $(ENV_FILE). Run 'make install' first."; exit 1; }

build: check-env ## Build all Docker images
	$(COMPOSE) build

up: check-env ## Build and start the complete application
	$(COMPOSE) up --build -d

repair: check-env ## Recreate containers and apply migrations (preserves volumes)
	$(COMPOSE) down --remove-orphans
	$(COMPOSE) up --build -d
	$(COMPOSE) exec web python manage.py migrate --noinput

down: ## Stop and remove the application containers
	$(COMPOSE) down

stop: ## Stop the application without removing containers
	$(COMPOSE) stop

logs: ## Follow application and worker logs
	$(COMPOSE) logs --follow --tail=100

migrate: check-env ## Apply database migrations inside the web container
	$(COMPOSE) exec web python manage.py migrate

makemigrations: check-env ## Create new Django migrations
	$(COMPOSE) exec web python manage.py makemigrations

shell: check-env ## Open the Django shell inside the web container
	$(COMPOSE) exec web python manage.py shell

superuser: check-env ## Create an administrative user
	$(COMPOSE) exec web python manage.py createsuperuser

test-unit: ## Run database-free unit tests locally with Hatch
	@command -v hatch >/dev/null 2>&1 || { echo "Hatch is required: https://hatch.pypa.io/latest/install/"; exit 1; }
	@hatch run test:pytest src/tests/unit -m unit

test-integration: check-env ## Run integration tests against the isolated Docker test database
	$(COMPOSE) up -d db redis
	$(COMPOSE) build tester
	$(COMPOSE) run --rm tester

test: test-unit test-integration ## Run all test layers

lint: ## Run Ruff, Black, and mypy through Hatch
	@hatch run lint:ruff check .
	@hatch run lint:black --check .
	@hatch run lint:mypy src

format: ## Auto-fix lint findings and format Python files
	@hatch run lint:ruff check --fix .
	@hatch run lint:black .

check: ## Run Django's deployment checks with Hatch
	@hatch run default:python manage.py check

clean: ## Remove local caches and build artifacts
	@find . -type d -name __pycache__ -prune -exec rm -rf {} +
	@rm -rf .coverage .hatch .mypy_cache .pytest_cache .ruff_cache dist htmlcov
