# Azure deployment
- [Resource group](#resource-group)
- [App service plan](#app-service-plan)
- [App service](#app-service)
- [Storage](#storage)
- [Container registry](#container-registry)
- [Azure SDK](#azure-sdk)
- [Other options](https://learn.microsoft.com/en-us/azure/container-apps/compare-options)

## Resource group
[Docs overview](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/manage-resource-groups-portal#what-is-a-resource-group)

 - is a container that holds related resources for an Azure solution (main thing)
 - needs `name` and `region`

## App service plan
[Docs overview](https://learn.microsoft.com/en-us/azure/app-service/overview-hosting-plans)

- is needed to create `App Service`
- defines a set of compute resources for a web app to run
- needs `name`, `OS`, `region`, [`pricing plan`](https://azure.microsoft.com/en-us/pricing/details/app-service/linux/)

## App service
[Docs overview](https://learn.microsoft.com/en-us/azure/app-service/overview)

- HTTP-based service
- have custom domains
- docker image or compose (as well as other things)
- can be <ins>`Web App`</ins>, `Static Web App`, `Web App + Database` and `WordPress`
- needs `App Service Plan` and everything needed to crate an App

## Storage
[Docs overview](https://learn.microsoft.com/en-us/azure/storage/common/storage-introduction)

- REST and libraries
- components:
    - [Azure Blobs](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-introduction): A massively scalable object store for text and binary data
    - [Azure Files](https://learn.microsoft.com/en-us/azure/storage/files/storage-files-introduction): Managed file shares for cloud or on-premises deployments.
    - [Azure Elastic SAN (preview)](https://learn.microsoft.com/en-us/azure/storage/elastic-san/elastic-san-introduction): A fully integrated solution that simplifies deploying, scaling, managing, and configuring a SAN in Azure.
    - [Azure Queues](https://learn.microsoft.com/en-us/azure/storage/queues/storage-queues-introduction): A messaging store for reliable messaging between application components.
    - [Azure Tables](https://learn.microsoft.com/en-us/azure/storage/tables/table-storage-overview): A NoSQL store for schemaless storage of structured data.
    - [Azure managed Disks](https://learn.microsoft.com/en-us/azure/virtual-machines/managed-disks-overview): Block-level storage volumes for Azure VMs.

- [Files pricing](https://azure.microsoft.com/en-us/pricing/details/storage/files/)
- [Tables pricing](https://azure.microsoft.com/en-us/pricing/details/storage/tables/)
- REST API available

## Container registry
[Docs overview](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-intro)

- [azure pricing](https://azure.microsoft.com/en-us/pricing/details/container-registry/), [docker pricing](https://www.docker.com/pricing/) and [github pricing](https://docs.github.com/en/billing/managing-billing-for-github-packages/about-billing-for-github-packages)
- can be controlled with [`Active Directory`](https://learn.microsoft.com/en-us/azure/active-directory/develop/app-objects-and-service-principals?tabs=browser) (don't have access)

## Azure SDK
[Docs](https://github.com/Azure/azure-sdk) | [Python docs](https://azure.github.io/azure-sdk-for-python/)

- [azure-mgmt-web](https://azuresdkdocs.blob.core.windows.net/$web/python/azure-mgmt-web/7.1.0/index.html) - manages apps and app plans (**API version** `2018_02_01`)
- [azure-storage-file-share](https://azuresdkdocs.blob.core.windows.net/$web/python/azure-storage-file-share/12.14.2/index.html) - manages file shares
- [azure-identity](https://azuresdkdocs.blob.core.windows.net/$web/python/azure-identity/1.14.1/index.html) - auth

### Issues
As for the moment, I can't authenticate myself other than with `Azure CLI` session because `AZURE_TENANT_ID` is needed. (https://aad.portal.azure.com/)

## Other options to deploy docker
https://learn.microsoft.com/en-us/azure/container-apps/compare-options
