SHELL = /bin/bash -o pipefail

# A failed recipe must not leave a half-written tar that later looks up to date.
.DELETE_ON_ERROR:

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
PYTHON_PATHS = $(PACKAGE_NAME) $(TEST_PATH) $(REPO_ROOT)/docs/tools $(REPO_ROOT)/.claude/hooks
BUILD_PATH   = $(REPO_ROOT)/dist

# Docker / infra (activate the Docker section below once infra/ exists).
COMPOSE_FILE = $(REPO_ROOT)/infra/compose.yaml
ENV_FILE     = $(REPO_ROOT)/infra/.env

# The Fuseki test image: built from the compose file and the fuseki/ files next to it, saved as a
# tar (CI caches the tar).
FUSEKI_COMPOSE   = $(REPO_ROOT)/rdf_persistence/testkit/containers/compose.yaml
FUSEKI_IMAGE_TAR = $(REPO_ROOT)/temp/fuseki-image.tar

# Coverage flags — appended only in coverage-aware targets, never in pytest.ini.
# `make test-containers` overrides the floor with --cov-fail-under=0 (PD-16).
COV_FLAGS = --cov=$(PACKAGE_NAME) \
            --cov-report=term-missing \
            --cov-report=xml:$(REPO_ROOT)/coverage.xml \
            --cov-fail-under=80

# The unit lane never collects the container tests, so it runs without testcontainers (PD-16).
UNIT_LANE = --ignore=$(TEST_PATH)/integration --ignore=$(TEST_PATH)/e2e

# The tests `make profile-tests` times; narrow it, e.g. to the lane without the slow tests.
PROFILE_MARK ?= unit or feature

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
.PHONY: install-uv install lock generate check-freshness check-generated refresh-snapshot refresh-golden build

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

TOY_PROJECT = tests/fixtures/library/pyproject.toml
GENERATED_GLOBS = ':(glob)**/generated/**'

generate: ## Regenerate everything from LinkML: the toolkit's own schemas (metamodel, service, generation) and the toy library
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Generating from LinkML$(END_BUILD_PRINT)"
	@ uv run rp-generate
	@ uv run rp-generate --project $(TOY_PROJECT)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Generated$(END_BUILD_PRINT)"

check-freshness: ## rp-generate --check on both projects: lint, checks, and the manifest comparison (PD-26)
	@ uv run rp-generate --check
	@ uv run rp-generate --check --project $(TOY_PROJECT)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Generated code matches its sources$(END_BUILD_PRINT)"

check-generated: generate ## Regenerate and fail if the result differs from what is committed (PD-19)
	@ git diff --exit-code --stat -- $(GENERATED_GLOBS)
	@ git ls-files --others --exclude-standard -- $(GENERATED_GLOBS) | grep . && exit 1 || true
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Generated output is fresh$(END_BUILD_PRINT)"

refresh-snapshot: ## Rewrite the reviewed model-shape snapshot after a deliberate model change (review the diff)
	@ RP_REFRESH_SNAPSHOT=1 uv run pytest tests/unit/generation/test_shape_snapshot.py -q

refresh-golden: ## Rewrite the golden files of schemas that are not the toy (the toy's golden is the committed tree: make generate)
	@ RP_REFRESH_GOLDEN=1 uv run pytest tests/unit/generation -k "ext_" -q

build: generate ## Build the package distribution (generates first)
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
	@ uv run ruff format $(PYTHON_PATHS)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Format complete$(END_BUILD_PRINT)"

lint-fix: ## Run Ruff checks with auto-fix
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running Ruff auto-fix$(END_BUILD_PRINT)"
	@ uv run ruff check --fix $(PYTHON_PATHS)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Ruff auto-fix complete$(END_BUILD_PRINT)"

pre-commit: ## Run pre-commit hooks on all files
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running pre-commit hooks$(END_BUILD_PRINT)"
	@ uv run pre-commit run --all-files
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Pre-commit hooks passed$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Validation — non-mutating targets
#-----------------------------------------------------------------------------
.PHONY: format-check lint typecheck typecheck-generated typecheck-ts typecheck-openapi-ts check-architecture test test-unit test-feature test-containers fuseki-image test-e2e test-perf test-fast test-changed profile-tests

format-check: ## Check formatting with Ruff, without changing files
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Checking formatting$(END_BUILD_PRINT)"
	@ uv run ruff format --check $(PYTHON_PATHS)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Formatting is clean$(END_BUILD_PRINT)"

lint: ## Run Ruff linting checks
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running Ruff checks$(END_BUILD_PRINT)"
	@ uv run ruff check $(PYTHON_PATHS)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Ruff checks passed$(END_BUILD_PRINT)"

typecheck: ## Run mypy type checks
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running mypy$(END_BUILD_PRINT)"
	@ uv run mypy $(PACKAGE_NAME)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Type checks passed$(END_BUILD_PRINT)"

# The Python folders of every [[tool.rp-generate]] entry, so a new entry is checked without an edit here.
# A folder inside another listed folder (the service module's) is checked with its parent.
GENERATED_PY = $(shell { uv run rp-generate --list-python-folders; uv run rp-generate --list-python-folders --project $(TOY_PROJECT); } | sort | awk '{ for (i in kept) if (index($$0, kept[i] "/") == 1) next; kept[NR] = $$0; print }')
TOY_TS = $(wildcard tests/fixtures/library/web/src/domain/generated/*.ts)

typecheck-generated: ## Run mypy on the generated Python only, with mypy-generated.ini (PD-27)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running mypy on generated code$(END_BUILD_PRINT)"
	@ uv run mypy --config-file mypy-generated.ini $(GENERATED_PY)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Generated code type checks passed$(END_BUILD_PRINT)"

typecheck-ts: ## Run tsc --noEmit --strict (typescript 5.9.3) on the generated TypeScript (needs Node)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running tsc on generated TypeScript$(END_BUILD_PRINT)"
	@ npx -y -p typescript@5.9.3 tsc --noEmit --strict $(TOY_TS)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Generated TypeScript type checks passed$(END_BUILD_PRINT)"

typecheck-openapi-ts: ## Run openapi-typescript (7.13.0) on the toy service's OpenAPI document, then tsc --strict on the result (needs Node)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running tsc on the TypeScript of the OpenAPI document$(END_BUILD_PRINT)"
	@ mkdir -p temp
	@ uv run python -m tests.dump_openapi temp/toy-openapi.json
	@ npx -y openapi-typescript@7.13.0 temp/toy-openapi.json -o temp/toy-openapi.ts
	@ npx -y -p typescript@5.9.3 tsc --noEmit --strict temp/toy-openapi.ts
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) OpenAPI TypeScript type checks passed$(END_BUILD_PRINT)"

check-architecture: ## Check architecture constraints with import-linter
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Checking architecture constraints$(END_BUILD_PRINT)"
	@ uv run lint-imports --config $(REPO_ROOT)/.importlinter
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Architecture checks passed$(END_BUILD_PRINT)"

check-spec: ## Validate the OpenSpec spine (pinned CLI, strict)
	@ npx -y @fission-ai/openspec@1.4.1 validate --all --strict

test: ## Run the unit and feature tests, with the coverage floor
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running unit and feature tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) $(UNIT_LANE) -n auto -m "unit or feature" $(COV_FLAGS) --junitxml=$(REPO_ROOT)/test-results.xml
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Unit and feature tests passed$(END_BUILD_PRINT)"

test-containers: ## Run the integration and e2e tests against Docker containers (no coverage floor)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running container tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) -m "integration or e2e" $(COV_FLAGS) --cov-report=xml:$(REPO_ROOT)/coverage-containers.xml --cov-fail-under=0 --junitxml=$(REPO_ROOT)/test-results-containers.xml
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Container tests passed$(END_BUILD_PRINT)"

$(FUSEKI_IMAGE_TAR): $(FUSEKI_COMPOSE) $(shell find $(dir $(FUSEKI_COMPOSE))fuseki -type f)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Building the Fuseki image$(END_BUILD_PRINT)"
	@ mkdir -p $(dir $@)
	@ docker compose -f $(FUSEKI_COMPOSE) build fuseki && docker save -o $@ $$(docker compose -f $(FUSEKI_COMPOSE) config --images fuseki)

fuseki-image: $(FUSEKI_IMAGE_TAR) ## Load the Fuseki test image from its tar, building and saving the tar first when it is missing or older than its inputs
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Loading the Fuseki image$(END_BUILD_PRINT)"
	@ docker load -i $<
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Fuseki image ready$(END_BUILD_PRINT)"

test-unit: ## Run the unit tests in parallel, with the 80 % coverage floor (CI job "unit")
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running unit tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) $(UNIT_LANE) -n auto -m "unit" $(COV_FLAGS) --junitxml=$(REPO_ROOT)/test-results.xml
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Unit tests passed$(END_BUILD_PRINT)"

test-feature: ## Run the BDD feature tests in parallel, with a 50 % coverage floor (CI job "feature")
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running feature tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) $(UNIT_LANE) -n auto -m "feature" $(COV_FLAGS) --cov-report=xml:$(REPO_ROOT)/coverage-feature.xml --cov-fail-under=50
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Feature tests passed$(END_BUILD_PRINT)"

test-perf: ## Run the wall-clock budget tests alone (no coverage, no xdist); not part of check-all
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running perf tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH)/perf -m perf
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Perf tests passed$(END_BUILD_PRINT)"

# Developer lanes (test-lanes): no coverage; the floors are checked by test, test-unit, test-feature.
test-fast: ## Run the unit and feature tests not marked slow, in parallel, without coverage (developer lane)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running the fast unit and feature tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) $(UNIT_LANE) -n auto -m "(unit or feature) and not slow"
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Fast tests passed$(END_BUILD_PRINT)"

test-changed: ## Run the tests of the files changed against BASE (default develop), slow ones included, without coverage; PYTEST_N overrides the worker count
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running the tests of the changed files$(END_BUILD_PRINT)"
	@ args=$$(uv run python -m tests.changed); status=$$?; \
	  if [ $$status -eq 3 ]; then $(MAKE) --no-print-directory test-fast; \
	  elif [ $$status -ne 0 ]; then exit $$status; \
	  elif [ -n "$$args" ]; then set -f; IFS=$$'\n'; \
	    uv run pytest $$args $(UNIT_LANE) -m "unit or feature" \
	    && echo -e "$(BUILD_PRINT)$(ICON_DONE) Changed-file tests passed$(END_BUILD_PRINT)"; fi

profile-tests: ## Print the 15 slowest unit and feature tests, set-up and call apart, without coverage (PROFILE_MARK narrows)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Profiling the unit and feature tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) $(UNIT_LANE) -n auto -q -p no:randomly -m "$(PROFILE_MARK)" --durations=15
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Profile complete$(END_BUILD_PRINT)"

test-e2e: ## Run end-to-end tests only
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running e2e tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) -m "e2e"
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) E2e tests passed$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Groups — one per CI job (.github/workflows/ci.yaml), each runnable alone
#-----------------------------------------------------------------------------
.PHONY: check-spec check-style check-types check-spec-docs check-generation check-quality check-all

check-style: format-check lint clean-code ## Formatting, lint and the complexity thresholds (CI job "style")
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Style checks passed$(END_BUILD_PRINT)"

check-types: typecheck typecheck-generated typecheck-ts typecheck-openapi-ts ## mypy on the code and the generated code, tsc on the generated TypeScript and on that of the OpenAPI document (CI job "types")
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Type checks passed$(END_BUILD_PRINT)"

check-spec-docs: check-spec check-docs ## The OpenSpec spine and the docs checks (CI job "spec, docs and generation")
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Spec and docs checks passed$(END_BUILD_PRINT)"

check-generation: check-freshness check-generated ## Generated code is fresh and regenerates unchanged (CI job "spec, docs and generation")
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Generation checks passed$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Aggregates — run locally before a PR
#-----------------------------------------------------------------------------
check-quality: check-style check-types check-architecture check-spec-docs check-freshness ## All static checks: the groups above, without the slower check-generated
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) All quality checks passed$(END_BUILD_PRINT)"

check-all: check-quality test ## Full suite: quality + unit and feature tests (containers, locally only: make test-containers)
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Full verification suite passed$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Reports (opt-in)
# Note: radon (and xenon, which uses it) cannot read a pyproject.toml whose [[tool.*]] is an array of
# tables (the rp-generate entries), so they run from inside the package, away from it.
#-----------------------------------------------------------------------------
.PHONY: coverage-report quality-report

coverage-report: ## Generate HTML coverage report in reports/
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Generating coverage report$(END_BUILD_PRINT)"
	@ mkdir -p $(REPO_ROOT)/reports
	@ uv run pytest $(TEST_PATH) $(UNIT_LANE) $(COV_FLAGS) --cov-report=html:$(REPO_ROOT)/reports/htmlcov -m "unit or feature"
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Coverage report at reports/htmlcov/index.html$(END_BUILD_PRINT)"

quality-report: ## Generate Radon quality report in reports/
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Generating quality report$(END_BUILD_PRINT)"
	@ mkdir -p $(REPO_ROOT)/reports
	@ uv run --directory $(PACKAGE_NAME) radon cc . -s -a -j > $(REPO_ROOT)/reports/complexity.json
	@ uv run --directory $(PACKAGE_NAME) radon mi . -s -j > $(REPO_ROOT)/reports/maintainability.json
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Quality reports at reports/$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Clean code analysis (clean-code runs in check-style)
#-----------------------------------------------------------------------------
.PHONY: complexity maintainability clean-code

complexity: ## Radon cyclomatic complexity analysis
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Checking cyclomatic complexity$(END_BUILD_PRINT)"
	@ uv run --directory $(PACKAGE_NAME) radon cc . -s -a
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Complexity analysis complete$(END_BUILD_PRINT)"

maintainability: ## Radon maintainability index
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Checking maintainability index$(END_BUILD_PRINT)"
	@ uv run --directory $(PACKAGE_NAME) radon mi . -s
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Maintainability analysis complete$(END_BUILD_PRINT)"

clean-code: ## Xenon threshold checks
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running Xenon threshold checks$(END_BUILD_PRINT)"
	@ uv run --directory $(PACKAGE_NAME) xenon . --exclude '*/generated/*' --max-absolute B --max-modules A --max-average A
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

check-docs: ## No consumer terms in architecture pages, the package or the tests; every page in the nav
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
	@ rm -rf $(REPO_ROOT)/coverage.xml $(REPO_ROOT)/coverage-containers.xml $(REPO_ROOT)/test-results.xml $(REPO_ROOT)/test-results-containers.xml $(REPO_ROOT)/.coverage
	@ rm -rf $(REPO_ROOT)/*.egg-info
	@ uv run ruff clean 2>/dev/null || true
	@ find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@ find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Clean complete$(END_BUILD_PRINT)"
