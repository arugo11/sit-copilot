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

az containerapp update \
  --name "${container_app_name}" \
  --resource-group "${resource_group}" \
  --set-env-vars \
    WEAVE_ENABLED=false \
    AZURE_OPENAI_ENABLED=false \
    LECTURE_LIVE_ASR_REVIEW_ENABLED=false \
    LECTURE_LIVE_TRANSLATION_ENABLED=false \
    LECTURE_LIVE_SUMMARY_ENABLED=false \
    LECTURE_LIVE_KEYTERMS_ENABLED=false \
    LECTURE_QA_ENABLED=false \
    LECTURE_IDLE_AUTOSTOP_SECONDS=120 \
  --only-show-errors \
  --output none

echo "safe env applied to ${container_app_name}"
