FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

COPY requirements-dev.txt /tmp/requirements-dev.txt

RUN pip install --no-cache-dir --requirement /tmp/requirements-dev.txt \
    && rm /tmp/requirements-dev.txt

