#!/usr/bin/env bash
# Usage: rollback_eb.sh APP ENV HEALTH_PATH [VERSION_LABEL]
# Without VERSION_LABEL: only lists the current and recent versions.
set -euo pipefail
APP="$1"; ENV_NAME="$2"; HEALTH_PATH="$3"; LABEL="${4:-}"

CURRENT=$(aws elasticbeanstalk describe-environments --application-name "$APP" \
  --environment-names "$ENV_NAME" --query 'Environments[0].VersionLabel' --output text)
echo "Current version of $ENV_NAME: $CURRENT"
echo "Recent versions of $APP (oldest to newest):"
aws elasticbeanstalk describe-application-versions --application-name "$APP" \
  --query 'sort_by(ApplicationVersions,&DateCreated)[-10:].[VersionLabel,DateCreated]' --output text

if [ -z "$LABEL" ]; then
  echo "No version_label given. List only, nothing changed."
  exit 0
fi

aws elasticbeanstalk update-environment --environment-name "$ENV_NAME" --version-label "$LABEL" >/dev/null
bash "$(dirname "$0")/eb_wait.sh" "$APP" "$ENV_NAME" "$LABEL" "$HEALTH_PATH"
