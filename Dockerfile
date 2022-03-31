# syntax=docker/dockerfile:1

ARG VARIANT=3.10-bullseye
FROM mcr.microsoft.com/vscode/devcontainers/python:${VARIANT}

ARG NODE_VERSION="16"
RUN if [ "${NODE_VERSION}" != "none" ]; then su vscode -c "umask 0002 && . /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"; fi

# system dependencies
ENV NODE_VERSION=16.8.0
RUN apt update
RUN apt install -y curl git gcc python3-dev

# python dependencies
COPY ./requirements.txt .
COPY . .
RUN pip install --upgrade pip setuptools wheel
COPY requirements.txt /tmp/pip-tmp/
RUN pip --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
   && rm -rf /tmp/pip-tmp
RUN pip install autopep8
RUN npm i -g nodemon
