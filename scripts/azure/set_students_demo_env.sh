#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SUBSCRIPTION_ID="4c170a0d-3e6d-42a0-b941-533e4f44e729"

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <subscription-id> <resource-group> <container-app-name>" >&2
  exit 1
fi

subscription_id="$1"
resource_group="$2"
container_app_name="$3"

if [ "${subscription_id}" != "${EXPECTED_SUBSCRIPTION_ID}" ]; then
  echo "subscription id must be ${EXPECTED_SUBSCRIPTION_ID}" >&2
  exit 1
fi

az account set --subscription "${subscription_id}"

active_subscription_id="$(az account show --query id -o tsv)"
if [ "${active_subscription_id}" != "${EXPECTED_SUBSCRIPTION_ID}" ]; then
  echo "active subscription mismatch: ${active_subscription_id}" >&2
  exit 1
fi

az containerapp update \
  --name "${container_app_name}" \
  --resource-group "${resource_group}" \
  --set-env-vars \
    AZURE_SUBSCRIPTION_ID="${EXPECTED_SUBSCRIPTION_ID}" \
    PUBLIC_DEMO_ENABLED=true \
    WEAVE_ENABLED=false \
    AZURE_OPENAI_ENABLED=true \
    AZURE_VISION_ENABLED=true \
    AZURE_SEARCH_ENABLED=true \
    LECTURE_LIVE_ASR_REVIEW_ENABLED=true \
    LECTURE_LIVE_TRANSLATION_ENABLED=true \
    LECTURE_LIVE_SUMMARY_ENABLED=true \
    LECTURE_LIVE_KEYTERMS_ENABLED=true \
    LECTURE_QA_ENABLED=true \
    LECTURE_IDLE_AUTOSTOP_SECONDS=120 \
  --only-show-errors \
  --output none

echo "demo env applied to ${container_app_name}"
