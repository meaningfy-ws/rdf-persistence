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
GENERATOR_NAME = rdf_persistence_generation
TEST_PATH    = $(REPO_ROOT)/tests
PYTHON_PATHS = $(PACKAGE_NAME) $(GENERATOR_NAME) $(TEST_PATH) $(REPO_ROOT)/docs/tools $(REPO_ROOT)/.claude/hooks
BUILD_PATH   = $(REPO_ROOT)/dist

# The release version: VERSION is the one source; release-please writes it and mirrors it into
# pyproject.toml and uv.lock, and check-version fails when they drift.
VERSION = $(shell cat $(REPO_ROOT)/VERSION)

# The Fuseki test image: built from the compose file and the fuseki/ files next to it, saved as a
# tar (CI caches the tar).
FUSEKI_COMPOSE   = $(REPO_ROOT)/rdf_persistence/testkit/containers/compose.yaml
FUSEKI_IMAGE_TAR = $(REPO_ROOT)/temp/fuseki-image.tar

# Coverage flags — appended only in coverage-aware targets, never in pytest.ini.
# `make test-containers` overrides the floor with --cov-fail-under=0 (PD-16).
# The library's lanes measure `rdf_persistence` alone and the generator's lane `rdf_persistence_generation`
# alone, each against its own pyramid (generator-package PD-10). `make test-containers` measures both.
COV_FLAGS = --cov=$(PACKAGE_NAME) \
            --cov-report=term-missing \
            --cov-report=xml:$(REPO_ROOT)/coverage.xml \
            --cov-fail-under=80
GENERATOR_COV_FLAGS = --cov=$(GENERATOR_NAME) \
                      --cov-report=term-missing \
                      --cov-report=xml:$(REPO_ROOT)/coverage-generator.xml \
                      --cov-fail-under=80

# The git ref `test-changed` and `refresh-map` read the changed and renamed files against.
BASE ?= develop

# The unit lane never collects the container tests, so it runs without testcontainers (PD-16).
# The generator's e2e conftest registers the container plugin whenever a session collects it (D-27).
GENERATOR_E2E = --ignore=$(TEST_PATH)/generator/e2e
UNIT_LANE = --ignore=$(TEST_PATH)/integration --ignore=$(TEST_PATH)/e2e --ignore=$(TEST_PATH)/perf $(GENERATOR_E2E)
# The library's lanes leave the generator's pyramid to `make test-generator`.
LIBRARY_LANE = $(UNIT_LANE) --ignore=$(TEST_PATH)/generator

# Every parallel lane distributes by xdist_group, and every lane leaves the quarantined tests out
# (tests/unit/test_lanes.py checks both).
PARALLEL       = -n auto --dist loadgroup
NOT_QUARANTINE = and not quarantine

# CI runs the fast unit lane in SPLITS shards balanced by the durations in .test_durations
# (pytest-split; `make test-durations` refreshes them). A shard keeps its coverage data and has no
# floor; `make coverage-combine` checks the floor on the union. The CI matrix lists 1..SPLITS.
SPLITS      = 8
SHARD_FLAGS = --splits $(SPLITS) --group $(GROUP) --splitting-algorithm least_duration --cov-fail-under=0

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
.PHONY: install-uv install lock generate check-freshness check-generated refresh-snapshot refresh-surface refresh-golden refresh-served-golden refresh-map build

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

refresh-snapshot: ## Rewrite the reviewed model-shape snapshots after a deliberate model change (review the diff); the public-surface baseline: make refresh-surface
	@ RP_REFRESH_SNAPSHOT=1 uv run pytest tests/unit/testkit/test_shape_snapshot.py tests/generator/unit/test_generation_shape.py -q

refresh-surface: ## Rewrite public-surface.json; this resets the move's public-surface baseline (TC-03), so run it only when a stage deliberately moves a public name (review the diff)
	@ RP_REFRESH_SNAPSHOT=1 uv run pytest tests/unit/test_public_surface.py -q

refresh-map: ## Re-key the scenario-map rows of renamed test files (against BASE, default develop), drop those of vanished tests and list the collected tests with no row (exit 1 while some are unmapped)
	@ uv run python -m tests.audit.refresh_map --base $(BASE)

refresh-golden: ## Rewrite the golden files of the extensions' schemas that are not the toy (the toy's golden is the committed tree: make generate; the served goldens: make refresh-served-golden)
	@ RP_REFRESH_GOLDEN=1 uv run pytest tests/generator/unit -k "ext_ and not test_the_toy_typescript_equals_the_golden_files" -q

refresh-served-golden: ## Rewrite the served OpenAPI and TypeScript goldens; this resets the baseline that guards the thematic move (review the diff)
	@ RP_REFRESH_GOLDEN=1 uv run pytest tests/unit/api/test_openapi_served.py -q
	@ RP_REFRESH_GOLDEN=1 uv run pytest tests/generator/unit/test_ext_typescript.py -k "test_the_toy_typescript_equals_the_golden_files" -q

build: generate ## Build the package distribution (generates first)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Building package$(END_BUILD_PRINT)"
	@ uv build
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Package built successfully$(END_BUILD_PRINT)"

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
.PHONY: format-check lint typecheck typecheck-generated typecheck-ts typecheck-openapi-ts check-architecture test test-unit test-feature test-generator test-containers fuseki-image test-e2e test-perf test-fast test-changed profile-tests test-unit-ci coverage-combine test-durations

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
	@ uv run mypy $(PACKAGE_NAME) $(GENERATOR_NAME)
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
	@ npx -y @fission-ai/openspec@1.13.2 validate --all --strict

test: ## Run the library's unit and feature tests and the generator's, each with its coverage floor
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running unit and feature tests$(END_BUILD_PRINT)"
	@ $(MAKE) --no-print-directory test-unit test-feature test-generator
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Unit and feature tests passed$(END_BUILD_PRINT)"

test-containers: ## Run the integration and e2e tests against Docker containers (no coverage floor)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running container tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) -m "(integration or e2e) $(NOT_QUARANTINE)" $(COV_FLAGS) --cov=$(GENERATOR_NAME) --cov-report=xml:$(REPO_ROOT)/coverage-containers.xml --cov-fail-under=0 --junitxml=$(REPO_ROOT)/test-results-containers.xml
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Container tests passed$(END_BUILD_PRINT)"

$(FUSEKI_IMAGE_TAR): $(FUSEKI_COMPOSE) $(shell find $(dir $(FUSEKI_COMPOSE))fuseki -type f)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Building the Fuseki image$(END_BUILD_PRINT)"
	@ mkdir -p $(dir $@)
	@ docker compose -f $(FUSEKI_COMPOSE) build fuseki && docker save -o $@ $$(docker compose -f $(FUSEKI_COMPOSE) config --images fuseki)

fuseki-image: $(FUSEKI_IMAGE_TAR) ## Load the Fuseki test image from its tar, building and saving the tar first when it is missing or older than its inputs
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Loading the Fuseki image$(END_BUILD_PRINT)"
	@ docker load -i $<
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Fuseki image ready$(END_BUILD_PRINT)"

test-unit: ## Run the library's unit tests in parallel, slow ones included, with the 80 % coverage floor over rdf_persistence
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running unit tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) $(LIBRARY_LANE) $(PARALLEL) -m "unit $(NOT_QUARANTINE)" $(COV_FLAGS) --junitxml=$(REPO_ROOT)/test-results.xml
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Unit tests passed$(END_BUILD_PRINT)"

test-unit-ci: ## Run the unit tests not marked slow in parallel, with the 80 % floor; GROUP=i runs CI shard i of SPLITS, without it
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running the fast unit tests $(GROUP)$(END_BUILD_PRINT)"
	@ COVERAGE_FILE=.coverage$(if $(GROUP),.$(GROUP)) uv run pytest $(TEST_PATH) $(LIBRARY_LANE) $(PARALLEL) -m "unit and not slow $(NOT_QUARANTINE)" $(COV_FLAGS) $(if $(GROUP),$(SHARD_FLAGS)) --junitxml=$(REPO_ROOT)/test-results$(if $(GROUP),-$(GROUP)).xml
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Fast unit tests passed$(END_BUILD_PRINT)"

coverage-combine: ## Combine the coverage data of the CI unit shards and check the 80 % floor
	@ uv run coverage combine
	@ uv run coverage xml --include='$(PACKAGE_NAME)/*' -o $(REPO_ROOT)/coverage.xml
	@ uv run coverage report --include='$(PACKAGE_NAME)/*' --fail-under=80

test-durations: ## Record the fast unit tests' durations in .test_durations, which balance the CI shards
	@ uv run pytest $(TEST_PATH) $(LIBRARY_LANE) $(PARALLEL) -m "unit and not slow $(NOT_QUARANTINE)" --store-durations --clean-durations

test-feature: ## Run the library's BDD feature tests in parallel, with a 50 % coverage floor over rdf_persistence (CI job "feature")
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running feature tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) $(LIBRARY_LANE) $(PARALLEL) -m "feature $(NOT_QUARANTINE)" $(COV_FLAGS) --cov-report=xml:$(REPO_ROOT)/coverage-feature.xml --cov-fail-under=50
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Feature tests passed$(END_BUILD_PRINT)"

test-generator: ## Run the generator's own tests (tests/generator, unit, feature and integration) in parallel, with the 80 % floor over rdf_persistence_generation (CI job "test-generator")
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running the generator tests$(END_BUILD_PRINT)"
	@ COVERAGE_FILE=.coverage.generator uv run pytest $(TEST_PATH)/generator $(GENERATOR_E2E) $(PARALLEL) -m "(unit or feature or integration) $(NOT_QUARANTINE)" $(GENERATOR_COV_FLAGS) --junitxml=$(REPO_ROOT)/test-results-generator.xml
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Generator tests passed$(END_BUILD_PRINT)"

test-perf: ## Run the wall-clock budget tests alone (no coverage, no xdist); not part of check-all
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running perf tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH)/perf -m "perf $(NOT_QUARANTINE)"
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Perf tests passed$(END_BUILD_PRINT)"

# Developer lanes (test-lanes): no coverage; the floors are checked by test, test-unit, test-feature.
test-fast: ## Run the unit and feature tests not marked slow, in parallel, without coverage (developer lane)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running the fast unit and feature tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) $(UNIT_LANE) $(PARALLEL) -m "(unit or feature) and not slow $(NOT_QUARANTINE)"
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Fast tests passed$(END_BUILD_PRINT)"

test-changed: ## Run the tests of the files changed against BASE (default develop), slow ones included, without coverage; PYTEST_N overrides the worker count
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running the tests of the changed files$(END_BUILD_PRINT)"
	@ args=$$(uv run python -m tests.changed); status=$$?; \
	  if [ $$status -eq 3 ]; then $(MAKE) --no-print-directory test-fast; \
	  elif [ $$status -ne 0 ]; then exit $$status; \
	  elif [ -n "$$args" ]; then set -f; IFS=$$'\n'; \
	    uv run pytest $$args $(UNIT_LANE) -m "(unit or feature) $(NOT_QUARANTINE)" \
	    && echo -e "$(BUILD_PRINT)$(ICON_DONE) Changed-file tests passed$(END_BUILD_PRINT)"; fi

profile-tests: ## Print the 15 slowest unit and feature tests, set-up and call apart, without coverage (PROFILE_MARK narrows)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Profiling the unit and feature tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) $(UNIT_LANE) $(PARALLEL) -q -p no:randomly -m "($(PROFILE_MARK)) $(NOT_QUARANTINE)" --durations=15
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Profile complete$(END_BUILD_PRINT)"

test-e2e: ## Run end-to-end tests only
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running e2e tests$(END_BUILD_PRINT)"
	@ uv run pytest $(TEST_PATH) -m "e2e $(NOT_QUARANTINE)"
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) E2e tests passed$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Groups — one per CI job (.github/workflows/ci.yaml), each runnable alone
#-----------------------------------------------------------------------------
.PHONY: check-spec check-style check-types check-spec-docs check-generation check-version check-quality check-all

check-style: format-check lint clean-code ## Formatting, lint and the complexity thresholds (CI job "style")
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Style checks passed$(END_BUILD_PRINT)"

check-types: typecheck typecheck-generated typecheck-ts typecheck-openapi-ts ## mypy on the code and the generated code, tsc on the generated TypeScript and on that of the OpenAPI document (CI job "types")
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Type checks passed$(END_BUILD_PRINT)"

check-spec-docs: check-spec check-docs check-version ## The OpenSpec spine and the docs checks (CI job "spec, docs and generation")
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Spec and docs checks passed$(END_BUILD_PRINT)"

check-generation: check-freshness check-generated ## Generated code is fresh and regenerates unchanged (CI job "spec, docs and generation")
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Generation checks passed$(END_BUILD_PRINT)"

check-version: ## pyproject.toml carries the version in VERSION (CI job "spec, docs and generation")
	@ grep -qx 'version = "$(VERSION)"' $(REPO_ROOT)/pyproject.toml \
	  || { echo -e "$(ICON_ERROR) pyproject.toml's version differs from VERSION ($(VERSION))"; exit 1; }
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Version $(VERSION) in sync$(END_BUILD_PRINT)"

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
.PHONY: coverage-report quality-report mutation

mutation: ## Mutate the domain layer, iris/services/iris.py and tenancy/services/tenant_move.py (domain, iris and tenant-move tests) and print the killed, survived and untested counts (selection in setup.cfg; slow)
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running mutmut (see setup.cfg for the selection)$(END_BUILD_PRINT)"
	@ uv run mutmut run
	@ uv run mutmut results
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Mutation run complete$(END_BUILD_PRINT)"

coverage-report: ## Generate HTML coverage report in reports/
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Generating coverage report$(END_BUILD_PRINT)"
	@ mkdir -p $(REPO_ROOT)/reports
	@ uv run pytest $(TEST_PATH) $(UNIT_LANE) $(COV_FLAGS) --cov=$(GENERATOR_NAME) --cov-report=html:$(REPO_ROOT)/reports/htmlcov -m "(unit or feature) $(NOT_QUARANTINE)"
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Coverage report at reports/htmlcov/index.html$(END_BUILD_PRINT)"

quality-report: ## Generate Radon quality report in reports/
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Generating quality report$(END_BUILD_PRINT)"
	@ mkdir -p $(REPO_ROOT)/reports
	@ uv run --directory $(PACKAGE_NAME) radon cc . -s -a -j > $(REPO_ROOT)/reports/complexity.json
	@ uv run --directory $(PACKAGE_NAME) radon mi . -s -j > $(REPO_ROOT)/reports/maintainability.json
	@ uv run --directory $(GENERATOR_NAME) radon cc . -s -a -j > $(REPO_ROOT)/reports/complexity-generator.json
	@ uv run --directory $(GENERATOR_NAME) radon mi . -s -j > $(REPO_ROOT)/reports/maintainability-generator.json
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Quality reports at reports/$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Clean code analysis (clean-code runs in check-style)
#-----------------------------------------------------------------------------
.PHONY: complexity maintainability clean-code

complexity: ## Radon cyclomatic complexity analysis
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Checking cyclomatic complexity$(END_BUILD_PRINT)"
	@ uv run --directory $(PACKAGE_NAME) radon cc . -s -a
	@ uv run --directory $(GENERATOR_NAME) radon cc . -s -a
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Complexity analysis complete$(END_BUILD_PRINT)"

maintainability: ## Radon maintainability index
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Checking maintainability index$(END_BUILD_PRINT)"
	@ uv run --directory $(PACKAGE_NAME) radon mi . -s
	@ uv run --directory $(GENERATOR_NAME) radon mi . -s
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Maintainability analysis complete$(END_BUILD_PRINT)"

clean-code: ## Xenon threshold checks
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Running Xenon threshold checks$(END_BUILD_PRINT)"
	@ uv run --directory $(PACKAGE_NAME) xenon . --exclude '*/generated/*' --max-absolute B --max-modules A --max-average A
	@ uv run --directory $(GENERATOR_NAME) xenon . --exclude '*/generated/*' --max-absolute B --max-modules A --max-average A
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Clean code checks passed$(END_BUILD_PRINT)"

#-----------------------------------------------------------------------------
# Docs (Antora) — see references/antora-docs.md. Remove this block if --no-docs.
#-----------------------------------------------------------------------------
.PHONY: install-antora build-docs preview-docs clean-docs check-docs check-diagrams

DOCS_DIR  = $(REPO_ROOT)/docs
DOCS_SITE = $(DOCS_DIR)/build/site
DOCS_PORT ?= 8081
# One mermaid for the site (both playbooks; check-docs enforces it) and for check-diagrams.
MERMAID_VERSION = 12.3.0
MERMAID_CLI_VERSION = 12.2.0
DIAGRAMS_DIR = $(REPO_ROOT)/temp/diagrams

install-antora: ## Install the Antora doc toolchain (npm) in docs/
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Installing Antora toolchain$(END_BUILD_PRINT)"
	@ cd $(DOCS_DIR) && npm install

build-docs: ## Build the documentation site to docs/build/site/
	@ echo -e "$(BUILD_PRINT)$(ICON_PROGRESS) Building docs$(END_BUILD_PRINT)"
	@ cd $(DOCS_DIR) && npx antora --fetch antora-playbook.local.yml
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Docs built at $(DOCS_SITE)$(END_BUILD_PRINT)"

preview-docs: build-docs ## Build then serve docs at http://localhost:$(DOCS_PORT) (8081, beside MWB2's 8080)
	@ python3 -m http.server --directory $(DOCS_SITE) $(DOCS_PORT)

check-docs: ## No consumer terms in architecture pages, the package or the tests; every page in the nav; one mermaid version
	@ python3 -I docs/tools/check_docs.py

check-diagrams: ## Render every [mermaid] block of the docs with the site's mermaid (MERMAID_VERSION)
	@ mkdir -p $(DIAGRAMS_DIR)
	@ python3 -I docs/tools/check_docs.py --mermaid-markdown $(DIAGRAMS_DIR)/all.md
	@ npx -y -p @mermaid-js/mermaid-cli@$(MERMAID_CLI_VERSION) -p mermaid@$(MERMAID_VERSION) \
		mmdc -q -p $(DOCS_DIR)/tools/puppeteer.json -i $(DIAGRAMS_DIR)/all.md -o $(DIAGRAMS_DIR)/rendered.md
	@ echo -e "$(BUILD_PRINT)$(ICON_DONE) Every diagram renders with mermaid $(MERMAID_VERSION)$(END_BUILD_PRINT)"

clean-docs: ## Remove built docs + node_modules
	@ rm -rf $(DOCS_DIR)/build $(DOCS_DIR)/node_modules

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
