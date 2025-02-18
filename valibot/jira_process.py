from dataclasses import dataclass
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
import platform
import getpass
import re
import json
import os
from jira import JIRA
from jsonpath_nz import log, jprint, parse_jsonpath, parse_dict
from valibot.util import TextCipher
from valibot.google_process import gTestCase

@dataclass
class JiraConfig:
    """JIRA configuration settings"""
    jira_server: str
    jira_user: str
    jira_api_key: str
    jira_project: str
    jira_type: str = "Task"
    jira_number: str = None

class JiraHandler():
    def __init__(self, config: JiraConfig):
        """Initialize JIRA client"""
        self.config = config
        
        try:
            self.client = JIRA(
                server=config['jira_server'],
                basic_auth=(config['jira_user'], config['jira_api_key'])
            )
            log.info("JIRA client initialized successfully")
        except Exception as e:
            log.error(f"Failed to initialize JIRA client: {str(e)}")
            raise

    def create_issue_with_attachment(
        self, 
        data: Dict[str, Any], 
        attachments: List[str] = None
    ) -> Optional[str]:
        """
        Create JIRA issue with attachments
        
        Args:
            data (Dict[str, Any]): Issue data
            attachments (List[str]): List of file paths to attach
            
        Returns:
            Optional[str]: Issue key if created successfully
        """
        try:
            # Format issue fields
            issue_dict = {
                'project': {'key': self.config.project_key},
                'summary': self.format_summary(data),
                'description': json.dumps(data, indent=2),
                'issuetype': {'name': self.config.issue_type},
            }
            
            # Add optional fields
            if 'priority' in data:
                issue_dict['priority'] = {'name': data['priority']}
            
            # Create issue
            issue = self.client.create_issue(fields=issue_dict)
            log.info(f"Created JIRA issue: {issue.key}")
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        self.client.add_attachment(
                            issue=issue.key,
                            attachment=file_path
                        )
                        log.info(f"Added attachment: {file_path}")
                    else:
                        log.warning(f"Attachment not found: {file_path}")
            
            return issue.key
            
        except Exception as e:
            log.error(f"Failed to create JIRA issue: {str(e)}")
            return None

    def update_issue_with_attachment(
        self, 
        issue_key: str, 
        data: Dict[str, Any], 
        attachments: List[str] = None,
        remove_existing: bool = False
    ) -> bool:
        """
        Update JIRA issue with attachments
        
        Args:
            issue_key (str): JIRA issue key
            data (Dict[str, Any]): Updated data
            attachments (List[str]): List of file paths to attach
            remove_existing (bool): Whether to remove existing attachments
            
        Returns:
            bool: Success status
        """
        try:
            # Get issue
            issue = self.client.issue(issue_key)
            
            # Update fields
            update_dict = {
                'summary': self.format_summary(data),
                'description': json.dumps(data, indent=2)
            }
            
            if 'priority' in data:
                update_dict['priority'] = {'name': data['priority']}
            
            # Update issue
            issue.update(fields=update_dict)
            
            # Handle attachments
            if remove_existing:
                # Remove existing attachments
                for attachment in issue.fields.attachment:
                    attachment.delete()
                    log.info(f"Removed attachment: {attachment.filename}")
            
            # Add new attachments
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        self.client.add_attachment(
                            issue=issue_key,
                            attachment=file_path
                        )
                        log.info(f"Added attachment: {file_path}")
                    else:
                        log.warning(f"Attachment not found: {file_path}")
            
            return True
            
        except Exception as e:
            log.error(f"Failed to update JIRA issue {issue_key}: {str(e)}")
            return False

    def list_issues(
        self, 
        days_back: int = 30, 
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List JIRA issues with formatted summary
        
        Args:
            days_back (int): Number of days to look back
            status (str, optional): Filter by status
            
        Returns:
            List[Dict[str, Any]]: List of issues
        """
        try:
            # Calculate date range
            date_from = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            # Build JQL query
            jql = f'project = {self.config.project_key} AND created >= "{date_from}"'
            if status:
                jql += f' AND status = "{status}"'
            
            # Search issues
            issues = self.client.search_issues(jql)
            
            # Format results
            results = []
            for issue in issues:
                attachments = [
                    {
                        'filename': att.filename,
                        'size': att.size,
                        'created': att.created
                    }
                    for att in issue.fields.attachment
                ]
                
                results.append({
                    'key': issue.key,
                    'summary': issue.fields.summary,
                    'status': issue.fields.status.name,
                    'created': issue.fields.created,
                    'updated': issue.fields.updated,
                    'attachments': attachments
                })
            
            return results
            
        except Exception as e:
            log.error(f"Failed to list issues: {str(e)}")
            return []

    def list_issues_by_summary(
        self,
        days_back: int = 30,
        status: Optional[str] = None,
        environment: Optional[str] = None,
        loan_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List JIRA issues with parsed summaries and filters
        
        Args:
            days_back (int): Number of days to look back
            status (str, optional): Filter by JIRA status
            environment (str, optional): Filter by environment
            loan_status (str, optional): Filter by loan status
            
        Returns:
            List[Dict[str, Any]]: List of formatted issues
        """
        try:
            # Calculate date range
            date_from = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            # Build JQL query
            jql = f'project = {self.config.project_key} AND created >= "{date_from}"'
            if status:
                jql += f' AND status = "{status}"'
            
            # Search issues
            issues = self.client.search_issues(
                jql,
                maxResults=1000,  # Adjust as needed
                fields='summary,status,created,updated,attachment,description'
            )
            
            # Format and filter results
            results = []
            for issue in issues:
                # Parse summary components
                summary_components = self.parse_summary(issue.fields.summary)
                
                # Apply additional filters
                if environment and summary_components.get('environment') != environment:
                    continue
                if loan_status and summary_components.get('loan_status') != loan_status:
                    continue
                
                # Get attachments info
                attachments = [
                    {
                        'filename': att.filename,
                        'size': att.size,
                        'created': att.created
                    }
                    for att in issue.fields.attachment
                ]
                
                # Try to parse description as JSON
                try:
                    description_data = json.loads(issue.fields.description)
                except:
                    description_data = {}
                
                # Combine all information
                issue_data = {
                    'key': issue.key,
                    'summary': issue.fields.summary,
                    'components': summary_components,
                    'status': issue.fields.status.name,
                    'created': issue.fields.created,
                    'updated': issue.fields.updated,
                    'attachments': attachments,
                    'additional_data': description_data
                }
                
                results.append(issue_data)
            
            return results
            
        except Exception as e:
            log.error(f"Failed to list issues: {str(e)}")
            return []

    def get_issue_details(self, issue_key: str) -> Dict[str, Any]:
        """
        Get comprehensive issue details including attachments and links
        If issue is an epic, includes all child issues in the epic
        """
        try:
            issue = self.client.issue(
                issue_key,
                expand='renderedFields,changelog,transitions,links'
            )
            
            # Get child issues if this is an epic
            child_issues = []
            if issue.fields.issuetype.name.lower() == 'epic':
                # JQL to find all issues in this epic
                jql = f'parent = {issue_key} OR "Epic Link" = {issue_key}'
                children = self.client.search_issues(jql, maxResults=1000)
                child_issues = [{
                    'key': child.key,
                    'summary': child.fields.summary,
                    'status': child.fields.status.name,
                    'type': child.fields.issuetype.name,
                    'priority': child.fields.priority.name if hasattr(child.fields, 'priority') else None
                } for child in children]
            
            # Regular subtasks
            subtasks = [
                {
                    'key': subtask.key,
                    'summary': subtask.fields.summary,
                    'status': subtask.fields.status.name,
                    'type': subtask.fields.issuetype.name
                }
                for subtask in getattr(issue.fields, 'subtasks', [])
            ]
            
            # Get attachments
            attachments = [
                {
                    'id': att.id,
                    'filename': att.filename,
                    'size': att.size,
                    'created': att.created,
                    'content_type': att.content_type,
                    'author': att.author.displayName,
                    'url': att.content
                }
                for att in issue.fields.attachment
            ]
            
            # Get linked issues
            linked_issues = []
            for link in issue.fields.issuelinks:
                linked_issue = None
                if hasattr(link, "outwardIssue"):
                    linked_issue = link.outwardIssue
                    link_type = "outward"
                elif hasattr(link, "inwardIssue"):
                    linked_issue = link.inwardIssue
                    link_type = "inward"
                
                if linked_issue:
                    linked_issues.append({
                        'key': linked_issue.key,
                        'link_type': link_type,
                        'relationship': link.type.name,
                        'status': linked_issue.fields.status.name,
                        'summary': linked_issue.fields.summary
                    })
            
            # Compile complete issue details
            issue_details = {
                'key': issue.key,
                'type': issue.fields.issuetype.name,
                'summary': issue.fields.summary,
                'status': issue.fields.status.name,
                'description': issue.fields.description,
                'created': issue.fields.created,
                'updated': issue.fields.updated,
                'creator': issue.fields.creator.displayName,
                'assignee': issue.fields.assignee.displayName if issue.fields.assignee else None,
                'priority': issue.fields.priority.name if hasattr(issue.fields, 'priority') else None,
                'components': [c.name for c in issue.fields.components],
                'labels': issue.fields.labels,
                'attachments': attachments,
                'web_link': issue.permalink(),
                'linked_issues': linked_issues,
                'subtasks': subtasks,
                'epic_children': child_issues if issue.fields.issuetype.name.lower() == 'epic' else [],
                'changelog': [
                    {
                        'author': history.author.displayName,
                        'created': history.created,
                        'items': [
                            {
                                'field': item.field,
                                'from': item.fromString,
                                'to': item.toString
                            }
                            for item in history.items
                        ]
                    }
                    for history in issue.changelog.histories
                ]
            }
            
            return issue_details
            
        except Exception as e:
            log.error(f"Failed to get issue details for {issue_key}: {str(e)}")
            return {}

    def download_attachment(self, issue_key: str, attachment_id: str, save_path: str) -> bool:
        """
        Download specific attachment from an issue
        
        Args:
            issue_key (str): JIRA issue key
            attachment_id (str): Attachment ID
            save_path (str): Path to save the attachment
            
        Returns:
            bool: Success status
        """
        try:
            attachment = self.client.attachment(attachment_id)
            with open(save_path, 'wb') as f:
                f.write(attachment.get())
            return True
        except Exception as e:
            log.error(f"Failed to download attachment {attachment_id}: {str(e)}")
            return False

    def create_issue_link(
        self,
        from_issue: str,
        to_issue: str,
        link_type: str = "Relates"
    ) -> bool:
        """
        Create a link between two issues
        
        Args:
            from_issue (str): Source issue key
            to_issue (str): Target issue key
            link_type (str): Type of link (e.g., "Relates", "Blocks", "Cloners")
            
        Returns:
            bool: Success status
        """
        try:
            self.client.create_issue_link(link_type, from_issue, to_issue)
            return True
        except Exception as e:
            log.error(f"Failed to create issue link: {str(e)}")
            return False

    def create_issue(
        self,
        summary: str,
        description: str,
        issue_type: str = None,
        priority: str = None,
        assignee: str = None,
        labels: List[str] = None,
        components: List[str] = None,
        attachments: List[str] = None,
        linked_issues: List[Dict[str, str]] = None,
        custom_fields: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Create a JIRA issue with comprehensive field support
        
        Args:
            summary (str): Issue summary
            description (str): Issue description
            issue_type (str, optional): Issue type (defaults to config issue_type)
            priority (str, optional): Issue priority
            assignee (str, optional): Username of assignee
            labels (List[str], optional): List of labels
            components (List[str], optional): List of component names
            attachments (List[str], optional): List of file paths to attach
            linked_issues (List[Dict[str, str]], optional): List of issues to link
                Format: [{'key': 'PROJ-123', 'type': 'Relates'}]
            custom_fields (Dict[str, Any], optional): Custom field values
                Format: {'customfield_10001': 'value'}
        
        Returns:
            Optional[str]: Issue key if created successfully
        """
        try:
            # Build basic issue fields
            issue_dict = {
                'project': {'key': self.config.project_key},
                'summary': summary,
                'description': description,
                'issuetype': {'name': issue_type or self.config.issue_type},
            }

            # Add optional fields
            if priority:
                issue_dict['priority'] = {'name': priority}
            
            if assignee:
                issue_dict['assignee'] = {'name': assignee}
            
            if labels:
                issue_dict['labels'] = labels
            
            if components:
                issue_dict['components'] = [{'name': c} for c in components]
            
            # Add any custom fields
            if custom_fields:
                issue_dict.update(custom_fields)

            # Create the issue
            issue = self.client.create_issue(fields=issue_dict)
            log.info(f"Created JIRA issue: {issue.key}")

            # Add attachments if provided
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        self.client.add_attachment(
                            issue=issue.key,
                            attachment=file_path
                        )
                        log.info(f"Added attachment: {file_path}")
                    else:
                        log.warning(f"Attachment not found: {file_path}")

            # Create issue links if provided
            if linked_issues:
                for link in linked_issues:
                    try:
                        self.client.create_issue_link(
                            link.get('type', 'Relates'),
                            issue.key,
                            link['key']
                        )
                        log.info(f"Created link between {issue.key} and {link['key']}")
                    except Exception as e:
                        log.error(f"Failed to create link to {link['key']}: {str(e)}")

            return issue.key

        except Exception as e:
            log.error(f"Failed to create JIRA issue: {str(e)}")
            return None

    def get_web_links(self, issue_key: str) -> List[Dict[str, str]]:
        """
        Get all web links from a JIRA issue description and comments
        
        Args:
            issue_key (str): JIRA issue key
            
        Returns:
            List[Dict[str, str]]: List of dictionaries containing link details
        """
        try:
            # Get issue with comments
            issue = self.client.issue(
                issue_key,
                expand='renderedFields,comment'
            )
            
            # Regular expression to find URLs
            url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            
            links = []
            
            # Extract links from description
            if issue.fields.description:
                description_links = re.findall(url_pattern, issue.fields.description)
                for link in description_links:
                    links.append({
                        'url': link,
                        'source': 'description',
                        'created': issue.fields.created
                    })
            
            # Extract links from comments
            for comment in issue.fields.comment.comments:
                comment_links = re.findall(url_pattern, comment.body)
                for link in comment_links:
                    links.append({
                        'url': link,
                        'source': 'comment',
                        'author': comment.author.displayName,
                        'created': comment.created
                    })
            
            return links
            
        except Exception as e:
            log.error(f"Failed to get web links from {issue_key}: {str(e)}")
            return []

    def get_issue_links_and_urls(self, issue_key: str) -> Dict[str, List]:
        """
        Get all linked issues and web links from a JIRA issue
        
        Args:
            issue_key (str): JIRA issue key
            
        Returns:
            Dict[str, List]: Dictionary containing linked issues and web links
        """
        try:
            # Get issue with comments and links
            issue = self.client.issue(
                issue_key,
                expand='renderedFields,comment,issuelinks'
            )
            
            # Get linked issues
            linked_issues = []
            for link in issue.fields.issuelinks:
                linked_issue = None
                if hasattr(link, "outwardIssue"):
                    linked_issue = link.outwardIssue
                    link_type = "outward"
                elif hasattr(link, "inwardIssue"):
                    linked_issue = link.inwardIssue
                    link_type = "inward"
                
                if linked_issue:
                    linked_issues.append({
                        'key': linked_issue.key,
                        'link_type': link_type,
                        'relationship': link.type.name,
                        'status': linked_issue.fields.status.name,
                        'summary': linked_issue.fields.summary
                    })
            
            # Get web links
            url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            web_links = []
            
            # From description
            if issue.fields.description:
                description_links = re.findall(url_pattern, issue.fields.description)
                for link in description_links:
                    web_links.append({
                        'url': link,
                        'source': 'description',
                        'created': issue.fields.created
                    })
            
            # From comments
            for comment in issue.fields.comment.comments:
                comment_links = re.findall(url_pattern, comment.body)
                for link in comment_links:
                    web_links.append({
                        'url': link,
                        'source': 'comment',
                        'author': comment.author.displayName,
                        'created': comment.created
                    })
            
            return {
                'linked_issues': linked_issues,
                'web_links': web_links
            }
            
        except Exception as e:
            log.error(f"Failed to get links from {issue_key}: {str(e)}")
            return {'linked_issues': [], 'web_links': []}

    def get_all_links(self, issue_key: str) -> Dict[str, List]:
        """
        Get all types of links (issue links and remote links) for a JIRA issue
        
        Args:
            issue_key (str): JIRA issue key
            
        Returns:
            Dict[str, List]: Dictionary containing both issue links and remote links
        """
        try:
            # Get issue with all needed fields
            issue = self.client.issue(
                issue_key,
                expand='remotelinks'
            )
            
            # Get linked issues
            linked_issues = []
            for link in issue.fields.issuelinks:
                linked_issue = None
                if hasattr(link, "outwardIssue"):
                    linked_issue = link.outwardIssue
                    link_type = "outward"
                    relationship = link.type.outward
                elif hasattr(link, "inwardIssue"):
                    linked_issue = link.inwardIssue
                    link_type = "inward"
                    relationship = link.type.inward
                
                if linked_issue:
                    linked_issues.append({
                        'key': linked_issue.key,
                        'link_type': link_type,
                        'relationship': relationship,
                        'status': linked_issue.fields.status.name,
                        'summary': linked_issue.fields.summary
                    })
            
            # Get remote links
            remote_links = []
            for link in issue.raw.get('remotelinks', []):
                remote_links.append({
                    'url': link['object']['url'],
                    'title': link['object'].get('title', ''),
                    'summary': link['object'].get('summary', ''),
                    'created': link.get('created', ''),
                    'updated': link.get('updated', '')
                })
            
            return {
                'issue_links': linked_issues,
                'remote_links': remote_links
            }
            
        except Exception as e:
            log.error(f"Failed to get links for {issue_key}: {str(e)}")
            return {'issue_links': [], 'remote_links': []}

def get_sheet_name(url: str) -> str:
    """Extract sheet name from Google Sheets URL"""
    try:
        # Check if it's a Google Sheets URL
        if 'docs.google.com/spreadsheets' not in url:
            return None
            
        # Try to get the sheet name from the URL
        if '/d/' in url:
            # Split URL to get the part after /d/
            parts = url.split('/d/')[1].split('/')
            sheet_id = parts[0]
            
            # If there's a specific sheet name in the URL
            sheet_name = None
            if len(parts) > 1 and 'edit' in parts[1]:
                sheet_params = parts[1].split('=')
                if len(sheet_params) > 1:
                    sheet_name = sheet_params[1]
            
            return {
                'sheet_id': sheet_id,
                'sheet_name': sheet_name
            }
    except Exception as e:
        log.error(f"Failed to parse sheet name: {str(e)}")
    return None

def process_jira_steps(config, prompt_dict):
    try:
        required_keys = ['jira_server', 'jira_api_key', 'jira_user']    
        for key in required_keys:
            if key not in config or not config[key]:
                raise ValueError(f"Missing required configuration: {key}")
            else:
                if key == 'jira_api_key':
                    config[key] = TextCipher().decrypt(config[key], f"{getpass.getuser()}@{platform.system()}")
                    continue
                log.info(f"Using jira {key}: {config[key]}")
                
        jira_handler = JiraHandler(config)
        jira_number = prompt_dict.get('jira_number', None)
        
        if not jira_number:
            raise ValueError("Jira Issue key or Jira number is required")
            
        # Get all links
        links_data = jira_handler.get_issue_links_and_urls(jira_number)
        
        # Print results
        if links_data['web_links']:
            log.info("Web Links:")
            for link in links_data['web_links']:
                if 'docs.google.com/spreadsheets' in link['url']:
                    sheet_info = get_sheet_name(link['url'])
                    jprint(sheet_info)
                    if sheet_info:
                        sheet_desc = f"ID: {sheet_info['sheet_id']}"
                        sheet_name = "TestData"
                        testData = gTestCase(jira_number,sheet_info['sheet_id'], sheet_name)
                        if isinstance(testData,dict):
                            testData_values = [str(value).lower() for value in testData.values()]
                            if str(jira_number).lower() in testData_values:
                                for key in testData.keys():
                                    if "test step" in str(key).lower():
                                        heading = json.loads(testData[key])
                                        return(parse_jsonpath(heading))
                            else:
                                log.info(f"[Google Spreadsheet] {link['url']} (from {link['source']}) -- Doesn't have any info")
                                return None

                    else:
                        log.info(f"[Google Spreadsheet] {link['url']} (from {link['source']}) -- Doesn't have any info")
                        return None
                else:
                    log.info(f"NOT a GOOGLE SHEET- {link['url']} (from {link['source']})")
        
        log.info("No Google Sheet found ... ")
        return None
        
    except Exception as e:
        log.error(f"Failed to process JIRA steps: {str(e)}")
        log.traceback(e)
        return None

def process_jira_links(config, prompt_dict):
    """
    Process all JIRA links (issue links and remote links)
    """
    try:
        required_keys = ['jira_server', 'jira_api_key', 'jira_user']    
        for key in required_keys:
            if key not in config or not config[key]:
                raise ValueError(f"Missing required configuration: {key}")
            else:
                if key == 'jira_api_key':
                    config[key] = TextCipher().decrypt(config[key], f"{getpass.getuser()}@{platform.system()}")
                    continue
                log.info(f"Using jira {key}: {config[key]}")
                
        jira_handler = JiraHandler(config)
        jira_number = prompt_dict.get('jira_number', None)
        
        if not jira_number:
            raise ValueError("JIRA issue key is required")
            
        # Get all links
        links_data = jira_handler.get_all_links(jira_number)
        jprint(links_data)
        
        # Print results
        if links_data['issue_links']:
            log.info("\nLinked Issues:")
            for issue in links_data['issue_links']:
                log.info(f"- {issue['key']}: {issue['summary']}")
                log.info(f"  Relationship: {issue['relationship']}")
                log.info(f"  Status: {issue['status']}")
        
        if links_data['remote_links']:
            log.info("\nRemote Links:")
            for link in links_data['remote_links']:
                log.info(f"- {link['url']}")
                if link['title']:
                    log.info(f"  Title: {link['title']}")
                if link['summary']:
                    log.info(f"  Summary: {link['summary']}")
        
        if not links_data['issue_links'] and not links_data['remote_links']:
            log.info(f"No links found for {jira_number}")
        
        return links_data
        
    except Exception as e:
        log.error(f"Failed to process JIRA links: {str(e)}")
        return None
