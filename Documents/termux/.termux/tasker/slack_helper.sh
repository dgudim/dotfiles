export SLACK_VACATION=1

with_token() {
    if [ -z ${SLACK_VACATION+x} ]; then
        "$@" -H "$SLACK_TOKEN" | jq
    else
        bash slack_vacation.sh | jq
    fi
}
