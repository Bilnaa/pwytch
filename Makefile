# Usage: make init name=<service-name>
# Example: make init name=users

TEMPLATE := cookiecutter-fastapi

.PHONY: init help

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
	@echo "  cd $(name) && uv run uvicorn app.main:app --reload"
