#!/data/data/com.termux/files/usr/bin/bash

source ./slack_token.sh

curl -X POST 'https://slack.com/api/users.profile.set' \
-H "$SLACK_TOKEN" \
-H 'Content-Type: application/json; charset=utf-8' \
-d '{ "profile": {"status_text": "Not in office", "status_emoji": ":homerdespawn:", "status_expiration": "0" }}' | jq
