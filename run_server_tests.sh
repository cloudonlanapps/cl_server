#!/bin/bash

# Set test artifact directory (optional - will use default if not set)
export TEST_ARTIFACT_DIR=/tmp/cl_server_test_artifacts

# Default values
SERVER_IP="localhost"
EXTRA_ARGS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --ip)
      SERVER_IP="$2"
      shift # past argument
      shift # past value
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift # past argument
      ;;
  esac
done

# Clean up any previous test artifacts
rm -rf $TEST_ARTIFACT_DIR

pushd sdks/dartsdk
./test/run_integration.sh --ip ${SERVER_IP}
popd 

uv run pytest sdks/pysdk/tests/ --auth-url=http://${SERVER_IP}:8010 --compute-url=http://${SERVER_IP}:8012 --store-url=http://${SERVER_IP}:8011 --username=admin --password=admin  --mqtt-url=mqtt://${SERVER_IP}:1883 "${EXTRA_ARGS[@]}"
uv run pytest apps/cli_python/tests/ --auth-url=http://192.168.0.105:8010 --compute-url=http://192.168.0.105:8012 --store-url=http://192.168.0.105:8011 --mqtt-url=mqtt://192.168.0.105:1883 --username=admin --password=admin
uv run pytest services/store/tests --auth-url=http://${SERVER_IP}:8010 --compute-url=http://${SERVER_IP}:8012                                      --username=admin --password=admin --mqtt-url=mqtt://${SERVER_IP}:1883  --qdrant-url=http://192.168.0.105:6333 "${EXTRA_ARGS[@]}"
uv run pytest services/compute/tests "${EXTRA_ARGS[@]}"
uv run pytest services/auth/tests "${EXTRA_ARGS[@]}"
uv run pytest services/packages/cl_ml_tools/tests "${EXTRA_ARGS[@]}"
uv run pytest services/packages/cl_ml_tools/tests --mqtt-url=mqtt://${SERVER_IP}:1883 "${EXTRA_ARGS[@]}"
