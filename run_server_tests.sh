#!/bin/bash

# Set test artifact directory (optional - will use default if not set)
export TEST_ARTIFACT_DIR=/tmp/cl_server_test_artifacts

# Clean up any previous test artifacts
rm -rf $TEST_ARTIFACT_DIR


pushd services/packages/cl_ml_tools ; uv run pytest tests ; popd
pushd services/auth ; uv run pytest tests ; popd
pushd services/compute ; uv run pytest tests ; popd


