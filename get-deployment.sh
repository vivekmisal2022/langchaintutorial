#!/bin/zsh
# obtain authentication token
SECRET=`echo -n "$AICORE_CLIENT_ID:$AICORE_CLIENT_SECRET" | base64 -i - ` 
TOKEN=`curl -X POST \
  --url "$AICORE_AUTH_URL/oauth/token" \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=client_credentials" \
  --data "client_id=$AICORE_CLIENT_ID" \
  --data "client_secret=$AICORE_CLIENT_SECRET"`
echo $TOKEN
