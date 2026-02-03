#!/bin/bash

# Set test artifact directory (optional - will use default if not set)
export TEST_ARTIFACT_DIR=/tmp/cl_server_test_artifacts

# Clean up any previous test artifacts
rm -rf $TEST_ARTIFACT_DIR

uv run pytest services/auth/tests
uv run pytest services/packages/cl_ml_tools/tests
uv run pytest services/compute/tests
uv run pytest services/store/tests --auth-url=http://localhost:8010 --compute-url=http://localhost:8012 --username=admin --password=admin 
uv run pytest sdks/pysdk/tests/ --auth-url=http://localhost:8010 --compute-url=http://localhost:8012 --store-url=http://localhost:8011 --username=admin --password=admin


