import json
import os
import time
from datetime import datetime
from typing import Dict, Optional
from config import Config
import threading
import requests
from dotenv import load_dotenv
import base64

load_dotenv()

class InventoryData:
    def __init__(self, filepath: str = Config.DATA_FILE):
        self.filepath = filepath
        self.lock = threading.Lock()
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        # Check if file exists and is valid
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    content = f.read().strip()
                    if content:  # File has content
                        json.loads(content)  # Validate it's valid JSON
                        return  # File is good, exit
            except (json.JSONDecodeError, IOError):
                pass  # File is corrupted, will recreate below
        
        # Create or recreate the file
        initial_data = {
            "skus": {},
            "config": {
                "last_sync_run": None,
                "sync_interval_minutes": Config.SYNC_INTERVAL_MINUTES,
                "auto_sync_enabled": False,
                "inventory_method": "manual",  # Add this line
                "sales_interval_minutes": 180,
                "last_check_run": None
            },
            "audit_log_stats": {
                "total_logs": 0,
                "last_log": None
            },
            "audit_log": []
        }
        with open(self.filepath, 'w') as f:
            json.dump(initial_data, f, indent=2)
    
    def _read_data(self) -> dict:
        with self.lock:
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with open(self.filepath, 'r') as f:
                        data = json.load(f)
                    return data
                except (IOError, json.JSONDecodeError) as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.1)
                    else:
                        raise
    
    def _write_data(self, data: dict):
        with self.lock:
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    # Write to temp file first, then rename (atomic operation)
                    temp_file = self.filepath + '.tmp'
                    with open(temp_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    
                    # Atomic rename
                    if os.path.exists(self.filepath):
                        os.replace(temp_file, self.filepath)
                    else:
                        os.rename(temp_file, self.filepath)
                    break
                except IOError as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.1)
                    else:
                        raise
    
    def get_all_skus(self) -> Dict:
        data = self._read_data()
        return data.get('skus', {})
    
    def get_sku(self, sku: str) -> Optional[Dict]:
        skus = self.get_all_skus()
        return skus.get(sku)
    
    def add_sku(self, sku: str, product_name: str, available_qty: int, 
                modified_by: str = 'system', notes: str = '', sn_flag:bool = False, part_num:str=None) -> Dict:
        data = self._read_data()
        
        sku_data = {
            'product_name': product_name,
            'available_qty': available_qty,
            'initial_qty': available_qty,
            'last_modified': datetime.now().isoformat(),
            'modified_by': modified_by,
            'notes': notes,
            'sn_flag':sn_flag,
            'part_num':part_num,
            'orders_processed': 0
        }
        
        data['skus'][sku] = sku_data
        
        # Add audit log entry
        data['audit_log'].insert(0,{
            'id': data['audit_log_stats']['total_logs'] + 1,
            'timestamp': datetime.now().isoformat(),
            'action': 'add',
            'sku': sku,
            'user': modified_by,
            'data': sku_data
        })

        # Update stats
        data['audit_log_stats']['total_logs'] += 1
        data['audit_log_stats']['last_log'] = datetime.now().isoformat()
        
        self._write_data(data)
        return sku_data
    
    def update_sku(self, sku: str, updates: Dict, modified_by: str = 'system') -> Optional[Dict]:
        data = self._read_data()
        
        if sku not in data['skus']:
            return None
        
        # Update fields
        for key, value in updates.items():
            if key in ['product_name', 'available_qty', 'notes']:
                data['skus'][sku][key] = value
        
        data['skus'][sku]['initial_qty'] = updates['available_qty']
        data['skus'][sku]['orders_processed'] = 0
        data['skus'][sku]['last_modified'] = datetime.now().isoformat()
        data['skus'][sku]['modified_by'] = modified_by
        
        # Add audit log entry
        data['audit_log'].insert(0,{
            'id': data['audit_log_stats']['total_logs'] + 1,
            'timestamp': datetime.now().isoformat(),
            'action': 'update',
            'sku': sku,
            'user': modified_by,
            'updates': updates
        })

        # Update stats
        data['audit_log_stats']['total_logs'] += 1
        data['audit_log_stats']['last_log'] = datetime.now().isoformat()
        
        self._write_data(data)
        return data['skus'][sku]
    
    def delete_sku(self, sku: str, modified_by: str = 'system') -> bool:
        data = self._read_data()
        
        if sku not in data['skus']:
            return False
        
        deleted_data = data['skus'].pop(sku)
        
        # Add audit log entry
        data['audit_log'].insert(0, {
            'id': data['audit_log_stats']['total_logs'] + 1,
            'timestamp': datetime.now().isoformat(),
            'action': 'delete',
            'sku': sku,
            'user': modified_by,
            'data': deleted_data
        })
        
        # Update stats
        data['audit_log_stats']['total_logs'] += 1
        data['audit_log_stats']['last_log'] = datetime.now().isoformat()

        self._write_data(data)
        return True
    
    def decrement_sku(self, sku: str, qty: int, orders_count: int = 1) -> Optional[Dict]:
        data = self._read_data()
        
        if sku not in data['skus']:
            return None
        
        print(f'SKU: {sku}, qty: {qty}, orders_count: {orders_count}')
        data['skus'][sku]['available_qty'] -= qty
        data['skus'][sku]['orders_processed'] += orders_count
        data['skus'][sku]['last_modified'] = datetime.now().isoformat()
        data['skus'][sku]['modified_by'] = 'auto-sync'
        
        self._write_data(data)
        return data['skus'][sku]
    
    def get_config(self) -> Dict:
        data = self._read_data()
        return data.get('config', {})
    
    def update_config(self, updates: Dict):
        data = self._read_data()
        data['config'].update(updates)
        self._write_data(data)
    
    def get_audit_log(self, limit: int = 50) -> list:
        data = self._read_data()
        return data.get('audit_log', [])[-limit:]
    
    def get_log_stats(self) -> dict:
        """Get log statistics"""
        data = self._read_data()
        logs = data.get('audit_log', [])
        return {
            'total_logs': data['audit_log_stats'].get('total_logs', 0),
            'last_log': data['audit_log_stats'].get('last_log'),
            'current_logs': len(logs),
        }
    
    def get_log_by_id(self, log_id: int) -> Optional[dict]:
        """Get a specific audit log entry by ID"""
        data = self._read_data()
        logs = data.get('audit_log', [])

        for log in logs:
            if log.get('id') == log_id:
                return log
        return None
    
    def clear_all_logs(self) -> int:
        """
        Clear all logs from the audit log

        Returns:
            Number of logs cleared
        """
        data = self._read_data()
        log_count = len(data.get('audit_log', []))

        data['audit_log'] = []
        data['audit_log_stats'] = {
            'total_logs': 0,
            'last_log': None
        }

        self._write_data(data)
        return log_count


class ErrorLogger:
    """Separate class for managing error logs in a dedicated JSON file"""

    def __init__(self, filepath: str = Config.ERROR_LOG_FILE):
        self.filepath = filepath
        self.lock = threading.Lock()
        self._ensure_file_exists()
        self._admin_email = os.getenv('ADMIN_EMAIL')
        self._sender_email = os.getenv('SENDER_EMAIL')

    def _ensure_file_exists(self):
        """Create the error log file if it doesn't exist"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    content = f.read().strip()
                    if content:
                        json.loads(content)
                        return
            except (json.JSONDecodeError, IOError):
                pass

        # Create or recreate the file
        initial_data = {
            "errors": [],
            "stats": {
                "total_errors": 0,
                "last_error": None
            }
        }
        with open(self.filepath, 'w') as f:
            json.dump(initial_data, f, indent=2)

    def _read_data(self) -> dict:
        """Read error log data with retry logic"""
        with self.lock:
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with open(self.filepath, 'r') as f:
                        data = json.load(f)
                    return data
                except (IOError, json.JSONDecodeError) as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.1)
                    else:
                        raise

    def _write_data(self, data: dict):
        """Write error log data atomically"""
        with self.lock:
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    temp_file = self.filepath + '.tmp'
                    with open(temp_file, 'w') as f:
                        json.dump(data, f, indent=2)

                    if os.path.exists(self.filepath):
                        os.replace(temp_file, self.filepath)
                    else:
                        os.rename(temp_file, self.filepath)
                    break
                except IOError as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.1)
                    else:
                        raise

    def log_error(self, error_type: str, message: str, source: str = 'unknown',
                  details: dict = None, user: str = 'system') -> dict:
        """
        Log an error to the error log file

        Args:
            error_type: Type of error (e.g., 'sync_error', 'api_error', 'database_error')
            message: Error message
            source: Where the error occurred (e.g., 'sync.py', 'app.py')
            details: Additional error details (optional)
            user: User associated with the error (optional)

        Returns:
            The error entry that was logged
        """
        data = self._read_data()

        error_entry = {
            'id': data['stats']['total_errors'] + 1,
            'timestamp': datetime.now().isoformat(),
            'error_type': error_type,
            'message': message,
            'source': source,
            'user': user,
            'details': details or {},
            'resolved': False
        }


        # helps prevent tons of emails being sent out for the exact same issue. 
        errors = data.get('errors', [])
        errors = [e for e in errors if not e.get('resolved', False)]    # unsresolved errors only.
        same_err_flag = 0
        for e in errors:
            if e['error_type'] == error_type and e['message'] == message and e['source'] == source and e['resolved'] is False:
                same_err_flag = 1

        # Add to errors list
        data['errors'].append(error_entry)

        # Update stats
        data['stats']['total_errors'] += 1
        data['stats']['last_error'] = datetime.now().isoformat()

        self._write_data(data)

        # send an error email only if its a new error:
        if same_err_flag == 0:
            print('sending email.')
            email_body_error = "<ul>"
            for key in error_entry.keys():
                email_body_error += f"<li><b>{key}</b>: {error_entry[key]}</li>" 
            email_body_error += "</ul>"

            email_body = f"""The <b>Retail Inventory Manager</b> experienced a new error. Please review and resolve:
            <br><br>
            {email_body_error}
            """
            email_subject = "Error Summary Email: Retail Inventory Manager"
            self.send_email(email_subject, email_body, [self._admin_email])

        same_err_flag = 0
        return error_entry

    def get_errors(self, limit: int = 50, unresolved_only: bool = False) -> list:
        """
        Get error logs

        Args:
            limit: Maximum number of errors to return (most recent)
            unresolved_only: If True, only return unresolved errors

        Returns:
            List of error entries
        """
        data = self._read_data()
        errors = data.get('errors', [])

        if unresolved_only:
            errors = [e for e in errors if not e.get('resolved', False)]

        # Return most recent errors first
        return list(reversed(errors[-limit:]))

    def get_error_by_id(self, error_id: int) -> Optional[dict]:
        """Get a specific error by ID"""
        data = self._read_data()
        errors = data.get('errors', [])

        for error in errors:
            if error.get('id') == error_id:
                return error
        return None

    def mark_resolved(self, error_id: int, resolved_by: str = 'system') -> bool:
        """
        Mark an error as resolved

        Args:
            error_id: ID of the error to mark as resolved
            resolved_by: Who resolved the error

        Returns:
            True if successful, False if error not found
        """
        data = self._read_data()
        errors = data.get('errors', [])

        for error in errors:
            if error.get('id') == error_id:
                error['resolved'] = True
                error['resolved_at'] = datetime.now().isoformat()
                error['resolved_by'] = resolved_by
                self._write_data(data)
                return True

        return False

    def clear_all_errors(self) -> int:
        """
        Clear all errors from the log

        Returns:
            Number of errors cleared
        """
        data = self._read_data()
        error_count = len(data.get('errors', []))

        data['errors'] = []
        data['stats'] = {
            'total_errors': 0,
            'last_error': None
        }

        self._write_data(data)
        return error_count

    def get_stats(self) -> dict:
        """Get error statistics"""
        data = self._read_data()
        errors = data.get('errors', [])

        unresolved_count = sum(1 for e in errors if not e.get('resolved', False))

        return {
            'total_errors': data['stats'].get('total_errors', 0),
            'last_error': data['stats'].get('last_error'),
            'current_errors': len(errors),
            'unresolved_errors': unresolved_count,
            'resolved_errors': len(errors) - unresolved_count
        }
    
    def send_email(self, subject: str, html_body: str, recipients: list, attachments=[], sender=None) -> None:
        ''' sends a basic notification email '''

        sender = self._sender_email if not sender else sender

        payload = {
            "sender": sender,
            "to": recipients,
            "subject": subject,
            "html_body": html_body
        }

        url = "https://api.smtp2go.com/v3/email/send"

        headers = {
        'Content-Type': 'application/json',
        'url': 'https://api.smtp2go.com/v3/',
        'X-Smtp2go-Api-Key': os.getenv('SMTP2GO_KEY')
        }

        # Convert file paths to base64-encoded attachments
        if attachments and len(attachments) > 0:
            encoded_attachments = []
            for filepath in attachments:
                with open(filepath, "rb") as f:
                    file_data = f.read()
                    encoded_attachments.append({
                        "filename": os.path.basename(filepath),
                        "fileblob": base64.b64encode(file_data).decode("utf-8")
                    })
            print(encoded_attachments)
            payload["attachments"] = encoded_attachments

        payload = json.dumps(payload)

        response = requests.request("POST", url, headers=headers, data=payload)
        print(f'email send response: {response}')
        return response
