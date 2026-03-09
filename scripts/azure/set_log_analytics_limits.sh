#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 3 ] || [ "$#" -gt 5 ]; then
  echo "usage: $0 <subscription-id> <resource-group> <workspace-name> [daily-cap-gb] [retention-days]" >&2
  exit 1
fi

subscription_id="$1"
resource_group="$2"
workspace_name="$3"
daily_cap_gb="${4:-0.023}"
retention_days="${5:-30}"

az account set --subscription "${subscription_id}"

az monitor log-analytics workspace update \
  --resource-group "${resource_group}" \
  --workspace-name "${workspace_name}" \
  --quota "${daily_cap_gb}" \
  --retention-time "${retention_days}" \
  --only-show-errors \
  --output table
