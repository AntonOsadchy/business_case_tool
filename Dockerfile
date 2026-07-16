FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY bess_bc ./bess_bc

RUN pip install --no-cache-dir .[dev]

ENTRYPOINT ["python3", "-m", "bess_bc.cli"]
