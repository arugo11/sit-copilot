#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <subscription-id>" >&2
  exit 1
fi

subscription_id="$1"
providers=(
  Microsoft.App
  Microsoft.Web
  Microsoft.ContainerRegistry
  Microsoft.ManagedIdentity
  Microsoft.Insights
  Microsoft.OperationalInsights
)

az account set --subscription "${subscription_id}"

for provider in "${providers[@]}"; do
  echo "registering ${provider}"
  az provider register --namespace "${provider}" --wait --only-show-errors
done

echo "done"
