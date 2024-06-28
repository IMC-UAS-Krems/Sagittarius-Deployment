#! /bin/bash

wget $URL_CONFIG -O /grafana_dashboards/dashboard.json
cat /grafana_dashboards/dashboard.json | yq -P ".datasources" > /etc/grafana/provisioning/datasources/datasource.yaml
cat /grafana_dashboards/dashboard.json | yq -o=json ".dashboards"  > /grafana_dashboards/dashboard.json
echo "Starting Grafana"
/run.sh
