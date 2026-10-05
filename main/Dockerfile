FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web .
RUN npm run build

FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /code
COPY common /common
COPY main/pyproject.toml main/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY main/app app
# FRONTEND_DIR defaults to ../web/dist, from /code
COPY --from=web /web/dist /web/dist
CMD ["uv", "run", "--no-dev", "fastapi", "run", "--host", "0.0.0.0", "--port", "8000"]
