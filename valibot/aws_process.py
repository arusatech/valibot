import boto3
import logging
import os
import sys
import mimetypes
import zipfile
from pathlib import Path
from typing import Optional, List, Dict, Union
from botocore.exceptions import ClientError, HTTPClientError
from datetime import datetime
from jsonpath_nz import log, jprint

class S3Handler():
    # Supported file types and their mime types
    SUPPORTED_TYPES = {
        'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
        'documents': ['.pdf', '.doc', '.docx', '.txt', '.csv', '.xlsx', '.xls'],
        'videos': ['.mp4', '.avi', '.mov', '.wmv', '.flv'],
        'archives': ['.zip', '.rar', '.7z', '.tar', '.gz']
    }

    def __init__(self, bucket_name: str = 'valibot-dev2'):
        """Initialize S3 client"""
        self.bucket_name = bucket_name
        try:
            session = boto3.Session(profile_name='dev2')
            self.s3_client = session.client('s3')
            log.info(f"Initialized S3 client for bucket: {bucket_name}")
        except Exception as e:
            log.error(f"Failed to initialize S3 client: {str(e)}")
            raise

    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type of file"""
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or 'application/octet-stream'

    def upload_file(
        self,
        file_path: str,
        folder: str,
        s3_key: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Upload single file to S3
        
        Args:
            file_path: Local file path
            folder: Target S3 folder
            s3_key: Custom S3 key/path
            metadata: Additional metadata
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # Generate S3 key if not provided
            if s3_key is None:
                s3_key = os.path.basename(file_path)

            # s3_path = self._normalize_path(s3_path)
            if not folder:
                s3_path = f"{s3_key}"
                log.info(f"S3 path: {s3_path}")
            else:
                s3_path = f"{folder}/{s3_key}"
                log.info(f"S3 path: {s3_path}")
            
            #normalize the path
            s3_path = s3_path.replace('\\', '/')
            
            # Prepare upload parameters
            upload_args = {
                'Filename': file_path,
                'Bucket': self.bucket_name,
                'Key': s3_path,
                'ExtraArgs': {
                    'ContentType': self._get_mime_type(file_path)
                }
            }

            # Add metadata if provided
            if metadata:
                upload_args['ExtraArgs']['Metadata'] = metadata

            # Upload file
            self.s3_client.upload_file(**upload_args)
            
            log.info(f"Uploaded {file_path} to s3://{self.bucket_name}/{s3_path}")
            return True

        except Exception as e:
            log.error(f"Upload failed: {str(e)}")
            return False

    def upload_folder(
        self,
        local_folder: str,
        s3_folder: str,
        include_base_folder: bool = True
    ) -> Dict[str, List[str]]:
        """
        Upload entire folder to S3
        
        Args:
            local_folder: Local folder path
            s3_folder: Target S3 folder
            include_base_folder: Include base folder name in S3 path
        """
        results = {
            'success': [],
            'failed': []
        }

        try:
            # Validate folder exists
            if not os.path.exists(local_folder):
                raise FileNotFoundError(f"Folder not found: {local_folder}")

            base_folder = os.path.basename(local_folder) if include_base_folder else ''
            
            # Walk through folder
            for root, _, files in os.walk(local_folder):
                for file in files:
                    local_path = os.path.join(root, file)
                    
                    # Calculate relative path for S3
                    rel_path = os.path.relpath(local_path, local_folder)
                    s3_key = os.path.join(s3_folder, base_folder, rel_path)
                    
                    # Upload file
                    # log.info(f"Local path: {local_path}")
                    if self.upload_file(local_path, '', s3_key):
                        results['success'].append(rel_path)
                    else:
                        results['failed'].append(rel_path)

            return results

        except Exception as e:
            log.error(f"Folder upload failed: {str(e)}")
            return results

    def upload_zip(
        self,
        zip_path: str,
        folder: str,
        extract: bool = False
    ) -> Dict[str, List[str]]:
        """
        Upload zip file or its contents
        
        Args:
            zip_path: Path to zip file
            folder: Target S3 folder
            extract: Whether to extract contents
        """
        results = {
            'success': [],
            'failed': []
        }

        try:
            if not zipfile.is_zipfile(zip_path):
                raise ValueError(f"Not a valid zip file: {zip_path}")

            if extract:
                # Upload zip contents
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    for file_info in zip_ref.filelist:
                        if file_info.filename.endswith('/'):  # Skip directories
                            continue
                            
                        # Extract file to temporary location
                        temp_path = zip_ref.extract(file_info.filename, '/tmp')
                        
                        try:
                            # Upload extracted file
                            s3_key = f"{folder}/{file_info.filename}"
                            if self.upload_file(temp_path, '', s3_key):
                                results['success'].append(file_info.filename)
                            else:
                                results['failed'].append(file_info.filename)
                        finally:
                            # Cleanup
                            os.remove(temp_path)
            else:
                # Upload zip file as is
                if self.upload_file(zip_path, folder):
                    results['success'].append(os.path.basename(zip_path))
                else:
                    results['failed'].append(os.path.basename(zip_path))

            return results

        except Exception as e:
            log.error(f"Zip upload failed: {str(e)}")
            return results

    def upload_batch(
        self,
        files: List[str],
        folder: str,
        prefix: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Upload multiple files in batch
        
        Args:
            files: List of file paths
            folder: Target S3 folder
            prefix: Optional prefix for S3 keys
        """
        results = {
            'success': [],
            'failed': []
        }

        for file_path in files:
            try:
                s3_key = f"{prefix}/{os.path.basename(file_path)}" if prefix else None
                
                if self.upload_file(file_path, folder, s3_key):
                    results['success'].append(file_path)
                else:
                    results['failed'].append(file_path)
                    
            except Exception as e:
                log.error(f"Failed to upload {file_path}: {str(e)}")
                results['failed'].append(file_path)

        return results

    def get_latest_s3_file(self, prefix):
        """
        Return the latest s3 file name in bucket folder.
        :param bucket: Name of the S3 bucket.
        :param prefix: fetch keys that start with this prefix.
        """
        log.info(f"Get Latest from Prefix {prefix}")
        try:
            list_obj = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if not 'Contents' in list_obj.keys():
                return None
            objs_v2 = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=prefix)['Contents']
            files = dict()
            for obj in objs_v2:
                key = obj['Key']
                timestamp = obj['LastModified']
                # if key starts with folder name retrieve that key
                if key.startswith(prefix):
                    # Adding a new key value pair
                    files.update({key: timestamp})
            latest_filename = max(files, key=files.get)
            return latest_filename
        except Exception as e:
            log.critical(f'!! Failed to capture log {e}, {type(e).__name__}')
            log.critical(f'Error on line {(sys.exc_info()[-1].tb_lineno)}')
            log.traceback(e)
            return None

    def get_latest_s3_folders(self,
        s3_key: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> list:
        """
        Get latest folder from S3 path based on date in folder name
        
        Args:
            s3_path: S3 path (e.g., 's3://bucket/folder/')
            
        Returns:
            Full path to latest folder
        """
        try:
            # List objects with prefix
            log.info(f"Get Latest folders from Prefix {s3_key}")
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=s3_key,
                Delimiter='/'
            )
            
            # Get folders (CommonPrefixes)
            folders = []
            if 'CommonPrefixes' in response:
                for obj in response['CommonPrefixes']:
                    folder_name = obj['Prefix'].rstrip('/').split('/')[-1]
                    # Check if folder matches valibot_YYYYMMDD_HHMMSS format
                    if folder_name.startswith('valibot_'):
                        try:
                            # Extract date part and convert to datetime
                            date_str = folder_name.split('valibot_')[1]
                            folder_date = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                            folders.append((obj['Prefix'], folder_date))
                        except (ValueError, IndexError):
                            continue
            
            # Get latest folder
            if folders:
                latest_folder = sorted(folders, key=lambda x: x[1], reverse=True)
                jprint(latest_folder)
                return latest_folder
                
            return False
            
        except Exception as e:
            log.error(f"Error getting latest S3 folder: {str(e)}")
            log.traceback(e)
            return False 

    def download_file_from_key(
        self, 
        s3_key: str, 
        file_type: Optional[str] = 'zip',
        local_dir: Optional[str] = None
    ) -> Optional[str]:
        """
        Download file (zip/log) from S3 key
        
        Args:
            s3_key: S3 key/prefix path
            file_type: Type of file to download ('zip' or 'log')
            local_dir: Local directory to save file (default: current directory)
            
        Returns:
            Path to downloaded file or None if not found
        """
        try:
            # Normalize key and set file pattern
            s3_key = s3_key.rstrip('/') + '/'
            file_pattern = 'trace.zip' if file_type == 'zip' else '.log'
            
            # List objects in the key
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=s3_key
            )
            
            # Find matching file
            target_file = None
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith(file_pattern):
                        target_file = obj['Key']
                        break
            
            if not target_file:
                log.error(f"No {file_type} file found in {s3_key}")
                return None
                
            # Create local directory if specified
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)
                
            # Generate local file path
            file_name = os.path.basename(target_file)
            local_path = os.path.join(local_dir or '.', file_name)
            
            # Download file
            log.info(f"Downloading {target_file} to {local_path}")
            self.s3_client.download_file(
                self.bucket_name,
                target_file,
                local_path
            )
            log.info(f"Downloaded {target_file} to {local_path}")
            return local_path
            
        except Exception as e:
            log.error(f"Error downloading file: {str(e)}")
            log.traceback(e)
            return None

def main():
    logging.basicConfig(level=logging.INFO)
    
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
        log.info(f"Uploaded {len(results['success'])} files")

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
        log.error(f"Error: {str(e)}")
        log.traceback(e)
