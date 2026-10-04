# Usage: make help

TEMPLATE := cookiecutter-fastapi
RUFF := ruff@0.16.10
SERVICES := $(patsubst %/pyproject.toml,%,$(wildcard */pyproject.toml))

.PHONY: help init dev infra-up infra-down test lint clear main stream live-chat replay search bookmarks stats

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-12s %s\n", $$1, $$2}'

init: ## Create a service from the template: make init name=<service-name>
ifndef name
	$(error name is required. Usage: make init name=<service-name>)
endif
	@if [ -e "$(name)" ]; then echo "Error: '$(name)' already exists"; exit 1; fi
	@command -v uv >/dev/null || { echo "Error: uv is not installed (https://docs.astral.sh/uv/)"; exit 1; }
	@uvx cookiecutter $(TEMPLATE) --no-input service_name="$(name)"
	@echo "Service '$(name)' created. Next:"
	@echo "  cd $(name) && uv run fastapi dev"

dev: ## Copy each .env.example to .env (if missing) and install every service
	@for service in $(SERVICES); do \
		if [ -f $$service/.env.example ] && [ ! -f $$service/.env ]; then \
			cp $$service/.env.example $$service/.env; \
			echo "$$service: .env created"; \
		fi; \
		uv sync --directory $$service || exit 1; \
	done

infra-up: ## Start postgres, redis and mosquitto
	docker compose up -d

infra-down: ## Stop the infra
	docker compose down

test: ## Run the tests of every service, fails if one of them fails
	@failed=""; \
	for service in $(SERVICES); do \
		echo "=== $$service"; \
		uv run --directory $$service pytest -q || failed="$$failed $$service"; \
	done; \
	if [ -n "$$failed" ]; then \
		echo "Failed:$$failed"; \
		exit 1; \
	fi

lint: ## Run ruff on every service (make lint fix=1 to fix what can be fixed)
	uvx $(RUFF) check $(if $(fix),--fix) $(SERVICES)

clear: ## Delete the local .db files
	find . -name "*.db" -not -path "*/.venv/*" -print -delete

main: ## Run main on port 8000
	uv run --directory main fastapi dev --port 8000

stream: ## Run stream on port 8001
	uv run --directory stream fastapi dev --port 8001

live-chat: ## Run live-chat on port 8002
	uv run --directory live-chat fastapi dev --port 8002

replay: ## Run replay on port 8003
	uv run --directory replay fastapi dev --port 8003

search: ## Run search on port 8004
	uv run --directory search fastapi dev --port 8004

bookmarks: ## Run bookmarks on port 8005
	uv run --directory bookmarks fastapi dev --port 8005

stats: ## Run stats on port 8006
	uv run --directory stats fastapi dev --port 8006
