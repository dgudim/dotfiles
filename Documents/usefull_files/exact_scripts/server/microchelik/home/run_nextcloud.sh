#!/bin/env /bin/bash

. "$(dirname "$(realpath "$0")")/base_env_definitions"

sudo docker run --detach \
--init \
--env NEXTCLOUD_DATADIR="/mnt/sata_500/nextcloud_data" \
--env NEXTCLOUD_MOUNT="/mnt/sata_500/nextcloud_external_mounts" \
--sig-proxy=false \
--name nextcloud-aio-mastercontainer \
--no-healthcheck \
--network proxy \
--restart always \
-p 8080:8080 \
--env APACHE_PORT=11000 \
--env APACHE_IP_BINDING=0.0.0.0 \
--env APACHE_ADDITIONAL_NETWORK="" \
--env SKIP_DOMAIN_VALIDATION=false \
--label caddy_0="${NEXTCLOUD_AIO_SITES}" \
--label caddy_0.reverse_proxy="{{upstreams https 8080}}" \
--label caddy_0.reverse_proxy.transport=http \
--label caddy_0.reverse_proxy.transport.tls= \
--label caddy_0.reverse_proxy.transport.tls_insecure_skip_verify= \
--label caddy_1="${NEXTCLOUD_AIO_TLS_SITES}" \
--label caddy_1.tls=internal \
--label caddy_1.reverse_proxy="{{upstreams https 8080}}" \
--label caddy_1.reverse_proxy.transport=http \
--label caddy_1.reverse_proxy.transport.tls= \
--label caddy_1.reverse_proxy.transport.tls_insecure_skip_verify= \
--label caddy_ingress_network=proxy \
--volume nextcloud_aio_mastercontainer:/mnt/docker-aio-config \
--volume /var/run/docker.sock:/var/run/docker.sock:ro \
ghcr.io/nextcloud-releases/all-in-one:latest
