# docker buildx build --platform linux/amd64,linux/arm64 --push -t dockerhub.ebi.ac.uk/gdp-public/jobsubmitter .

FROM python:3.10-alpine AS builder
WORKDIR /app
ADD pyproject.toml poetry.lock /app/

RUN apk add build-base libffi-dev
RUN pip install poetry
RUN poetry config virtualenvs.in-project true
RUN poetry install --no-ansi

# ---

FROM python:3.10-alpine
WORKDIR /app

COPY --from=builder /app /app
ADD . /app

RUN adduser app -h /app -u 1000 -g 1000 -DH
USER 1000

# change this to match your application
ENTRYPOINT ["/app/.venv/bin/python", "jobsubmitter.py"]
