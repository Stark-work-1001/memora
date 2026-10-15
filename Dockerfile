# MCP over stdio: run with `docker run -i --rm -v memory-merge-data:/data memory-merge-local`.
# Lexical retrieval only by default; point MM_EMBED_URL at a model server to enable vectors
# (from inside a container, the host is not 127.0.0.1: see docs/INTEGRATIONS.md).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MM_DATA=/data
RUN useradd --create-home --uid 10001 mm && mkdir /data && chown mm /data
WORKDIR /app
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY pyproject.toml README.md LICENSE ./
COPY memory_merge ./memory_merge
RUN pip install --no-cache-dir --no-deps . && rm -rf /app/memory_merge
USER mm
VOLUME ["/data"]
ENTRYPOINT ["memory-merge-mcp"]
