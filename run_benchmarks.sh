#!/bin/bash

PROFILE=$1
RPC_URL=$2
PRIVATE_KEY=$3

cat <<EOF > ./profiles.json
{
  "profiles": {
    "$PROFILE": {
      "node_url": "$RPC_URL",
      "funded_key": "$PRIVATE_KEY"
    }
  }
}
EOF

export PROFILE=$PROFILE

docker compose build
docker compose up --abort-on-container-exit --exit-code-from benchmark
EXIT_CODE=$?
docker compose down

echo "Benchmark exit code for profile ${PROFILE}: $EXIT_CODE"
exit $EXIT_CODE
