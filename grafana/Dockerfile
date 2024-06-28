FROM grafana/grafana-enterprise:10.2.2

USER root

RUN apk add --no-cache wget
RUN wget https://github.com/mikefarah/yq/releases/download/v4.44.2/yq_linux_amd64 -O /usr/bin/yq && chmod +x /usr/bin/yq

RUN mkdir -p /grafana_dashboards && chown -R grafana /grafana_dashboards
RUN mkdir -p /config && chown -R grafana /config

USER grafana

# COPY ./provisioning/data_source.yaml /etc/grafana/provisioning/datasources/
COPY ./provisioning/dashboard.yaml /etc/grafana/provisioning/dashboards/
# RUN echo ${PWD} && ls -lR
COPY ./plugins/ /var/lib/grafana/plugins/
COPY ./setup.sh /

ENTRYPOINT ["/setup.sh"]
