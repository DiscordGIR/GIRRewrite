# syntax=docker/dockerfile:1

ARG VARIANT=3.12-bullseye
FROM mcr.microsoft.com/vscode/devcontainers/python:${VARIANT}

ARG NODE_VERSION="23"
RUN if [ "${NODE_VERSION}" != "none" ]; then su vscode -c "umask 0002 && . /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"; fi

ARG POETRY_VERSION="1.8.4"
RUN if [ "${POETRY_VERSION}" != "none" ]; then su vscode -c "umask 0002 && pip3 install poetry==${POETRY_VERSION}"; fi

# system dependencies
RUN apt update
RUN apt install -y curl git gcc python3-dev

# python dependencies
COPY . .
RUN npm i -g nodemon
