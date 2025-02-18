import os
import re
import sys
import json
import getpass
import platform
import argparse
import signal
from datetime import datetime
from valibot.util import GeminiClient, TextCipher, validate_email, extract_json
from valibot.aws_process import S3Handler
from valibot.engine import runEngine
from jsonpath_nz import log, jprint

#Global variables
#Signal handler
GLB_PROMPT = f'''Your task as developer
You will be provided with text delimited by triple backticks
Provide them in JSON format with the following keys:
action, db_file, jira_project, jira_number, storage, log_path
where
action key = any of the following actions [run, execution, analysis, update, list, show, filter, update_filter, debug, trace, raise, execute] or default set to None
jira_project key = any of the following JIRA projects that has three letters default set to XSP
jira_number key = any of the JIRA number that has patttern of <jira_project>-<number> or default set to None
log_path key =  path that contains debug, trace, log, trace.zip or default set to None
'''
#Signal handler
def signal_handler(sig, frame):
    '''Signal handler for Ctrl+C'''
    log.info('\n !!!You pressed Ctrl+C , Exiting ...... ')
    sys.exit(0)


def s3_process(bucket_name, **operations):
    '''Process the prompt using GeminiClient'''
    try:
        s3 = S3Handler('valibot-dev2')

        # Example: Upload single file with metadata
        s3.upload_file(
            'document.pdf',
            'loans',
            metadata={'category': 'contract'}
        )

        # Example: Upload entire folder
        results = s3.upload_folder(
            'local_folder',
            'loans/documents'
        )
        print(f"Uploaded {len(results['success'])} files")

        # Example: Upload and extract zip
        zip_results = s3.upload_zip(
            'files.zip',
            'loans_snapshot',
            extract=True
        )
        log.info(f"Processed {len(zip_results['success'])} files from zip")

        # Example: Batch upload
        batch_results = s3.upload_batch(
            ['file1.pdf', 'file2.jpg'],
            'loans',
            prefix='2024/01'
        )
        log.info(f"Batch uploaded {len(batch_results['success'])} files")

    except Exception as e:
        log.critical(f'!! Failed S3 operation {e}, {type(e).__name__}')
        log.critical(f'Error on line {(sys.exc_info()[-1].tb_lineno)}')
        log.traceback(e)
        return(f"S3 Error: {e}",False)
        

def gemini_client_process(prompt, api_key):
    '''Process the prompt using GeminiClient'''
    promptClient = GeminiClient(api_key=api_key)
    response = promptClient.generate_response(
        prompt,
        temperature=0.7,
        top_p=0.95,
        top_k=40,
        max_output_tokens=1000,
        candidate_count=1
    )
    return response


def parse_opts(argv):
    """
    Parsing command line argument for tool 'valibot' 
    """
    parser = argparse.ArgumentParser(prog="valibot")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-p", "--prompt", type=str, nargs='?', default=None , help="Prompt: Generative Prompt for the Date Analytic bot")
    group.add_argument("-f", "--file", type=str, nargs='?', default=None , help="Prompt: provided as a file (use -t to get the prompt template)")
    parser.add_argument("-d", "--debug", action="store_true", help="Debug: Captures debug to the default temp file")
    parser.add_argument("-t", "--template", action="store_true", help="template: Generative Prompt template file")
    
    if len(argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser.parse_args()
    

def main(argv):
    '''Main function to execute PAM rules'''
    try:
        opts = parse_opts(sys.argv)
        config = None
        log.info(f"Prompt Engineering request -- started")
        prompt = opts.prompt
        if not prompt:
            if opts.file:
                prompt = open(opts.file, 'r').read()
            else:
                return(f"Please provide prompt: to start the bot",False)
        
        if os.path.exists('config.json'):
            with open('config.json', 'r') as file:
                config = json.load(file)
        else:
            log.error(f"!! Error : config.json file NOT FOUND")
            log.info(f"Creating a new config.json file at {os.path.join(os.getcwd(), 'config.json')}")  
            #create a new config.json file
            with open('config.json', 'w') as file:
                json.dump({'api_key': 'None', 'db_file': 'None'}, file)
            return(f'''
                    --- To Start the bot ---
                    provide prompt: 'set api_key <YOUR GOOGLE_API_KEY> '
                    Provide prompt: 'set db_file <YOUR DB_FILE_PATH> '
                    ''',False)
        
        #Prompt starts with 'set' and follows by key and value
        public_key = f"{getpass.getuser()}@{platform.system()}"
        if str(prompt).lower().startswith('set '):
            set_patterns = {
                'colon': r'^set\s+([^\s:]+)\s*:\s*(.+)$',      # set key: value
                'equals': r'^set\s+([^\s=]+)\s*=\s*(.+)$',     # set key=value
                'space': r'^set\s+([^\s:=]+)\s+([^:=].+)$'     # set key value
            }
            key = None
            value = None
            sensitive_keys = ['key', 'secret', 'password', 'pass'] 
            # Try each pattern
            for pattern_name, pattern in set_patterns.items():
                match = re.match(pattern, prompt, re.IGNORECASE)
                if match:
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    #encrypt the sensitive data
                    if any(sensitive in key.lower() for sensitive in sensitive_keys):
                        value = TextCipher().encrypt(value, public_key)
                    break
            if key is None or value is None:
                return(f"Invalid set prompt format. Please use 'set key value' format.",False)
            config[key] = value
            log.info(f"Config: {config}")
            with open('config.json', 'w') as file:
                json.dump(config, file)
            return(f"Config updated successfully with {key} : {value}",True)

        if 'api_key' not in config.keys():
            return(f"Provide prompt: 'set api_key <YOUR GOOGLE_API_KEY>' ",False)
        
        #S3 bucket configuration - to ensure the output files are stored in S3 bucket
        storage = "local"
        if 's3_bucket' not in config.keys():
            log.info(f"S3_bucket NOT FOUND in config.json file. Hence results/ouput logs are stored locally")
        elif not config['s3_bucket'].startswith('valibot'):
            log.info(f"S3_bucket doesn;t start with valibot in config.json file. Hence results/ouput logs are stored locally")
        else:
            log.info(f"S3_bucket has results and output logs")
            s3 = S3Handler(config['s3_bucket'])
            storage =  s3
            
        #Generative AI prompts
        api_key = TextCipher().decrypt(config['api_key'], public_key)
        if not api_key:
            return(f"Provide prompt: 'set api_key <YOUR GOOGLE_API_KEY>' ",False)
        prompt = f'''{GLB_PROMPT}
        ```{prompt}```
        '''
        prompt_response = gemini_client_process(prompt, api_key)
        # fmt_print(prompt_response)
        if prompt_response['metadata']['status'] == 'error':
            return(f'''Failed to get response from Gemini [ {prompt_response['response']['error']} ], 
                    Try again by providing valid api_key (set api_key <YOUR GOOGLE_API_KEY>)''',False)
        else:
            json_data = extract_json(prompt_response['response']['content'])
            count= 0
            while not json_data:
                prompt_response = gemini_client_process(prompt, api_key)
                json_data = extract_json(prompt_response['response']['content'])
                count += 1
                if count > 3:
                    return(f"Failed to extract JSON from the prompt response after 3 attempts",False)
                else:
                    log.info(f"Retrying {count} time again... ")

            
            msg = runEngine(config, json_data)
            return(msg, True)
        
    except Exception as e:
        log.critical(f'!! Failed to capture log {e}, {type(e).__name__}')
        log.critical(f'Error on line {(sys.exc_info()[-1].tb_lineno)}')
        log.traceback(e)
        return(f"Error: {e}",False)
    

if __name__ == "__main__":
    '''Execute all the Rules'''
    #Press Control C to exit the code anytime
    
    signal.signal(signal.SIGINT, signal_handler) 
    # log.info(f"Arguments for {__file__} : {sys.argv}")
    opts = parse_opts(sys.argv)
    DEBUG = opts.debug
    try:
        msg, status = main(sys.argv)
        log.info(f"{msg}  -- {status}")
    except Exception as e:  
        log.critical(f'!! Prmpt failed : [{e}], {type(e).__name__}')
        log.critical(f'Error on line {(sys.exc_info()[-1].tb_lineno)}')
        log.traceback(e)