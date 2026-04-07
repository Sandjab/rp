#!/usr/bin/env bash
cd "$(dirname "$0")"
python scripts/dashboard_server.py "$@"
