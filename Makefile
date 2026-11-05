SHELL = /bin/bash -o pipefail

BUILD_PRINT     = \e[1;34m
END_BUILD_PRINT = \e[0m

ICON_DONE     = [done]
ICON_ERROR    = [x]
ICON_WARNING  = [!]
ICON_PROGRESS = [-]

# No-src layout: the top-level package lives at the repo root.
REPO_ROOT    = $(shell pwd)
PACKAGE_NAME = rdf_persistence
TEST_PATH    = $(REPO_ROOT)/tests
BUILD_PATH   = $(REPO_ROOT)/dist

# Docker / infra (activate the Docker section below once infra/ exists).
COMPOSE_FILE = $(REPO_ROOT)/infra/compose.yaml
ENV_FILE     = $(REPO_ROOT)/infra/.env

# Coverage flags — appended only in coverage-aware targets, never in pytest.ini.
# `make test-containers` overrides the floor with --cov-fail-under=0 (PD-16).
COV_FLAGS = --cov=$(PACKAGE_NAME) \
            --cov-report=term-missing \
            --cov-report=xml:$(REPO_ROOT)/coverage.xml \
            --cov-fail-under=80

.DEFAULT_GOAL := help

#-----------------------------------------------------------------------------
# Help — auto-generated from `## ` comments on targets.
#-----------------------------------------------------------------------------
.PHONY: help
help: ## Display available targets
	@ echo -e "$(BUILD_PRINT)Available targets:$(END_BUILD_PRINT)"
	@ grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

#-----------------------------------------------------------------------------
# Install / build (mutating)
#-----------------------------------------------------------------------------
.PHONY: install-uv install lock build

install-uv: ## Install uv if not present
	@ command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

install: install-uv ## Install project dependencies (all groups and extras; does NOT lock)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Installing dependencies$(END_BUILD_PRINT)"
	@ uv sync --all-extras
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Dependencies installed$(END_BUILD_PRINT)"

lock: ## Update uv.lock
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Locking dependencies$(END_BUILD_PRINT)"
	@ uv lock
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Lock file updated$(END_BUILD_PRINT)"

build: ## Build the package distribution
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Building package$(END_BUILD_PRINT)"
	@ uv build
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Package built successfully$(END_BUILD_PRINT)"

run: ## Run the application (python -m <package>; tailor per archetype)
	@ uv run python -m $(PACKAGE_NAME)

#-----------------------------------------------------------------------------
# Code quality — mutating targets
#-----------------------------------------------------------------------------
.PHONY: format lint-fix pre-commit

format: ## Format code with Ruff
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Formatting code$(END_BUILD_PRINT)"
	@ uv run ruff format $(PACKAGE_NAME) $(TEST_PATH)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Format complete$(END_BUILD_PRINT)"

lint-fix: ## Run Ruff checks with auto-fix
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running Ruff auto-fix$(END_BUILD_PRINT)"
	@ uv run ruff check --fix $(PACKAGE_NAME) $(TEST_PATH)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Ruff auto-fix complete$(END_BUILD_PRINT)"

pre-commit: ## Run pre-commit hooks on all files
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running pre-commit hooks$(END_BUILD_PRINT)"
	@ uv run pre-commit run --all-files
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Pre-commit hooks passed$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Validation — non-mutating targets
#-----------------------------------------------------------------------------
.PHONY: lint typecheck check-architecture test test-unit test-feature test-containers test-e2e

lint: ## Run Ruff linting checks
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running Ruff checks$(END_BUILD_PRINT)"
	@ uv run ruff check $(PACKAGE_NAME) $(TEST_PATH)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Ruff checks passed$(END_BUILD_PRINT)"

typecheck: ## Run mypy type checks
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running mypy$(END_BUILD_PRINT)"
	@ uv run mypy $(PACKAGE_NAME)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Type checks passed$(END_BUILD_PRINT)"

check-architecture: ## Check architecture constraints with import-linter
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Checking architecture constraints$(END_BUILD_PRINT)"
	@ uv run lint-imports --config $(REPO_ROOT)/.importlinter
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Architecture checks passed$(END_BUILD_PRINT)"

check-spec: ## Validate the OpenSpec spine (pinned CLI, strict)
	@ npx -y @fission-ai/openspec@1.4.1 validate --all --strict

test: ## Run the unit and feature tests, with the coverage floor
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running unit and feature tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) -m "unit or feature" $(COV_FLAGS) --junitxml=$(REPO_ROOT)/test-results.xml
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Unit and feature tests passed$(END_BUILD_PRINT)"

test-containers: ## Run the integration and e2e tests against Docker containers (no coverage floor)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running container tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) -m "integration or e2e" $(COV_FLAGS) --cov-fail-under=0 --junitxml=$(REPO_ROOT)/test-results-containers.xml
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Container tests passed$(END_BUILD_PRINT)"

test-unit: ## Run unit tests only
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running unit tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) -m "unit"
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Unit tests passed$(END_BUILD_PRINT)"

test-feature: ## Run BDD feature tests only
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running feature tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) -m "feature"
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Feature tests passed$(END_BUILD_PRINT)"

test-e2e: ## Run end-to-end tests only
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running e2e tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) -m "e2e"
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) E2e tests passed$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Aggregates
#-----------------------------------------------------------------------------
.PHONY: check-spec check-quality check-all ci-quick ci-full

check-quality: lint typecheck check-architecture check-spec ## Static checks: lint + typecheck + architecture
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) All quality checks passed$(END_BUILD_PRINT)"

check-all: check-quality test ## Full suite: quality + unit and feature tests (containers: make test-containers)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Full verification suite passed$(END_BUILD_PRINT)"

ci-quick: check-quality test-unit ## CI fast: quality + unit tests
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) CI quick checks passed$(END_BUILD_PRINT)"

ci-full: check-all clean-code ## CI full: quality + unit and feature tests + clean-code
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) CI full checks passed$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Reports (opt-in)
#-----------------------------------------------------------------------------
.PHONY: coverage-report quality-report

coverage-report: ## Generate HTML coverage report in reports/
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Generating coverage report$(END_BUILD_PRINT)"
	@ mkdir -p $(REPO_ROOT)/reports
	@ uv run pytest $(TEST_PATH) $(COV_FLAGS) --cov-report=html:$(REPO_ROOT)/reports/htmlcov -m "unit or feature"
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Coverage report at reports/htmlcov/index.html$(END_BUILD_PRINT)"

quality-report: ## Generate Radon quality report in reports/
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Generating quality report$(END_BUILD_PRINT)"
	@ mkdir -p $(REPO_ROOT)/reports
	@ uv run radon cc $(PACKAGE_NAME) -s -a -j > $(REPO_ROOT)/reports/complexity.json
	@ uv run radon mi $(PACKAGE_NAME) -s -j > $(REPO_ROOT)/reports/maintainability.json
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Quality reports at reports/$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Clean code analysis (separate from check-quality)
#-----------------------------------------------------------------------------
.PHONY: complexity maintainability clean-code

complexity: ## Radon cyclomatic complexity analysis
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Checking cyclomatic complexity$(END_BUILD_PRINT)"
	@ uv run radon cc $(PACKAGE_NAME) -s -a
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Complexity analysis complete$(END_BUILD_PRINT)"

maintainability: ## Radon maintainability index
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Checking maintainability index$(END_BUILD_PRINT)"
	@ uv run radon mi $(PACKAGE_NAME) -s
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Maintainability analysis complete$(END_BUILD_PRINT)"

clean-code: ## Xenon threshold checks
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running Xenon threshold checks$(END_BUILD_PRINT)"
	@ uv run xenon $(PACKAGE_NAME) --max-absolute B --max-modules A --max-average A
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Clean code checks passed$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Docs (Antora) — see references/antora-docs.md. Remove this block if --no-docs.
#-----------------------------------------------------------------------------
.PHONY: install-antora build-docs preview-docs clean-docs check-docs

DOCS_DIR  = $(REPO_ROOT)/docs
DOCS_SITE = $(DOCS_DIR)/build/site
DOCS_PORT ?= 8081

install-antora: ## Install the Antora doc toolchain (npm) in docs/
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Installing Antora toolchain$(END_BUILD_PRINT)"
	@ cd $(DOCS_DIR) && npm install

build-docs: ## Build the documentation site to docs/build/site/
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Building docs$(END_BUILD_PRINT)"
	@ cd $(DOCS_DIR) && npx antora --fetch antora-playbook.local.yml
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Docs built at $(DOCS_SITE)$(END_BUILD_PRINT)"

preview-docs: build-docs ## Build then serve docs at http://localhost:$(DOCS_PORT) (8081, beside MWB2's 8080)
	@ python3 -m http.server --directory $(DOCS_SITE) $(DOCS_PORT)

check-docs: ## Check the docs: no consumer terms in architecture pages, every page in the nav
	@ python3 -I docs/tools/check_docs.py

clean-docs: ## Remove built docs + node_modules
	@ rm -rf $(DOCS_DIR)/build $(DOCS_DIR)/node_modules

#-----------------------------------------------------------------------------
# Docker / infra — see references/ci-and-infra.md. Remove this block if --no-infra.
# .env lives at infra/.env; compose targets pass --env-file explicitly (D11).
#-----------------------------------------------------------------------------
.PHONY: check-env up down rebuild logs watch

check-env:
	@ test -f $(ENV_FILE) || (echo -e "$(ICON_ERROR) Missing $(ENV_FILE). Run: cp infra/.env.example infra/.env" && exit 1)

up: check-env ## Start services (docker compose up -d)
	@ docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d

down: check-env ## Stop services (docker compose down)
	@ docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down

rebuild: check-env ## Rebuild and start services
	@ docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d --build

logs: check-env ## Follow service logs
	@ docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f

watch: check-env ## Start services with file watching (hot-reload)
	@ docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) watch

#-----------------------------------------------------------------------------
# Utilities
#-----------------------------------------------------------------------------
.PHONY: clean

clean: ## Remove build artifacts and caches
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Cleaning build artifacts and caches$(END_BUILD_PRINT)"
	@ rm -rf $(BUILD_PATH) $(REPO_ROOT)/reports
	@ rm -rf $(REPO_ROOT)/.pytest_cache $(REPO_ROOT)/.mypy_cache $(REPO_ROOT)/.ruff_cache
	@ rm -rf $(REPO_ROOT)/.import_linter_cache
	@ rm -rf $(REPO_ROOT)/coverage.xml $(REPO_ROOT)/test-results.xml $(REPO_ROOT)/test-results-containers.xml $(REPO_ROOT)/.coverage
	@ rm -rf $(REPO_ROOT)/*.egg-info
	@ uv run ruff clean 2>/dev/null || true
	@ find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@ find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Clean complete$(END_BUILD_PRINT)"
