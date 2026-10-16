#!/usr/bin/env bash
# Usage: eb_wait.sh APP ENV VERSION_LABEL HEALTH_PATH
# Waits until the environment runs VERSION_LABEL, then smoke-tests it.
set -euo pipefail
APP="$1"; ENV_NAME="$2"; LABEL="$3"; HEALTH_PATH="$4"

STATUS=""; VERSION=""; HEALTH=""
for i in $(seq 1 90); do
  read -r STATUS VERSION HEALTH < <(aws elasticbeanstalk describe-environments \
    --application-name "$APP" --environment-names "$ENV_NAME" \
    --query 'Environments[0].[Status,VersionLabel,HealthStatus]' --output text)
  echo "[$i/90] status=$STATUS version=$VERSION health=$HEALTH"
  if [ "$STATUS" = "Ready" ] && [ "$VERSION" = "$LABEL" ]; then break; fi
  sleep 10
done

if [ "$STATUS" != "Ready" ] || [ "$VERSION" != "$LABEL" ]; then
  echo "ERROR: environment did not reach version $LABEL. Recent events:"
  aws elasticbeanstalk describe-events --application-name "$APP" --environment-name "$ENV_NAME" \
    --max-items 15 --query 'Events[].[EventDate,Severity,Message]' --output text || true
  exit 1
fi

case "$HEALTH" in
  Degraded|Severe) echo "ERROR: environment health is $HEALTH"; exit 1 ;;
esac

CNAME=$(aws elasticbeanstalk describe-environments --application-name "$APP" \
  --environment-names "$ENV_NAME" --query 'Environments[0].CNAME' --output text)
echo "Smoke test: http://$CNAME$HEALTH_PATH"
curl -fsS --retry 10 --retry-delay 6 --retry-connrefused "http://$CNAME$HEALTH_PATH"
echo
echo "Smoke test: dashboard page and /analyze"
curl -fsS --retry 3 --retry-delay 5 "http://$CNAME/" | grep -q "DeployGuard"
curl -fsS "http://$CNAME/analyze?error_rate=1&latency_ms=100&health_status=healthy" | grep -q '"risk_score"'
echo "OK: $ENV_NAME runs $LABEL"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  echo "- **$ENV_NAME** now runs \`$LABEL\` (http://$CNAME)" >> "$GITHUB_STEP_SUMMARY"
fi
