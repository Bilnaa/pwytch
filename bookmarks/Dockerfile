FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /code
COPY common /common
COPY bookmarks/pyproject.toml bookmarks/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY bookmarks/app app
CMD ["uv", "run", "--no-dev", "fastapi", "run", "--host", "0.0.0.0", "--port", "8000"]
