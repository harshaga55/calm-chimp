#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "${ROOT_DIR}"

echo ">> Cleaning previous Briefcase artifacts"
rm -rf "${ROOT_DIR}/build/calm_chimp" "${ROOT_DIR}/dist/macOS"

echo ">> Ensuring dependencies are installed"
poetry install --with dev

APP_NAME="calm_chimp"
ARCH="arm64"

echo ">> Creating Briefcase app template (architecture: ${ARCH})"
poetry run briefcase create macOS app -a "${APP_NAME}" --no-input

echo ">> Building macOS app bundle"
poetry run briefcase build macOS app -a "${APP_NAME}" --no-input

echo ">> Packaging macOS DMG"
poetry run briefcase package macOS app -a "${APP_NAME}" --no-input --adhoc-sign --no-notarize

echo ">> Package ready: dist/macOS"
