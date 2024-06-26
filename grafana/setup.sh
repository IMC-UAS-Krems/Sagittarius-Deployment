#! /bin/bash

wget $URL_CONFIG -O /grafana_dashboards/dashboard.json
cat /grafana_dashboards/dashboard.json | yq ".datasources" -y > /etc/grafana/provisioning/datasources/datasource.yaml
cat /grafana_dashboards/dashboard.json | yq ".dashboards" > /grafana_dashboards/dashboard.json
echo "Starting Grafana"
/run.sh
