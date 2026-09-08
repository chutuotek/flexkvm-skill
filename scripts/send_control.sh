#!/bin/bash
# FlexKVM agent control interface quick-call script
# Usage: ./send_control.sh '{"events":[{"type":"click","x":0.5,"y":0.5}]}'

set -e

FlexKVM_IP="${FlexKVM_IP:-}"
FlexKVM_TOKEN="${FlexKVM_TOKEN:-}"
API_URL="https://${FlexKVM_IP}/api/v1/agent/control"

if [ $# -eq 0 ]; then
    echo "Usage: $0 '<json_payload>'"
    echo "Example:"
    echo "  $0 '{\"events\":[{\"type\":\"text\",\"value\":\"hello\"},{\"type\":\"delay\",\"ms\":300}]}'"
    echo ""
    echo "Environment variables:"
    echo "  FlexKVM_IP - FlexKVM device IP (required, e.g. 192.168.x.x)"
    echo "  FlexKVM_TOKEN - Agent API key (required, sk- + 32 hex, Settings -> Agent)"
    exit 1
fi

if [ -z "${FlexKVM_IP}" ]; then
    echo "Error: FlexKVM_IP is required"
    exit 1
fi

if [ -z "${FlexKVM_TOKEN}" ]; then
    echo "Error: FlexKVM_TOKEN is required"
    exit 1
fi

echo "Sending request to: ${API_URL}"
# -k: device serves HTTPS on the default port (443) with a self-signed certificate
curl -ks -X POST "${API_URL}" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${FlexKVM_TOKEN}" \
    -d "$1"