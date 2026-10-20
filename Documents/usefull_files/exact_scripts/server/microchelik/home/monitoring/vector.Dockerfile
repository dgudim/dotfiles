FROM timberio/vector:latest-debian AS vector

FROM debian:forky-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends systemd ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/*
COPY --from=vector /usr/bin/vector /usr/bin/vector
ENTRYPOINT ["/usr/bin/vector"]
