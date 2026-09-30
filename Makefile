# Usage: make init name=<service-name>
# Example: make init name=users

TEMPLATE := cookiecutter-fastapi

.PHONY: init help main stream live-chat replay search bookmarks stats

help:
	@echo "Usage: make init name=<service-name>"

init:
ifndef name
	$(error name is required. Usage: make init name=<service-name>)
endif
	@if [ -e "$(name)" ]; then echo "Error: '$(name)' already exists"; exit 1; fi
	@command -v uv >/dev/null || { echo "Error: uv is not installed (https://docs.astral.sh/uv/)"; exit 1; }
	@uvx cookiecutter $(TEMPLATE) --no-input service_name="$(name)"
	@echo "Service '$(name)' created. Next:"
	@echo "  cd $(name) && uv run fastapi dev"


main:
	uv run --directory main fastapi dev --port 8000

stream:
	uv run --directory stream fastapi dev --port 8001

live-chat:
	uv run --directory live-chat fastapi dev --port 8002

replay:
	uv run --directory replay fastapi dev --port 8003

search:
	uv run --directory search fastapi dev --port 8004

bookmarks:
	uv run --directory bookmarks fastapi dev --port 8005

stats:
	uv run --directory stats fastapi dev --port 8006

