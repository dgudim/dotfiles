#export SLACK_VACATION=0a

source slack_token.sh

with_token() {
    if [ -z ${SLACK_VACATION+x} ]; then
        "$@" -H "$SLACK_TOKEN" | jq
    else
        bash slack_vacation.sh | jq
    fi
}
