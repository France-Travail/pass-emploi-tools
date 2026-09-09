#!/bin/bash
set -e

if [ -n "$1" ]; then
  SIMULATION_CMD="gatlingRun-$1"
fi

GATLING_RUN_CMD=${SIMULATION_CMD:-'gatlingRun'}
echo ${GATLING_RUN_CMD}
./gradlew ${GATLING_RUN_CMD}
