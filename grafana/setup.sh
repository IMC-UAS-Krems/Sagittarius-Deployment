#! /bin/bash

wget $URL_CONFIG -O /grafana_dashboards/dashboard.json
echo "Starting Grafana"
/run.sh
