import sys
from jsonpath_nz import log, jprint
from valibot.util import OUTPUT_DIR, TraceViewer
from valibot.jira_process import process_jira_steps, process_jira_links
from valibot.util import get_future_date, parse_url_to_variable, save_dict_to_file
from valibot.test_execution import testExecution
from playwright.sync_api import sync_playwright
import json
from typing import Dict, Any, Optional
import logging
from pathlib import Path
import tempfile
import webbrowser
import os

class ActionHandler:
    def __init__(self, config_dict: Dict[str, Any], prompt_dict: Dict[str, Any]):
        """
        Initialize action handler
        
        Args:
            config_dict: Configuration dictionary with URLs and credentials
            prompt_dict: Test data dictionary with action parameters
            logger: Logger object for logging
        """
        self.config = config_dict
        self.prompt_dict = prompt_dict
               
    def _validate_config(self, environment):
        """Validate configuration data"""
        required_fields = [f'tpo_url_{environment}', f'tpo_username_{environment}', f'tpo_password_{environment}', f'loc_url_{environment}', f'loc_username_{environment}', f'loc_password_{environment}']
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required configuration: {field}")

    def process_action(self) -> Dict[str, Any]:
        """
        Process action based on test data
        
        Returns:
            Dict containing result/status
        """
        try:
            action = self.prompt_dict.get('action', '').lower()
            environment = self.prompt_dict.get('environment', 'dev')
            
            # Validate action
            if not action:
                raise ValueError("Action is required")
                
            # Process based on action type
            if action in ['run', 'execution', 'execute']:
                return self._handle_run()
            elif action == 'update':
                return self._handle_update(environment)
            elif action == 'list':
                return self._handle_list()
            elif action in ['debug', 'show', 'trace']:
                return self._handle_debug()
            elif action in ['raise']:
                return self._handle_raise()
            else:
                raise ValueError(f"Invalid action: {action}")
                
        except Exception as e:
            log.error(f"Error processing action: {str(e)}")
            log.traceback(e)
            return {
                'status': 'error',
                'message': str(e)
            }

    def _handle_run(self) -> Dict[str, Any]:
        """Handle create action"""
        try:
            
            msg = process_jira_steps(self.config, self.prompt_dict)
            if not msg:
                raise ValueError("No test steps found")
            else:
                if isinstance(msg, dict):
                    testResult = testExecution(msg, self.config, self.prompt_dict)
            log.info(f"Trace file: {f"{OUTPUT_DIR}/trace.zip"}" )
            return(msg)
        except Exception as e:
            log.error(f"Run/Execution of Jira action failed: {str(e)}")
            log.traceback(e)
            raise

    def _handle_update(self, environment: str) -> Dict[str, Any]:
        """Handle update action"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                
                url = self.config['urls'].get(environment)
                creds = self.config['credentials'].get(environment)
                
                log.info(f"Updating loan in {url}")
                
                page.goto(url)
                page.fill('input[name="username"]', creds['username'])
                page.fill('input[name="password"]', creds['password'])
                page.click('button[type="submit"]')
                
                # Navigate to existing loan
                loan_number = self.prompt_dict.get('loan_number')
                if not loan_number or loan_number == 'None':
                    raise ValueError("Loan number required for update")
                    
                page.goto(f"{url}/loans/{loan_number}")
                
                return {
                    'status': 'success',
                    'message': f'Updated loan {loan_number}'
                }
                
        except Exception as e:
            log.error(f"Update action failed: {str(e)}")
            log.traceback(e)
            raise

    def _handle_list(self) -> Dict[str, Any]:
        """Handle list action"""
        try:
            storage = self.prompt_dict.get('storage')
            if not storage:
                raise ValueError("Storage handler required")
                
            # Create pattern for listing
            
            pattern = self.prompt_dict.get('loan_number', None)
            log.info(f" LOGPATH {self.prompt_dict.get('log_path')} -- {pattern}")
            if pattern:
                if pattern.isdigit():
                    pattern = f"loans/{pattern}/"
                files = storage.get_latest_s3_folders(pattern)
            elif self.prompt_dict.get('log_path') in ['loans/', 'loans']:
                pattern = f"loans/"
                files = storage.get_latest_s3_folders(pattern)
            else:
                pattern = f"no_loans/"
                files = storage.get_latest_s3_folders(pattern)

            return {
                'status': 'success',
                'files': files
            }
            
        except Exception as e:
            log.error(f"List action failed: {str(e)}")
            log.traceback(e)
            raise

    def _handle_debug(self) -> Dict[str, Any]:
        """Handle debug/show action"""
        try:
            # storage = self.prompt_dict.get('storage')
            # if not storage:
            #     raise ValueError("Storage handler required")
            
            trace_path = self.prompt_dict.get('log_path')
                
            # log.info(f"Downloading trace for loan: {log_path}")
                
            # # Download trace file
            # trace_path = storage.download_file_from_key(f"{log_path}")
                
            # Open trace viewer
            if not trace_path:
                raise ValueError("Trace file not found")
            
            # viewer_url = f"https://trace.playwright.dev/?trace={trace_path}"
            # log.info(f"Opening trace viewer: {viewer_url}")
            # webbrowser.open(viewer_url)
            trace_viewer = TraceViewer()
            trace_viewer.show_trace(trace_path, port=9222)
            
            return {
                'status': 'success',
                'message': 'Opened trace viewer',
                'trace_path': trace_path
            }
            
        except Exception as e:
            log.error(f"Debug action failed: {str(e)}")
            log.traceback(e)
            raise
    
    def _handle_raise(self, environment: str) -> Dict[str, Any]:
        """Handle create action"""
        try:
            #Raise JIRA ticket for failed test cases
            pass
                
        except Exception as e:
            log.error(f"Create action failed: {str(e)}")
            log.traceback(e)
            raise

        
def runEngine(config_dict, prompt_dict):
    '''
    Process the prompt and return the result
    '''
    try:
        # Create handler and process action
        jprint(prompt_dict)
        handler = ActionHandler(config_dict, prompt_dict)
        result = handler.process_action()
        # fmt_print(result)
        #based on action , type and channel,  call the appropriate function 
        #if action is create, then call the create function
        #if action is update, then call the update function
        #if action is list, then call the list function
        #if action is debug or show, then call the debug function
        #if action is any other value, then return an error message 
        
        return(f"Prompt Processing -- completed",True)
    except Exception as e:
        log.critical(f'!! Failed to process prompt {e}, {type(e).__name__}')
        log.critical(f'Error on line {(sys.exc_info()[-1].tb_lineno)}')
        log.traceback(e)
        return(f"Error: {e}",False)

