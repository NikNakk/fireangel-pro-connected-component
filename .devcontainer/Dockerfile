FROM mcr.microsoft.com/devcontainers/python:3.14-trixie

COPY requirements-dev.txt /tmp/requirements-dev.txt

RUN pip install --no-cache-dir --requirement /tmp/requirements-dev.txt \
    && rm /tmp/requirements-dev.txt

