#!/usr/bin/env bash
set -euo pipefail

uv sync --all-extras


uv pip install -e sdks/pysdk
uv pip install -e services/packages/cl_ml_tools
uv pip install -e services/auth
uv pip install -e services/shared
uv pip install -e services/store
uv pip install -e services/compute
