"""
Usage: main.py (dash | grafana) (create | delete) <filename> <webapp_name>

Options:
    -h --help   Show help
"""

import argparse
import logging
import os
from base64 import b64encode
from string import Template
from typing import Literal

from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.web.models import NameValuePair, Site, SiteConfig
from azure.storage.fileshare import ShareFileClient
from dotenv import dotenv_values, load_dotenv

load_dotenv()

logging.getLogger("azure").setLevel(logging.ERROR)

SUBSCRIPTION_ID = os.environ["AZURE_SUBSCRIPTION_ID"]
GROUP_NAME = os.environ["AZURE_GROUP_NAME"]
APP_PLAN = os.environ["AZURE_APP_PLAN"]
FILE_SHARE_CONNECTION_STRING = os.environ["AZURE_FILE_SHARE_CONNECTION_STRING"]
FILE_SHARE_NAME = os.environ["AZURE_FILE_SHARE_NAME"]

parser = argparse.ArgumentParser()
parser.add_argument("target", choices=["dash", "grafana"], help="Target to deploy")
parser.add_argument("action", choices=["create", "delete"], help="Action to perform")
parser.add_argument("filename", help="Name of the file to upload or delete")
parser.add_argument("webapp_name", help="Name of the web app to create or delete")


def log(log_string: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"\033[93m{log_string}..\033[0m", end="\r")
            func(*args, **kwargs)
            print(f"\033[92m{log_string}...✅\033[0m")

        return wrapper

    return decorator


def generate_base64_compose(target: Literal["dash", "grafana"]) -> str:
    path = f"{target}/docker-compose.yml"
    with open(path, "r") as f:
        compose = f.read()
    return b64encode(compose.encode("utf-8")).decode("utf-8")


@log("Uploading config file to file share")
def upload_file_to_share(file_name: str, target: Literal["dash", "grafana"]):
    file_share = ShareFileClient.from_connection_string(
        conn_str=FILE_SHARE_CONNECTION_STRING,
        share_name=FILE_SHARE_NAME,
        file_path=f"{target}_{file_name}",
    )
    with open(f"{target}/conf/{file_name}", "rb") as f:
        file_share.upload_file(f)


@log("Creating web app")
def create_web_app(
    web_app_name: str,
    compose_b64: str,
    file_name: str,
    target: Literal["dash", "grafana"],
):
    credential = DefaultAzureCredential()

    client = WebSiteManagementClient(
        credential, SUBSCRIPTION_ID, api_version="2018-02-01"
    )  # NOTE: api version is important! this is the latest version that is supported and it works

    plan = client.app_service_plans.get(GROUP_NAME, APP_PLAN)

    # app_settings aka environment variables
    app_settings = dotenv_values(".env.app")
    app_settings["URL_CONFIG"] = Template(app_settings["URL_CONFIG"]).safe_substitute(
        file_name=f"{target}_{file_name}"
    )

    client.web_apps.begin_create_or_update(
        GROUP_NAME,
        web_app_name,
        Site(
            type="Microsoft.Web/sites",
            kind="app,linux,container",
            location="Germany West Central",
            client_affinity_enabled=False,
            server_farm_id=plan.id,
            https_only=True,
            site_config=SiteConfig(
                linux_fx_version="COMPOSE|{}".format(compose_b64),
                ftps_state="FtpsOnly",
                always_on=False,
                app_settings=[
                    NameValuePair(
                        name=k,
                        value=v,
                    )
                    for k, v in app_settings.items()
                ],
                http_logging_enabled=True,
            ),
        ),
    ).result()


@log("Deleting file from file share")
def delete_file(file_name: str, target: Literal["dash", "grafana"]):
    file_share = ShareFileClient.from_connection_string(
        conn_str=FILE_SHARE_CONNECTION_STRING,
        share_name=FILE_SHARE_NAME,
        file_path=f"{target}_{file_name}",
    )

    file_share.delete_file()


@log("Deleting web app")
def delete_web_app(web_app_name: str):
    credential = DefaultAzureCredential()
    client = WebSiteManagementClient(
        credential, SUBSCRIPTION_ID, api_version="2018-02-01"
    )  # NOTE: api version is important! this is the latest version that is supported and it works
    client.web_apps.delete(GROUP_NAME, web_app_name, delete_empty_server_farm=False)


def main():
    args = parser.parse_args()

    if args.action == "delete":
        delete_web_app(args.webapp_name)
        delete_file(args.filename, args.target)

        exit(0)

    upload_file_to_share(args.filename, args.target)
    base64_compose = generate_base64_compose(args.target)
    create_web_app(args.webapp_name, base64_compose, args.filename, args.target)


if __name__ == "__main__":
    main()
