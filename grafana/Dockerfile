FROM grafana/grafana-enterprise:10.2.2

USER root

RUN apk add --no-cache wget
RUN mkdir -p /grafana_dashboards && chown -R grafana /grafana_dashboards

USER grafana

COPY ./provisioning/data_source.yaml /etc/grafana/provisioning/datasources/
COPY ./provisioning/dashboard.yaml /etc/grafana/provisioning/dashboards/
# RUN echo ${PWD} && ls -lR
COPY ./plugins/ /var/lib/grafana/plugins/
COPY ./setup.sh /

ENTRYPOINT ["/setup.sh"]
