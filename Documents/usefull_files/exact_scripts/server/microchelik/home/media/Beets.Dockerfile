FROM python:3.13-slim

RUN pip install --no-cache-dir "beets[lyrics]~=2.14.1"

ENV PYTHONUNBUFFERED=1 \
    BEETSDIR=/config \
    HOME=/data
WORKDIR /data
ENTRYPOINT ["beet"]
