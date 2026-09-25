FROM caddy:2-builder AS builder

RUN xcaddy build \
    --with github.com/mholt/caddy-l4=github.com/vnxme/caddy-l4@packet-conn-wrapper

FROM caddy:2

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
