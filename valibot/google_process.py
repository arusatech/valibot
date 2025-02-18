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

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from jsonpath_nz import parse_dict, parse_jsonpath, log, jprint

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def gTestCase(jira_ID:str, sheet_ID:str, sheet_name:str):
    '''
    Main function for google process
    '''
    try:
        creds = {
            "token":None,
            "refresh_token":"1//06A39wMyRWSJPCgYIARAAGAYSNwF-L9IrekmuF8CBoo-ZFDOj49QNIuxdhwlTMIFZARxfMU5YUNIYG10_iI-umOCsX5M0EPpqWbc",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "1039799392500-a215b5357rje7uag2p3k7m8dheiude3b.apps.googleusercontent.com",
            "client_secret": "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",
            "scopes":SCOPES
            
        }
        gcreds  = Credentials(**creds)
        drive = build('drive', 'v3', credentials=gcreds, cache_discovery=True)
        gsheetService = build("sheets", "v4", credentials=gcreds)
        sheet = gsheetService.spreadsheets()
        result = sheet.values().get(spreadsheetId=sheet_ID, range=sheet_name).execute()
        cellValues = result.get('values', [])
        data = []
        if len(cellValues) > 0:
            keys = cellValues[0]
            for i in range(1, len(cellValues)):
                data.append(dict(zip(keys, cellValues[i] + [""] * (len(keys)-len(cellValues[i])))))
                # data.append(dict(zip(keys, cellValues[i])))

        total_scenarios = len(data)
        log.info(f"TotalScenarions : {total_scenarios}")
        if not jira_ID:
            return data
        else:
            for row in data:
                if row["TestCaseID"].lower() == str(jira_ID).lower():
                    return row
                else:
                    return f"No test case found for {jira_ID}"
            
    except Exception as e:
        log.error(e)
        log.traceback(e)


# if __name__ == "__main__":
#     testcasteID= "xsp-59"
#     testcase = gTestCase(testcasteID)
#     jprint(testcase)
# [END sheets_quickstart]