FROM python:3.14-slim
# ffmpeg convertit la playlist HLS de stream en .mp4
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /code
COPY common /common
COPY replay/pyproject.toml replay/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY replay/app app
CMD ["uv", "run", "--no-dev", "fastapi", "run", "--host", "0.0.0.0", "--port", "8000"]
