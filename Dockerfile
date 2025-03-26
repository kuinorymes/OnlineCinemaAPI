FROM python:3.10

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=off

RUN apt update && apt install -y \
    gcc \
    libpq-dev \
    netcat-openbsd \
    postgresql-client \
    dos2unix \
    && apt clean

RUN python -m pip install --upgrade pip && \
    pip install poetry

WORKDIR /usr/src/app

COPY /pyproject.toml ./
COPY /poetry.lock ./
COPY /alembic.ini ./

RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

COPY ./src .
