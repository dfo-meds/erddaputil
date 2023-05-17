FROM python:3.9.13-slim-bullseye

RUN apt update

RUN apt install dumb-init

RUN apt clean

VOLUME /erddap_util/config

VOLUME /erddap_data

WORKDIR /erddap_util

ENV ERDDAPUTIL_CONFIG_PATH=/erddap_util/docker_config;/erddap_util/config

RUN pip install --upgrade pip

COPY requirements/docker-requirements.txt requirements-docker.txt
RUN pip install -r requirements-docker.txt

COPY requirements/requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY docker/start.sh start.sh
RUN chmod +x start.sh

COPY docker/config docker_config

EXPOSE 9172
EXPOSE 9173

COPY erddaputil erddaputil

ENTRYPOINT ["/usr/bin/dumb-init", "--", "/erddap_util/start.sh"]
CMD ["daemon"]
