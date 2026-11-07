# NaviSync (https://github.com/zeroquinc/NaviSync): Last.fm play counts and loved tracks -> Navidrome.

FROM alpine/git:latest AS source
ARG NAVISYNC_REPO=zeroquinc/NaviSync
ARG NAVISYNC_BRANCH=main

ADD https://api.github.com/repos/${NAVISYNC_REPO}/commits/${NAVISYNC_BRANCH} /tmp/head.json
RUN git clone --depth 1 --branch "$NAVISYNC_BRANCH" "https://github.com/${NAVISYNC_REPO}.git" /src \
 && git -C /src log -1 --format='NaviSync %h (%cs)' > /src/VERSION \
 && rm -rf /src/.git

FROM python:3.13-alpine

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY --from=source /src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=source /src/ .
COPY config/navisync/navisync_unattended.py .

RUN ln -s /state/cache /app/cache \
 && ln -s /state/json /app/json

ENTRYPOINT ["python", "/app/navisync_unattended.py"]
