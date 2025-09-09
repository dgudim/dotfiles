#!/data/data/com.termux/files/usr/bin/bash

arr[0]="Creating system user accounts"
arr[1]="Updating journal message catalog"
arr[2]="Reloading system manager configuration"
arr[3]="Updating udev hardware database"
arr[4]="Applying kernel sysctl settings"
arr[5]="Reloading device manager configuration"
arr[6]="Arming ConditionNeedsUpdate"
arr[7]="Reloading system bus configuration"
arr[8]="Checking package integrity"
arr[9]="Updating module dependencies"
arr[10]="Running post-transaction hooks"
rand=$[$RANDOM % ${#arr[@]}]
status=${arr[$rand]}

source ./slack_token.sh

with_token curl -X POST 'https://slack.com/api/users.profile.set' \
-H 'Content-Type: application/json; charset=utf-8' \
-d "{ \"profile\": {\"status_text\": \"$status\", \"status_emoji\": \":linux_red:\", \"status_expiration\": \"0\" }}"

