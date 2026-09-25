#!/bin/bash
# https://gist.github.com/achetronic/2db363e6c2fbecd42ae67512fbea50ca
# Docker Hub refuses deep anonymous pagination ("sign in to page further").
# This uses the existing `docker login` credential to get a Hub JWT.

set -euo pipefail

SHA256_HASH="65f70a152846cf504dff86e807007e9aeac98c3aeb7b62541b2c55ab9d264e56"
NAMESPACE='library'
REPO_NAME='postgres'
PAGE_SIZE=100
DIGEST="sha256:${SHA256_HASH}"

hub_token() {
    local cfg helper creds user pass
    cfg="${DOCKER_CONFIG:-$HOME/.docker}/config.json"
    if [[ ! -f "$cfg" ]]; then
        echo "No Docker config at $cfg. Run: docker login" >&2
        return 1
    fi

    helper="docker-credential-$(jq -r '.credsStore // "secretservice"' "$cfg")"
    if ! command -v "$helper" >/dev/null; then
        echo "Credential helper not found: $helper" >&2
        return 1
    fi

    creds=$(printf '%s' 'https://index.docker.io/v1/' | "$helper" get)
    user=$(jq -r '.Username' <<<"$creds")
    pass=$(jq -r '.Secret' <<<"$creds")
    if [[ -z "$user" || -z "$pass" || "$user" == "null" || "$pass" == "null" ]]; then
        echo "Docker is not logged in to Docker Hub. Run: docker login" >&2
        return 1
    fi

    curl -fsS -X POST 'https://hub.docker.com/v2/users/login/' \
        -H 'Content-Type: application/json' \
        -d "$(jq -n --arg u "$user" --arg p "$pass" '{username:$u,password:$p}')" \
        | jq -er '.token'
}

TOKEN=$(hub_token)

page=1
while true; do
    echo "Looking into page: $page"

    body=$(curl -sS -w $'\n%{http_code}' \
        -H "Authorization: JWT ${TOKEN}" \
        "https://registry.hub.docker.com/v2/repositories/${NAMESPACE}/${REPO_NAME}/tags/?page=${page}&page_size=${PAGE_SIZE}")
    code=${body##*$'\n'}
    body=${body%$'\n'*}

    if [[ "$code" == "429" ]]; then
        echo -e "\e[35mRate limited on page $page, sleeping 7 seconds...\e[0m"
        sleep 7
        continue
    fi

    if [[ "$code" != "200" ]]; then
        echo "Docker Hub returned HTTP $code on page $page:" >&2
        echo "$body" >&2
        exit 1
    fi

    result=$(jq --arg digest "$DIGEST" '
        .results[]?
        | select((.digest == $digest) or (any(.images[]?; .digest == $digest)))
    ' <<<"$body")

    if [[ -n "$result" ]]; then
        echo "$result" | jq '.'
        exit 0
    fi

    next=$(jq -r '.next // empty' <<<"$body")
    if [[ -z "$next" ]]; then
        echo "Digest not found in ${NAMESPACE}/${REPO_NAME}" >&2
        exit 1
    fi

    page=$((page + 1))
done
