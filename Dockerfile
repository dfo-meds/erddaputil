FROM python:3.9.13-slim-bullseye

VOLUME /erddap_util/config

VOLUME /erddap_data

WORKDIR /erddap_util

ENV ERDDAPUTIL_CONFIG_PATHS=/erddap_util/docker_config;/erddap_util/config

RUN pip install --upgrade pip

COPY docker/requirements.txt requirements-docker.txt
RUN pip install -r requirements-docker.txt

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY docker/start.sh start.sh
RUN chmod +x start.sh

COPY docker/config docker_config

EXPOSE 9172

COPY erddaputil erddaputil

ENTRYPOINT ["./start.sh"]
CMD ["daemon"]
