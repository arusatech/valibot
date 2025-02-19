# Incoming server (IMAP) imap.hostinger.com 993
# Outgoing server (SMTP) smtp.hostinger.com 465
# Incoming server (POP) pop.hostinger.com 995

import email
import imaplib
import os
import re
import smtplib
from jsonpath_nz import log, jprint
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import html2text

class EmailProcessor:
    def __init__(self, imap_server, email_address, password):
        self.imap_server = imap_server
        self.email_address = email_address
        self.password = password
        self.imap_connection = None

    def connect(self):
        """Establish connection to IMAP server"""
        try:
            self.imap_connection = imaplib.IMAP4_SSL(self.imap_server)
            self.imap_connection.login(self.email_address, self.password)
            return True
        except Exception as e:
            log.error(f"Connection error: {str(e)}")
            log.traceback(e)
            return False

    def disconnect(self):
        """Close IMAP connection"""
        try:
            if self.imap_connection:
                self.imap_connection.logout()
        except Exception as e:
            log.error(f"Error disconnecting from IMAP server: {str(e)}")
            log.traceback(e)

    def configure_html_parser(self):
        """Configure HTML parser with ignore settings"""
        h = html2text.HTML2Text()
        # Ignore various HTML elements
        h.ignore_links = True
        h.ignore_images = True
        h.ignore_tables = True
        h.ignore_emphasis = True
        h.body_width = 0
        h.unicode_snob = True  # Prevents conversion of unicode to ascii
        h.skip_internal_links = True
        h.inline_links = True
        h.protect_links = True
        h.single_line_break = True  # Reduces multiple line breaks
        h.ul_item_mark = ''  # Remove list markers
        h.emphasis_mark = ''  # Remove emphasis markers
        h.strong_mark = ''    # Remove strong markers
        return h
    
    
    def list_emails(self, parseList=None, from_domain=None, days=1, mailbox="INBOX"):
        """
        List emails with their subjects, from, dates and content
        Args:
            from_domain (str): Filter emails from specific domain
            days (int): Number of days to look back
            mailbox (str): Mailbox to search in (default: "INBOX")
        """
        if not self.imap_connection:
            log.error("No IMAP connection established")
            return None

        try:
            self.imap_connection.select(mailbox)
            
            # Build search criteria based on days
            if days and str(days).lower() != 'all':
                search_criteria = f'(SINCE "{(datetime.now() - timedelta(days=int(days))).strftime("%d-%b-%Y")}")'
                _, message_numbers = self.imap_connection.search(None, search_criteria)
            else:
                _, message_numbers = self.imap_connection.search(None, "ALL")
            
            email_list = []
            for num in message_numbers[0].split():
                _, msg_data = self.imap_connection.fetch(num, "(RFC822)")  # Changed from RFC822.HEADER to RFC822
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Check domain filter if specified
                if from_domain and str(from_domain).lower() not in str(email_message['from']).lower():
                    continue
                
                # Extract content
                content = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            content += part.get_payload(decode=True).decode()
                        elif part.get_content_type() == "text/html":
                            html_content = part.get_payload(decode=True).decode()
                            h = self.configure_html_parser()
                            content += h.handle(html_content)
                else:
                    payload = email_message.get_payload(decode=True).decode()
                    if email_message.get_content_type() == "text/html":
                        h = self.configure_html_parser()
                        content = h.handle(payload)
                    else:
                        content = payload

                content = content.strip().replace("\ufeff", "").replace("\u034f", "")
                # After getting the content, process it according to parseList
                extracted_data = {}
                if parseList:
                    for field in parseList:
                        field = field.lower()
                        for p in content.split('\n'):
                            p = p.strip().lower()
                            if field in p:
                                #position of the field in the p
                                pos = p.find(field)
                                #extract the content after the field
                                extracted_data[field] = p[pos+len(field)+1:].strip()
                                break
                            else:
                                extracted_data[field] = ""
                email_info = {
                    'subject': email_message['subject'],
                    'from': email_message['from'],
                    'date': email_message['date'],
                    'content': content,
                    'extracted_fields': extracted_data
                }
                email_list.append(email_info)

            # Sort emails by date (newest first)
            email_list.sort(key=lambda x: email.utils.parsedate_to_datetime(x['date']), reverse=True)
            
            log.info(f"Found {len(email_list)} emails in {mailbox} from {from_domain} in the last {days} days")
            return email_list
            
        except Exception as e:
            log.error(f"Error listing emails: {str(e)}")
            log.traceback(e)
            return None

    
# if __name__ == "__main__":
#     user_email = "info@arusallc.com" 
#     email_processor = EmailProcessor(
#         imap_server="imap.hostinger.com",
#         email_address=user_email,
#         password="12Arusallc?"
#     )
#     #get the domain from the email
#     domain = user_email.split("@")[1]
#     if email_processor.connect():
#         emails = email_processor.list_emails(from_domain=domain, parseList=["paragraph", "email", "full name"])
#         jprint(emails)

#         if emails:
#             for email_info in emails:
#                 log.info(f"Subject: {email_info['subject']}")
#     email_processor.disconnect()


