FROM python:3.12-slim@sha256:9d3abd9fc11d06998ccdbdd93b4dd49b5ad7d67fcbbc11c016eb0eb2c2194891

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AI_ARCHIVE_CONTAINER=1

WORKDIR /app

COPY pyproject.toml README.md requirements-container.txt ./
COPY cli ./cli
COPY docs ./docs
COPY examples ./examples
COPY mcp ./mcp
COPY plans ./plans
COPY schemas ./schemas
COPY specs ./specs
COPY src ./src
COPY templates ./templates
COPY zettel-kasten ./zettel-kasten

RUN python -m pip install --no-cache-dir --require-hashes -r requirements-container.txt \
    && python -m pip install --no-cache-dir --no-build-isolation --no-deps -e . \
    && groupadd --gid 10001 archive \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin archive

VOLUME ["/archives"]

USER archive

ENTRYPOINT ["archive"]
CMD ["--help"]
