#!/usr/bin/env bash

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
  if [[ -v GLOBUS_CLI_CLIENT_ID ]] || [[ -v GLOBUS_CLI_CLIENT_SECRET ]]; then
    echo "Secrets set"
  else
    echo "ERROR: Secrets not set"
    help
    exit 1
  fi

  if [[ -v LOCAL_DEST ]] || [[ -v GLOBUS_SRC ]]; then
    echo "LOCAL_DEST: $LOCAL_DEST"
    echo "GLOBUS_SRC: $GLOBUS_SRC"
  else
    echo "ERROR: missing environment variables GLOBUS_SRC or LOCAL_DEST"
    help
    exit 1
  fi
}

setup() {
  ENDPOINT_DETAILS=$(globus endpoint create --personal my-gcp-endpoint-shared)
  SETUP_ID=$(echo "$ENDPOINT_DETAILS" | sed -n 's/.*Setup Key://p' | sed -e 's/^[ \t]*//')
  GLOBUS_DEST=$(echo "$ENDPOINT_DETAILS" | sed -n 's/.*Endpoint ID://p' | sed -e 's/^[ \t]*//')
  echo "SETUP_ID: $SETUP_ID"
  globusconnectpersonal -debug -setup "$SETUP_ID" || cat /home/globus-client/.globusonline/lta/register.log
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
  # debug live container with sleep
  echo "Sleeping..."
  sleep 3600
}

main