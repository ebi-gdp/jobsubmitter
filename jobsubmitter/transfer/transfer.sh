#!/bin/bash

set -euo pipefail

help() {
  echo "Recursively transfer all files from a globus endpoint to a local directory"
  echo
  echo "Requires the following environment variables to run:"
  echo "GLOBUS_CLI_CLIENT_ID:     secret"
  echo "GLOBUS_CLI_CLIENT_SECRET: secret"
  echo "GLOBUS_SRC:               uuid of source endpoint (remote identifier)"
  echo "LOCAL_DEST:               local directory that remote files are transferred to"
}

check_env() {
  envVars=("GLOBUS_CLI_CLIENT_ID" "GLOBUS_CLI_CLIENT_SECRET" "GLOBUS_SRC" "LOCAL_DEST")
  for var in "${envVars[@]}"; do
      if [ -z ${var+x} ];
      then
        echo "$var is unset";
        help
        exit 1
      else
        echo "$var is set";
      fi
  done
}

setup() {
  ENDPOINT_DETAILS=$(globus endpoint create --personal my-gcp-endpoint-shared --default-directory /data/)
  SETUP_ID=$(echo "$ENDPOINT_DETAILS" | sed -n 's/.*Setup Key://p' | sed -e 's/^[ \t]*//')
  GLOBUS_DEST=$(echo "$ENDPOINT_DETAILS" | sed -n 's/.*Endpoint ID://p' | sed -e 's/^[ \t]*//')
  globusconnectpersonal -setup "$SETUP_ID"
  globusconnectpersonal -start &

  until [ "$(globusconnectpersonal -status | sed -n 's/.*Globus Online://p' | sed -e 's/^[ \t]*//')" = "connected" ]
  do
    echo "Waiting..."
    sleep 5
  done

  echo "Globus connected"

  transfer "$GLOBUS_DEST"
}

transfer() {
  GLOBUS_DEST=$1

  TASK_ID=$(globus transfer -r "$GLOBUS_SRC":/ "$GLOBUS_DEST":"$LOCAL_DEST" | sed -n 's/.*Task ID://p' | sed -e 's/^[ \t]*//')
  echo "TASK ID: $TASK_ID"
  globus task wait --polling-interval 30 "$TASK_ID"
  echo "Transfer complete. Goodbye :)"
}

main() {
  check_env
  setup
}

main

