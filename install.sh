#!/usr/bin/env bash
set -euo pipefail

uv sync --all-extras


uv pip install -e "sdks/pysdk[dev]"
uv pip install -e "services/packages/cl_ml_tools[dev]"
uv pip install -e "services/auth[dev]"
uv pip install -e "services/store[dev]"
uv pip install -e "services/compute[dev]"
uv pip install -e "apps/cli_python[dev]"
