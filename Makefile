SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE ?= docker compose
ENV_FILE := .env
# Production adds docker-compose.prod.yml: no published database ports, resource
# limits, named media volume, and the production Gunicorn config.
PROD_COMPOSE ?= $(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml
BACKUP_DIR ?= $(CURDIR)/backups

.PHONY: help install check-env build up repair down stop logs migrate makemigrations migrations-check \
	shell superuser token refresh-token backfill-profiles test test-unit test-integration lint format \
	check schema collectstatic clean prod-build prod-up prod-down prod-logs prod-release backup-db \
	restore-db check-deploy

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

migrations-check: ## Verify model changes have committed migrations
	@hatch run default:python manage.py makemigrations --check --dry-run

shell: check-env ## Open the Django shell inside the web container
	$(COMPOSE) exec web python manage.py shell

superuser: check-env ## Create an administrative user
	$(COMPOSE) exec web python manage.py createsuperuser

token: check-env ## Generate a JWT access and refresh token for a user
	@read -p "Email: " email; \
	$(COMPOSE) exec web python manage.py shell -c "\
from django.contrib.auth import get_user_model;\
from rest_framework_simplejwt.tokens import RefreshToken;\
User = get_user_model();\
user = User.objects.get(email='$$email');\
refresh = RefreshToken.for_user(user);\
print('ACCESS TOKEN:');\
print(str(refresh.access_token));\
print('REFRESH TOKEN:');\
print(str(refresh));\
"

refresh-token: check-env ## Generate a new access token from a refresh token
	@read -p "Refresh token: " token; \
	$(COMPOSE) exec web python manage.py shell -c "\
from rest_framework_simplejwt.tokens import RefreshToken;\
refresh = RefreshToken('$$token');\
print('NEW ACCESS TOKEN:');\
print(str(refresh.access_token));\
"

backfill-profiles: check-env ## Provision profiles for users missing one inside the web container
	$(COMPOSE) exec web python manage.py backfill_profiles

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

schema: ## Validate and generate the OpenAPI schema
	@hatch run default:python manage.py spectacular --file /tmp/budget-tracker-schema.yml --validate

collectstatic: check-env ## Collect static assets inside the web container
	$(COMPOSE) exec web python manage.py collectstatic --noinput

# --- Production (docker-compose.yml + docker-compose.prod.yml) --------------

prod-build: check-env ## Build the runtime images for the production stack
	$(PROD_COMPOSE) build

prod-up: check-env ## Start the hardened production stack
	$(PROD_COMPOSE) up -d --remove-orphans

prod-down: ## Stop the production stack (volumes are preserved)
	$(PROD_COMPOSE) down

check-deploy: ## Run Django's deployment checks against the real production environment
	$(PROD_COMPOSE) run --rm web python manage.py check --deploy

prod-logs: ## Follow the production stack logs
	$(PROD_COMPOSE) logs --follow --tail=100

prod-release: check-env ## Build, run release jobs, then start the production stack
	$(PROD_COMPOSE) build
	$(PROD_COMPOSE) run --rm web python manage.py migrate --noinput
	$(PROD_COMPOSE) run --rm web python manage.py collectstatic --noinput
	$(PROD_COMPOSE) up -d --remove-orphans

backup-db: ## Write a timestamped pg_dump into BACKUP_DIR (default ./backups) and prune old ones
	BACKUP_DIR=$(BACKUP_DIR) ./scripts/backup_db.sh

restore-db: ## Restore a dump after validating it: make restore-db FILE=backups/backup_*.dump [ARGS='--dry-run'|'--yes']
	@test -n "$(FILE)" || { echo "Usage: make restore-db FILE=<dump> [ARGS='--dry-run']"; exit 1; }
	@BACKUP_DIR=$(BACKUP_DIR) ./scripts/restore_db.sh $(ARGS) "$(FILE)"

clean: ## Remove local caches and build artifacts
	@find . -type d -name __pycache__ -prune -exec rm -rf {} +
	@rm -rf .coverage .hatch .mypy_cache .pytest_cache .ruff_cache dist htmlcov
