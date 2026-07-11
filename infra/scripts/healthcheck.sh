#!/usr/bin/env bash
set -euo pipefail

curl -fsS "http://localhost/api/v1/health/live"
curl -fsS "http://localhost/api/v1/health/ready"
curl -fsS "http://localhost/api/v1/health/metrics"
