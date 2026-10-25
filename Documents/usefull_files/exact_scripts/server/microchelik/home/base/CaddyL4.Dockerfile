FROM caddy:2-builder AS builder

RUN xcaddy build \
    --with github.com/mholt/caddy-l4=github.com/vnxme/caddy-l4@packet-conn-wrapper \
    --with github.com/lucaslorentz/caddy-docker-proxy/v2 \
    --with github.com/dmarcwise/caddy-shield \
    --with github.com/hslatman/caddy-crowdsec-bouncer/http \
    --with github.com/porech/caddy-maxmind-geolocation

FROM caddy:2

COPY --from=builder /usr/bin/caddy /usr/bin/caddy

CMD ["caddy", "docker-proxy", "--caddyfile-path", "/etc/caddy/Caddyfile"]
