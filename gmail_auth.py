import os
import json
import tempfile
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
]


def get_gmail_service():
    creds = None
    token_from_env = bool(os.environ.get('GMAIL_TOKEN_JSON'))

    if token_from_env:
        creds = Credentials.from_authorized_user_info(
            json.loads(os.environ['GMAIL_TOKEN_JSON']), SCOPES
        )
    elif os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            if not token_from_env:
                with open('token.json', 'w') as f:
                    f.write(creds.to_json())
        else:
            creds_file, tmp_path = _resolve_credentials_file()
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)
            if tmp_path:
                os.unlink(tmp_path)
            with open('token.json', 'w') as f:
                f.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def _resolve_credentials_file():
    credentials_json = os.environ.get('GMAIL_CREDENTIALS_JSON')
    if credentials_json:
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        tmp.write(credentials_json)
        tmp.close()
        return tmp.name, tmp.name
    if os.path.exists('credentials.json'):
        return 'credentials.json', None
    raise FileNotFoundError(
        'No Gmail credentials found. '
        'Set GMAIL_CREDENTIALS_JSON env var or place credentials.json in this directory.'
    )
