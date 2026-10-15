#!/bin/env /bin/bash

sudo mkdir -pv /mnt/sata_500/nextcloud_data

sudo docker run --detach \
--init \
--env NEXTCLOUD_DATADIR="/mnt/sata_500/nextcloud_data" \
--env NEXTCLOUD_MOUNT="/mnt/sata_500/nextcloud_external_mounts" \
--sig-proxy=false \
--name nextcloud-aio-mastercontainer \
--network proxy \
--restart always \
--env APACHE_PORT=11000 \
--env APACHE_IP_BINDING=0.0.0.0 \
--env APACHE_ADDITIONAL_NETWORK="" \
--env SKIP_DOMAIN_VALIDATION=false \
--label caddy_0="http://aio.kloud.home, http://aio.kloud.vpn" \
--label caddy_0.reverse_proxy="{{upstreams https 8080}}" \
--label caddy_0.reverse_proxy.transport=http \
--label caddy_0.reverse_proxy.transport.tls= \
--label caddy_0.reverse_proxy.transport.tls_insecure_skip_verify= \
--label caddy_1="https://aio.kloud.home, https://aio.kloud.vpn" \
--label caddy_1.tls=internal \
--label caddy_1.reverse_proxy="{{upstreams https 8080}}" \
--label caddy_1.reverse_proxy.transport=http \
--label caddy_1.reverse_proxy.transport.tls= \
--label caddy_1.reverse_proxy.transport.tls_insecure_skip_verify= \
--label caddy_ingress_network=proxy \
--volume nextcloud_aio_mastercontainer:/mnt/docker-aio-config \
--volume /var/run/docker.sock:/var/run/docker.sock:ro \
ghcr.io/nextcloud-releases/all-in-one:latest
