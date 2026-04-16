#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate
PYTHONPATH=src python -m ai_daily.cli init-db
PYTHONPATH=src python -m ai_daily.cli seed-sources

