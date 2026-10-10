#!/usr/bin/env bash
# Usage: deploy_eb.sh APP ENV BUNDLE_DIR HEALTH_PATH
# Zips BUNDLE_DIR, registers it as a new application version, deploys it, verifies.
set -euo pipefail
APP="$1"; ENV_NAME="$2"; BUNDLE_DIR="$3"; HEALTH_PATH="$4"
REGION="${AWS_REGION:-ap-south-1}"

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET="elasticbeanstalk-${REGION}-${ACCOUNT}"
LABEL="gh-${GITHUB_SHA::8}-${GITHUB_RUN_NUMBER}"
ZIP="$(pwd)/${APP}-${LABEL}.zip"

if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "ERROR: S3 bucket $BUCKET not found. Create the Elastic Beanstalk environment in the console first."
  exit 1
fi

(cd "$BUNDLE_DIR" && zip -qr "$ZIP" . -x '*__pycache__*')
echo "Bundle contents:"; unzip -l "$ZIP" | awk '{print $4}' | grep -v '^$' | head -40

aws s3 cp "$ZIP" "s3://$BUCKET/$APP/$LABEL.zip"
aws elasticbeanstalk create-application-version --application-name "$APP" \
  --version-label "$LABEL" --source-bundle "S3Bucket=$BUCKET,S3Key=$APP/$LABEL.zip"
aws elasticbeanstalk update-environment --environment-name "$ENV_NAME" --version-label "$LABEL" >/dev/null

bash "$(dirname "$0")/eb_wait.sh" "$APP" "$ENV_NAME" "$LABEL" "$HEALTH_PATH"
