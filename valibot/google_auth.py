# Copyright 2024 AR USA LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json
import os.path
from google.auth.transport.requests import Request
from jsonpath_nz import parse_dict, parse_jsonpath, log, jprint

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

def get_google_auth_token():
    """
    Get Google OAuth2 refresh token and credentials
    """
    creds = None
    token_file = "token.json"
    credentials_file = "credentials.json"

    try:
        # Check if token.json exists and is valid
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            
        # If no valid credentials available, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    log.error(f"Token refresh failed: {e}")
                    creds = None
            
            # If still no valid creds, run OAuth flow
            if not creds:
                if not os.path.exists(credentials_file):
                    raise FileNotFoundError(
                        "credentials.json not found. Please download it from Google Cloud Console"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file, 
                    SCOPES,
                    redirect_uri='http://localhost:8080'
                )
                
                # Run local server to get authorization
                creds = flow.run_local_server(port=8080)
                
                # Save credentials
                with open(token_file, "w") as token:
                    token.write(creds.to_json())
                
                # Print refresh token for backup
                token_info = json.loads(creds.to_json())
                log.info("=== Save these credentials safely ===")
                log.info(f"Refresh Token: {token_info.get('refresh_token')}")
                log.info(f"Client ID: {token_info.get('client_id')}")
                log.info(f"Client Secret: {token_info.get('client_secret')}")
                log.info("===================================")
        
        return creds

    except Exception as e:
        log.error(f"Error getting Google credentials: {e}")
        raise

def validate_token():
    """
    Validate and print token information
    """
    try:
        if os.path.exists("token.json"):
            with open("token.json", "r") as f:
                token_data = json.load(f)
                
            log.info("Current Token Information:")
            log.info(f"Client ID: {token_data.get('client_id')}")
            log.info(f"Refresh Token Available: {'refresh_token' in token_data}")
            log.info(f"Token URI: {token_data.get('token_uri')}")
            return True
        return False
    except Exception as e:
        log.error(f"Error validating token: {e}")
        return False

if __name__ == "__main__":
    try:
        log.info("Starting Google OAuth Process...")
        
        # Check existing token
        if validate_token():
            response = input("Existing token found. Do you want to generate new token? (y/n): ")
            if response.lower() != 'y':
                log.info("Using existing token.")
                exit(0)
            
        # Get new token
        creds = get_google_auth_token()
        log.info("Successfully obtained Google credentials!")
        
        # Validate the new token
        validate_token()
        
    except Exception as e:
        log.error(f"Failed to get Google credentials: {e}") 