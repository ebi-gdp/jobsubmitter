# docker buildx build --platform linux/amd64,linux/arm64 --push -t dockerhub.ebi.ac.uk/gdp-public/jobsubmitter .

FROM --platform=amd64 python:3.10 AS builder

WORKDIR /app

RUN pip install poetry

RUN python -m venv /venv

COPY pyproject.toml poetry.lock /app

RUN poetry export --without-hashes -f requirements.txt | /venv/bin/pip install -r /dev/stdin

COPY . .

RUN poetry build && /venv/bin/pip install dist/*.whl

FROM --platform=amd64 python:3.10-alpine

COPY --from=builder /venv /venv

ENV PATH="/venv/bin:${PATH}"

# ADD . /app
# RUN adduser app -h /app -u 1000 -g 1000 -DH
# USER 1000
