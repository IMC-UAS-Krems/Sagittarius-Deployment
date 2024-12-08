FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY requirements.txt .

RUN pip install --trusted-host pypi.python.org -r requirements.txt \
    && rm -rf /root/.cache/pip \
    && rm -rf /tmp/* \
    && rm -rf /usr/local/lib/python3.11/site-packages/azure/mgmt/web/v2015* \
    && rm -rf /usr/local/lib/python3.11/site-packages/azure/mgmt/web/v2016_08_01/ \
    && rm -rf /usr/local/lib/python3.11/site-packages/azure/mgmt/web/v2016_09_01/ \
    && rm -rf /usr/local/lib/python3.11/site-packages/azure/mgmt/web/v2018_11_01/ \
    && rm -rf /usr/local/lib/python3.11/site-packages/azure/mgmt/web/v2019* \
    && rm -rf /usr/local/lib/python3.11/site-packages/azure/mgmt/web/v2020* \
    && rm -rf /usr/local/lib/python3.11/site-packages/azure/mgmt/web/v2021*
    # && rm -rf /usr/local/lib/python3.11/site-packages/azure/mgmt/web/v2022*


COPY . .

EXPOSE 9001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9001"]
