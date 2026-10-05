FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /code
COPY common /common
COPY stats/pyproject.toml stats/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY stats/app app
CMD ["uv", "run", "--no-dev", "fastapi", "run", "--host", "0.0.0.0", "--port", "8000"]
