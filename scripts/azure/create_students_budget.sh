#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 4 ] || [ "$#" -gt 6 ]; then
  echo "usage: $0 <subscription-id> <budget-name> <amount> <emails-csv> [action-group-ids-csv] [location]" >&2
  exit 1
fi

subscription_id="$1"
budget_name="$2"
amount="$3"
emails_csv="$4"
action_group_ids_csv="${5:-}"
deployment_location="${6:-japaneast}"

start_date="$(date -u +%Y-%m-01)"
end_date="$(date -u -d "${start_date} + 1 year" +%F)"

IFS=',' read -r -a email_array <<< "${emails_csv}"
email_json="$(printf '%s\n' "${email_array[@]}" | python3 -c 'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))')"

if [ -n "${action_group_ids_csv}" ]; then
  IFS=',' read -r -a action_group_array <<< "${action_group_ids_csv}"
  action_group_json="$(printf '%s\n' "${action_group_array[@]}" | python3 -c 'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))')"
else
  action_group_json='[]'
fi

az account set --subscription "${subscription_id}"

az deployment sub create \
  --name "${budget_name}" \
  --location "${deployment_location}" \
  --template-file "$(dirname "$0")/templates/students-budget.bicep" \
  --parameters \
    budgetName="${budget_name}" \
    amount="${amount}" \
    startDate="${start_date}" \
    endDate="${end_date}" \
    contactEmails="${email_json}" \
    contactGroupIds="${action_group_json}" \
  --only-show-errors \
  --output table
