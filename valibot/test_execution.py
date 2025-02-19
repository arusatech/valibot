import sys
import os
import json
import requests
import logging
import time
import random
import string
from jsonpath_nz import log, jprint, parse_jsonpath, parse_dict
from playwright.sync_api import sync_playwright
from valibot.util import remove_common_prefix, find_common_prefix, TextCipher, PageScraper, OUTPUT_DIR

# Common resolutions
RESOLUTIONS = {
    'HD': {'width': 1280, 'height': 720},
    'Full_HD': {'width': 1920, 'height': 1080},
    '2K': {'width': 2560, 'height': 1440},
    '4K': {'width': 3840, 'height': 2160},
    'laptop': {'width': 1366, 'height': 768},
    'tablet': {'width': 1024, 'height': 768},
    'mobile': {'width': 390, 'height': 844}
}

def testExecution(testData:dict, config:dict, prompt_dict:dict):
    '''Execute the test data'''
    try:
        # jprint(testData)
        jsonInstruction = parse_dict(testData)
        common_prefix = find_common_prefix(jsonInstruction.keys())
        # jprint(common_prefix)
        last_key = common_prefix.split(".")[-2]
        testItem = dict()
        testItem = remove_common_prefix(jsonInstruction, common_prefix)
        # jprint(testItem)
        time_to_wait = 3
            
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport=RESOLUTIONS['Full_HD'],
                screen=RESOLUTIONS['Full_HD']  # Physical screen size
            )
            page = context.new_page()
            pScraper = PageScraper(page)
            context.tracing.start(screenshots=False, snapshots=True, sources=True)
            step = 0
            for key, value in testItem.items():
                step += 1
                log.info(f"Executing the instruction  - Step: {step}, Key: {key}, Value: {value}")
                if key.startswith( "url"):
                    log.info(f"Navigating to the URL: {value}")
                    page.goto(value)
                if key.startswith("input"):
                    input_list = key.split(".")
                    if str(input_list[1]).startswith("placeholder"):
                        page.fill(f"input[placeholder='{input_list[2]}']", value)
                        log.info(f"Setting the select: {value}")
                    log.info(f"Waiting for {time_to_wait} seconds")
                    time.sleep(time_to_wait)
                if key.startswith("textarea"):
                    input_list = key.split(".")
                    if str(input_list[1]).startswith("placeholder"):
                        page.fill(f"textarea[placeholder='{input_list[2]}']", value)
                        
                    log.info(f"Waiting for {time_to_wait} seconds")
                    time.sleep(time_to_wait)
                if key.startswith("button"):
                    input_list = key.split(".")
                    
                    page.click(f"button[name='{value}']")
                    log.info(f"Waiting for {time_to_wait} seconds")
                    time.sleep(time_to_wait)

            context.tracing.stop(path=os.path.join(OUTPUT_DIR, "trace.zip"))
            browser.close()
        return True
        
    except Exception as e:
        log.error(f"Error executing test data: {str(e)}")
        log.traceback(e)
        raise
    
