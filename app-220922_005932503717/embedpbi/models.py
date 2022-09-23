from django.db import models
from django.contrib import messages

import msal
import requests
import json

class BaseConfig():


    # Can be set to 'MasterUser' or 'ServicePrincipal'
    AUTHENTICATION_MODE = 'ServicePrincipal'

    # Workspace Id in which the report is present
    WORKSPACE_ID = 'b6b3e837-f8e2-4360-a280-19f5a4491057'

    # Report Id for which Embed token needs to be generated
    REPORT_ID = 'b81d7892-0075-473c-abab-ece46fb8bed1'

    DATASET_IDS = ['384d9124-3ef6-49f1-bf39-c8bc5e088f12']

    # Id of the Azure tenant in which AAD app and Power BI report is hosted. Required only for ServicePrincipal authentication mode.
    TENANT_ID = 'f42a3004-bf11-4e94-861c-9893a7c2edf5'

    # Client Id (Application Id) of the AAD app
    CLIENT_ID = '527a7be6-5917-4603-9421-decf87e9abc8'

    # Client Secret (App Secret) of the AAD app. Required only for ServicePrincipal authentication mode.
    CLIENT_SECRET = 'gxg8Q~ArTdAcUgVnm2wWuAru9KX5jdw4EPWB_cfD'

    # Scope Base of AAD app. Use the below configuration to use all the permissions provided in the AAD app through Azure portal.
    SCOPE_BASE = ['https://analysis.windows.net/powerbi/api/.default']

    # URL used for initiating authorization request
    AUTHORITY_URL = 'https://login.microsoftonline.com/organizations'

    # Master user email address. Required only for MasterUser authentication mode.
    POWER_BI_USER = ''

    # Master user email password. Required only for MasterUser authentication mode.
    POWER_BI_PASS = ''

app_config = BaseConfig()

class ReportConfig:

    # Camel casing is used for the member variables as they are going to be serialized and camel case is standard for JSON keys

    reportId = None
    reportName = None
    embedUrl = None
    datasetId = None

    def __init__(self, report_id, report_name, embed_url, dataset_id = None):
        self.reportId = report_id
        self.reportName = report_name
        self.embedUrl = embed_url
        self.datasetId = dataset_id

class EmbedConfig:

    # Camel casing is used for the member variables as they are going to be serialized and camel case is standard for JSON keys

    tokenId = None
    accessToken = None
    tokenExpiry = None
    reportConfig = None

    def __init__(self, token_id, access_token, token_expiry, report_config):
        self.tokenId = token_id
        self.accessToken = access_token
        self.tokenExpiry = token_expiry
        self.reportConfig = report_config

class EmbedToken:

    # Camel casing is used for the member variables as they are going to be serialized and camel case is standard for JSON keys

    tokenId = None
    token = None
    tokenExpiry = None

    def __init__(self, token_id, token, token_expiry):
        self.tokenId = token_id
        self.token = token
        self.tokenExpiry = token_expiry

class EmbedTokenRequestBody:

    # Camel casing is used for the member variables as they are going to be serialized and camel case is standard for JSON keys

    datasets = None
    reports = None
    targetWorkspaces = None
    identities = None

    def __init__(self):
        self.datasets = []
        self.reports = []
        self.targetWorkspaces = []
        self.identities = []

class AadService:

    def get_access_token(self):
        '''Generates and returns Access token

        Returns:
            string: Access token
        '''

        response = None
        try:
            if app_config.AUTHENTICATION_MODE.lower() == 'masteruser':

                # Create a public client to authorize the app with the AAD app
                clientapp = msal.PublicClientApplication(app_config.CLIENT_ID, authority=app_config.AUTHORITY_URL)
                accounts = clientapp.get_accounts(username=app_config.POWER_BI_USER)

                if accounts:
                    response = clientapp.acquire_token_silent(app_config.SCOPE_BASE, account=accounts[0])

                if not response:
                    # Make a client call if Access token is not available in cache
                    response = clientapp.acquire_token_by_username_password(app_config.POWER_BI_USER, app_config.POWER_BI_PASS, scopes=app_config.SCOPE_BASE)

            # Service Principal auth is the recommended by Microsoft to achieve App Owns Data Power BI embedding
            elif app_config.AUTHENTICATION_MODE.lower() == 'serviceprincipal':
                authority = app_config.AUTHORITY_URL.replace('organizations', app_config.TENANT_ID)
                clientapp = msal.ConfidentialClientApplication(app_config.CLIENT_ID, client_credential=app_config.CLIENT_SECRET, authority=authority)

                # Make a client call if Access token is not available in cache
                response = clientapp.acquire_token_for_client(scopes=app_config.SCOPE_BASE)

            try:
                return response['access_token']
            except KeyError:
                raise Exception(response['error_description'])

        except Exception as ex:
            raise Exception('Error retrieving Access token\n' + str(ex))

class PbiEmbedService:

    def get_embed_params_for_single_report(self, workspace_id, report_id, identities, additional_dataset_id=None):
        '''Get embed params for a report and a workspace

        Args:
            workspace_id (str): Workspace Id
            report_id (str): Report Id
            additional_dataset_id (str, optional): Dataset Id different than the one bound to the report. Defaults to None.

        Returns:
            EmbedConfig: Embed token and Embed URL

        '''

        report_url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}'
        api_response = requests.get(report_url, headers=self.get_request_header())

        if api_response.status_code != 200:
            abort(api_response.status_code, description=f'Error while retrieving Embed URL\n{api_response.reason}:\t{api_response.text}\nRequestId:\t{api_response.headers.get("RequestId")}')

        api_response = json.loads(api_response.text)
        report = ReportConfig(api_response['id'], api_response['name'], api_response['embedUrl'])
        dataset_ids = [api_response['datasetId']]



        # Append additional dataset to the list to achieve dynamic binding later
        if additional_dataset_id is not None:
            dataset_ids.append(additional_dataset_id)

        embed_token = self.get_embed_token_for_single_report_single_workspace(report_id, dataset_ids, workspace_id, identities)
        embed_config = EmbedConfig(embed_token.tokenId, embed_token.token, embed_token.tokenExpiry, [report.__dict__])
        return json.dumps(embed_config.__dict__)
    def get_embed_token_for_single_report_single_workspace(self, report_id, dataset_ids, target_workspace_id=None, identities=None):
        '''Get Embed token for single report, multiple datasets, and an optional target workspace

        Args:
            report_id (str): Report Id
            dataset_ids (list): Dataset Ids
            target_workspace_id (str, optional): Workspace Id. Defaults to None.

        Returns:
            EmbedToken: Embed token
        '''

        request_body = EmbedTokenRequestBody()

        print('request bodyyy.  ', json.dumps(request_body.__dict__))

        for dataset_id in dataset_ids:
            request_body.datasets.append({'id': dataset_id})

        request_body.reports.append({'id': report_id})

        if target_workspace_id is not None:
            request_body.targetWorkspaces.append({'id': target_workspace_id})


#         userprinciple = None

        if identities is not None:
            request_body.identities = identities



        # Generate Embed token for multiple workspaces, datasets, and reports. Refer https://aka.ms/MultiResourceEmbedToken
        embed_token_api = 'https://api.powerbi.com/v1.0/myorg/GenerateToken'

        print('heyyyyy.   ', json.dumps(request_body.__dict__))

        api_response = requests.post(embed_token_api, data=json.dumps(request_body.__dict__), headers=self.get_request_header())

        if api_response.status_code != 200:
            print(api_response.status_code, "Description", f'Error while retrieving Embed token\n{api_response.reason}:\t{api_response.text}\nRequestId:\t{api_response.headers.get("RequestId")}')

        print('200 ----------------')

        api_response = json.loads(api_response.text)
        embed_token = EmbedToken(api_response['tokenId'], api_response['token'], api_response['expiration'])
        return embed_token
    def get_request_header(self):
        '''Get Power BI API request header

        Returns:
            Dict: Request header
        '''

        return {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + AadService().get_access_token()}
