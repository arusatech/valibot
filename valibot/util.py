import os
import re
import sys
import json
import random
import subprocess
import shutil
from pathlib import Path
import tempfile
import google.generativeai as genai
import base64
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import Page, expect
from typing import Optional, Dict, Any
from datetime import datetime
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from jsonpath_nz import log, jprint

#Global setting
#create OUTPUT_DIR if not exists from current working directory

OUTPUT_DIR = os.path.join(os.getcwd(), f'valibot_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def find_common_prefix(strings):
    """Find the longest common prefix among a list of strings"""
    if not strings:
        return ""
    
    # Convert to list if input is dict_keys
    strings = list(strings)
    
    # Get the shortest string length
    shortest = min(len(s) for s in strings)
    
    # Find the longest common prefix
    for i in range(shortest):
        char = strings[0][i]
        if not all(s[i] == char for s in strings):
            return strings[0][:i]
    
    return strings[0][:shortest]

def remove_common_prefix(json_dict, common_prefix):
    return {
        key.replace(common_prefix, ''): value 
        for key, value in json_dict.items()
    }

def validate_email(email):
    '''Validate the email address'''
    # RFC 5322 Official Standard Email Pattern
    email_pattern = r'''(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])'''
    if not re.match(email_pattern, email, re.IGNORECASE):
        return ("Invalid email format", False)
    return (f"Logged in user : {email}", True)

def extract_json(content: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from content string that may be wrapped in markdown code blocks
    
    Args:
        content (str): Content string containing JSON
        
    Returns:
        Optional[Dict[str, Any]]: Parsed dictionary or None if invalid
    """
    try:
        # Pattern to match JSON content between code blocks
        json_pattern = r'```(?:json)?\n(.*?)\n```'
        
        # Try to find JSON content in code blocks
        match = re.search(json_pattern, content, re.DOTALL)
        if match:
            # Extract JSON string from code block
            json_str = match.group(1)
        else:
            # Try parsing the content directly
            json_str = content
            
        # Parse JSON string to dict
        return json.loads(json_str)
        
    except Exception as e:
        log.error(f"Error parsing content: {str(e)}")
        log.traceback(e)
        return None  

def save_dict_to_file(data_dict, filepath):
    """Save dictionary to a JSON file, creating directories if they don't exist.
    
    Args:
        data_dict (dict): Dictionary to save
        filepath (str): Full path including filename where the JSON should be saved
    """
    try:
        # Create directory path if it doesn't exist
        directory = os.path.dirname(filepath)
        os.makedirs(directory, exist_ok=True)
        
        # Save the dictionary as JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, indent=4)
        log.info(f"Successfully saved data to {filepath}")
        
    except Exception as e:
        log.error(f"Failed to save dictionary to file: {e}")
        log.error(f"Filepath: {filepath}")
        log.traceback(e)
        raise

def parse_url_to_variable(url: str) -> str:
    """
    Parse URL and convert last path and query params to variable name
    
    Args:
        url: Full URL string
        
    Returns:
        Variable name with underscores
    """
    def is_uuid(text: str) -> bool:
        """Check if string is UUID format"""
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(uuid_pattern, text.lower()))
    
    def get_path_after_uuid(path_parts: List[str]) -> str:
        """
        Get path components after UUID
        
        Args:
            path_parts: List of path components
            
        Returns:
            Path components after UUID or UUID if no components after
        """
        try:
            # Find UUID in path
            uuid_index = -1
            for i, part in enumerate(path_parts):
                if is_uuid(part):
                    uuid_index = i
                    break
            
            if uuid_index != -1:
                # If components exist after UUID, return them
                if uuid_index < len(path_parts) - 1:
                    return '_'.join(path_parts[uuid_index + 1:][:4])
                # If no components after UUID, return UUID
                return path_parts[uuid_index]
                
            # If no UUID found, return last component
            return path_parts[-1] if path_parts else ''
            
        except Exception as e:
            log.error(f"Error processing path parts: {str(e)}")
            log.traceback(e)
            return None
    
    retDict = {}
    try:
        # Parse URL
        parsed = urlparse(url)
        
        # Get path parts
        path_parts = [p for p in parsed.fragment.split('/') if p]
        for i, part in enumerate(path_parts):
            if is_uuid(part):
                retDict['UUID'] = part
                path_parts = path_parts[i+1:]
                break

        path_parts = [part[:4] for part in path_parts]
        log.info(f"path_parts: {path_parts}")
        clean_parts = []
        for part in path_parts:
            # Replace special characters with underscore
            clean_part = re.sub(r'[^a-zA-Z0-9]', '_', part)
            # Remove consecutive underscores
            clean_part = re.sub(r'_+', '_', clean_part)
            clean_parts.append(clean_part)
            
        # Join all parts with underscore
        retDict['variable'] = '_'.join(clean_parts)
        retDict['variable'] = f"{retDict['variable']}_{random.randint(1000, 9999)}"
        # log.info(f"retDict: {retDict}")
        return retDict
        
    except Exception as e:
        log.error(f"Error parsing URL: {str(e)}")
        log.traceback(e)
        retDict['variable'] = 'url_error'
        return(retDict)

def get_future_date(days_ahead=30):
    """
    Get a future date formatted as 'Month day_in_words year'
    Example: 'February twenty seventh 2025'
    
    Args:
        days_ahead (int): Number of days to add to current date
    
    Returns:
        str: Formatted date string
    """
    try:
        # Get future date
        future_date = datetime.now() + timedelta(days=days_ahead)
        # Get month name
        month = future_date.strftime('%B')
        # Get year
        year = future_date.year
        # Hard-code the day since it's always "twenty seventh"
        return f"{month} twentie seventh {year}"
    except Exception as e:
        log.error(f"Error getting future date: {str(e)}")
        log.traceback(e)
        return None
  
class GeminiClient:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client
        
        Args:
            api_key (str, optional): Gemini API key. If not provided, will look for GOOGLE_API_KEY env variable
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY key must be provided either directly from config.json or through environment variable")
        
        # Configure the library
        genai.configure(api_key=self.api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel('gemini-pro')
           
    def _create_response_template(self, prompt: str, response: str, status: str = "success", 
                                error: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a standardized JSON response template
        
        Args:
            prompt (str): Original prompt
            response (str): Generated response
            status (str): Status of the generation (success/error)
            error (str, optional): Error message if any
            
        Returns:
            dict: Formatted response dictionary
        """
        return {
            "metadata": {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "model": "gemini-pro",
                "status": status
            },
            "request": {
                "prompt": prompt,
                "type": "generate_content"
            },
            "response": {
                "content": response if status == "success" else None,
                "error": error if status == "error" else None
            }
        }

    def generate_response(self, prompt: str, **kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate response using Gemini in JSON format
        
        Args:
            prompt (str): The input prompt
            **kwargs: Additional parameters for the generation
                     (temperature, top_p, top_k, max_output_tokens, etc.)
        
        Returns:
            dict: JSON formatted response
        """
        try:
            # Generate the response
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(**kwargs)
            )
            
            # Return formatted response
            return self._create_response_template(prompt, response.text)
            
        except Exception as e:
            return self._create_response_template(
                prompt=prompt,
                response="",
                status="error",
                error=str(e)
            )
    
    def generate_chat_response(self, messages: list, **kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate response in chat mode with JSON format
        
        Args:
            messages (list): List of message dictionaries with 'role' and 'content'
            **kwargs: Additional parameters for the generation
        
        Returns:
            dict: JSON formatted response
        """
        try:
            # Start a chat
            chat = self.model.start_chat()
            
            # Send all messages
            last_prompt = ""
            for message in messages:
                if message['role'] == 'user':
                    last_prompt = message['content']
                    response = chat.send_message(message['content'], **kwargs)
            
            # Return formatted response
            return self._create_response_template(last_prompt, response.text)
            
        except Exception as e:
            return self._create_response_template(
                prompt=messages[-1]['content'] if messages else "",
                response="",
                status="error",
                error=str(e)
            )

class TextCipher:
    '''
    TextCipher class to encrypt and decrypt text
    ''' 
    def __init__(self, salt: bytes = None):
        """
        Initialize TextCipher with optional salt
        
        Args:
            salt (bytes, optional): Salt for key derivation
        """
        self.salt = salt if salt else os.urandom(16)
        
    def _generate_key(self, password: str) -> bytes:
        """
        Generate encryption key from password
        
        Args:
            password (str): Password to derive key from
            
        Returns:
            bytes: Derived key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def encrypt(self, text: str, password: str) -> str:
        """
        Encrypt plain text using password
        
        Args:
            text (str): Text to encrypt
            password (str): Password for encryption
            
        Returns:
            CipherResult: Encryption result
        """
        try:
            # Input validation
            if not text or not password:
                return(None)
            
            # Generate key from password
            key = self._generate_key(password)
            cipher_suite = Fernet(key)
            
            # Encrypt
            cipher_text = cipher_suite.encrypt(text.encode())
            
            # Combine salt and cipher text
            combined = base64.urlsafe_b64encode(self.salt + cipher_text)
            
            return(combined.decode())
            
        except Exception as e:
            log.traceback(e)
            return None

    def decrypt(self, cipher_text: str, password: str) -> str:
        """
        Decrypt cipher text using password
        
        Args:
            cipher_text (str): Text to decrypt
            password (str): Password for decryption
            
        Returns:
            CipherResult: Decryption result
        """
        try:
            # Input validation
            if not cipher_text or not password:
                return(None)
            
            
            # Decode combined salt and cipher text
            combined = base64.urlsafe_b64decode(cipher_text.encode())
            
            # Extract salt and cipher text
            salt = combined[:16]
            actual_cipher_text = combined[16:]
            
            # Set salt and generate key
            self.salt = salt
            key = self._generate_key(password)
            cipher_suite = Fernet(key)
            
            # Decrypt
            plain_text = cipher_suite.decrypt(actual_cipher_text)
            
            return(plain_text.decode())
            
        except Exception as e:
            log.traceback(e)
            return(None)

class TraceViewer:
    def __init__(self):
        self.playwright_exe = 'playwright.exe' if os.name == 'nt' else 'playwright'
        self._check_installation()
        
    def _check_installation(self):
        """Check if playwright is installed"""
        if not shutil.which(self.playwright_exe):
            raise RuntimeError(
                "Playwright CLI not found. "
                "Install with: python -m playwright install"
            )
    
    def show_trace(
        self,
        trace_path: str,
        port: Optional[int] = None,
        browser: str = 'default'
    ) -> bool:
        """Show trace with options"""
        try:
            trace_path = Path(trace_path).absolute()
            if not trace_path.exists():
                raise FileNotFoundError(f"Trace not found: {trace_path}")
                
            # Build command
            command = [self.playwright_exe, 'show-trace']
            if port:
                command.extend(['--port', str(port)])
            if browser != 'default':
                command.extend(['--browser', browser])
            command.append(str(trace_path))
            
            # Run viewer
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True if os.name == 'nt' else False
            )
            
            return True
            
        except Exception as e:
            log.error(f"Error showing trace: {str(e)}")
            log.traceback(e)
            return False

class PageScraper:
    def __init__(self, page: Page):
        self.page = page
        
    def scrape_elements(self) -> Dict[str, Any]:
        """
        Scrape various elements from the page
        
        Returns:
            Dictionary containing scraped elements
        """
        return {
            'textareas': self._get_textareas(),
            'inputs': self._get_inputs(),
            'buttons': self._get_buttons(),
            'labels': self._get_labels(),
            'divs': self._get_divs(),
            'selects': self._get_selects(),
            'links': self._get_links(),
            'forms': self._get_forms()
        }
        
    def _get_textareas(self) -> List[Dict[str, str]]:
        """Get all input elements"""
        textareas = []
        for textarea in self.page.locator('textarea').all():
            try:
                textarea_data = {
                    'type': textarea.get_attribute('type') or 'text',
                    'name': textarea.get_attribute('name') or '',
                    'id': textarea.get_attribute('id') or '',
                    'data-testid': textarea.get_attribute('data-testid') or '',
                    'value': textarea.get_attribute('value') or '',
                    'placeholder': textarea.get_attribute('placeholder') or '',
                    'required': textarea.get_attribute('required') == 'true',
                    'disabled': textarea.get_attribute('disabled') == 'true'
                }
                #XPATH for input
                for p in ['data-testid', 'id', 'name', 'type']:
                    xpath = f"//textarea[@{p}='{textarea_data[p]}']"
                    elements = self.page.locator(xpath).all()
                    if len(elements) == 1:
                        textarea_data['xpath'] = xpath
                        break
                
                textareas.append(textarea_data)
            except Exception as e:
                log.error(f"Error getting input data: {str(e)}")
                log.traceback(e)
                
        return textareas
        
    def _get_inputs(self) -> List[Dict[str, str]]:
        """Get all input elements"""
        inputs = []
        for input_el in self.page.locator('input').all():
            try:
                input_data = {
                    'type': input_el.get_attribute('type') or 'text',
                    'name': input_el.get_attribute('name') or '',
                    'id': input_el.get_attribute('id') or '',
                    'data-testid': input_el.get_attribute('data-testid') or '',
                    'value': input_el.get_attribute('value') or '',
                    'placeholder': input_el.get_attribute('placeholder') or '',
                    'required': input_el.get_attribute('required') == 'true',
                    'disabled': input_el.get_attribute('disabled') == 'true'
                }
                #XPATH for input
                for p in ['data-testid', 'id', 'name', 'type']:
                    xpath = f"//input[@{p}='{input_data[p]}']"
                    elements = self.page.locator(xpath).all()
                    if len(elements) == 1:
                        input_data['xpath'] = xpath
                        break
                
                inputs.append(input_data)
            except Exception as e:
                log.error(f"Error getting input data: {str(e)}")
                log.traceback(e)
                
        return inputs
        
    def _get_buttons(self) -> List[Dict[str, str]]:
        """Get all button elements"""
        buttons = []
        for button in self.page.locator('button, input[type="button"], input[type="submit"]').all():
            try:
                button_data = {
                    'text': button.inner_text() or '',
                    'type': button.get_attribute('type') or 'button',
                    'name': button.get_attribute('name') or '',
                    'id': button.get_attribute('id') or '',
                    'disabled': button.get_attribute('disabled') == 'true'
                }
                #XPATH for button
                for p in ['id', 'name', 'text', 'type']:
                    match p:
                        case 'id':
                            xpath = f"//button[@id='{button_data['id']}']"
                        case 'name':
                            xpath = f"//button[@name='{button_data['name']}']"
                        case 'text':
                            xpath = f"//button[contains(text(),'{button_data['text']}')]"
                        case 'type':
                            xpath = f"//button[@type='{button_data['type']}']"
                        case _:
                            continue
                    elements = self.page.locator(xpath).all()
                    if len(elements) == 1:
                        button_data['xpath'] = xpath
                        break
                buttons.append(button_data)
            except Exception as e:
                log.error(f"Error getting button data: {str(e)}")
                log.traceback(e)
                
        return buttons
        
    def _get_labels(self) -> List[Dict[str, str]]:
        """Get all label elements"""
        labels = []
        for label in self.page.locator('label').all():
            try:
                label_data = {
                    'text': label.inner_text() or '',
                    'for': label.get_attribute('for') or '',
                    'id': label.get_attribute('id') or ''
                }
                #XPATH for labels
                for p in ['id', 'text']:
                    match p:
                        case 'text':
                            xpath = f"//label[contains(text(),'{label_data['text']}')]"
                        case 'id':
                            xpath = f"//label[@id='{label_data['id']}']"
                        case _:
                            continue
                    elements = self.page.locator(xpath).all()
                    if len(elements) == 1:
                        label_data['xpath'] = xpath
                        break
                labels.append(label_data)
            except Exception as e:
                log.error(f"Error getting label data: {str(e)}")
                log.traceback(e)
                
        return labels
        
    def _get_divs(self) -> List[Dict[str, str]]:
        """Get important div elements"""
        divs = []
        for div in self.page.locator('div[id], div[class], div[role], div[data-testid]').all():
            try:
                div_data = {
                    'data-testid': div.get_attribute('data-testid') or '',
                    'id': div.get_attribute('id') or '',
                    'class': div.get_attribute('class') or '',
                    'role': div.get_attribute('role') or '',
                    'text': div.inner_text() or ''
                }
                #XPATH for div
                for p in ['data-testid', 'id']:
                    if div_data[p]:
                        match p:
                            case 'data-testid':
                                xpath = f"//div[@data-testid='{div_data['data-testid']}//input']"
                            case 'id':
                                xpath = f"//div[@id='{div_data['id']}//input']"
                            case _:
                                continue
                        elements = self.page.locator(xpath).all()
                        if len(elements) == 1:
                            div_data['xpath'] = xpath
                        if div_data['text']:
                            div_data['text'] = div_data['text'].split()
                            
                        divs.append(div_data)
                        
            except Exception as e:
                log.error(f"Error getting div data: {str(e)}")
                log.traceback(e)
                
        return divs
        
    def _get_selects(self) -> List[Dict[str, Any]]:
        """Get all select elements with options"""
        selects = []
        for select in self.page.locator('select').all():
            try:
                options = []
                for option in select.locator('option').all():
                    options.append({
                        'value': option.get_attribute('value') or '',
                        'text': option.inner_text() or '',
                        'selected': option.get_attribute('selected') == 'true'
                    })
                    
                select_data = {
                    'name': select.get_attribute('name') or '',
                    'id': select.get_attribute('id') or '',
                    'multiple': select.get_attribute('multiple') == 'true',
                    'options': options
                }
                selects.append(select_data)
            except Exception as e:
                log.error(f"Error getting select data: {str(e)}")
                log.traceback(e)
                
        return selects
        
    def _get_links(self) -> List[Dict[str, str]]:
        """Get all link elements"""
        links = []
        for link in self.page.locator('a[href]').all():
            try:
                link_data = {
                    'text': link.inner_text() or '',
                    'href': link.get_attribute('href') or '',
                    'id': link.get_attribute('id') or '',
                    'target': link.get_attribute('target') or '_self'
                }
                links.append(link_data)
            except Exception as e:
                log.error(f"Error getting link data: {str(e)}")
                log.traceback(e)
                
        return links
        
    def _get_forms(self) -> List[Dict[str, Any]]:
        """Get all form elements"""
        forms = []
        for form in self.page.locator('form').all():
            try:
                form_data = {
                    'id': form.get_attribute('id') or '',
                    'name': form.get_attribute('name') or '',
                    'method': form.get_attribute('method') or 'get',
                    'action': form.get_attribute('action') or '',
                    'inputs': [],
                    'buttons': []
                }
                
                # Get form inputs
                for input_el in form.locator('input').all():
                    form_data['inputs'].append({
                        'type': input_el.get_attribute('type') or 'text',
                        'name': input_el.get_attribute('name') or '',
                        'value': input_el.get_attribute('value') or ''
                    })
                    
                # Get form buttons
                for button in form.locator('button, input[type="submit"]').all():
                    form_data['buttons'].append({
                        'text': button.inner_text() or '',
                        'type': button.get_attribute('type') or 'submit'
                    })
                    
                forms.append(form_data)
            except Exception as e:
                log.error(f"Error getting form data:{str(e)}")
                log.traceback(e)
                
        return forms
