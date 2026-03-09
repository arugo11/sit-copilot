#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <subscription-id> <resource-group> <container-app-name>" >&2
  exit 1
fi

subscription_id="$1"
resource_group="$2"
container_app_name="$3"

az account set --subscription "${subscription_id}"

az containerapp show \
  --name "${container_app_name}" \
  --resource-group "${resource_group}" \
  --query "properties.template.containers[0].env[?name=='WEAVE_ENABLED' || name=='AZURE_OPENAI_ENABLED' || name=='LECTURE_LIVE_ASR_REVIEW_ENABLED' || name=='LECTURE_LIVE_TRANSLATION_ENABLED' || name=='LECTURE_LIVE_SUMMARY_ENABLED' || name=='LECTURE_LIVE_KEYTERMS_ENABLED' || name=='LECTURE_QA_ENABLED' || name=='LECTURE_IDLE_AUTOSTOP_SECONDS'].{name:name,value:value,secretRef:secretRef}" \
  --output table
