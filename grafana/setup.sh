#! /bin/bash

wget $URL_CONFIG -O /config/sag_config.json
cat /config/sag_config.json | yq -P ".datasources" > /etc/grafana/provisioning/datasources/datasource.yaml
cat /config/sag_config.json | yq  -o=json ".dashboards" > /grafana_dashboards/dashboard.json
echo "Starting Grafana"
/run.sh
