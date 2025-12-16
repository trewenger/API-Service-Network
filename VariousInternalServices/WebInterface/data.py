"""
Data layer for VariousInternalServices Web Interface

Provides thread-safe JSON file operations for script configuration,
run history, and error logging.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests
from config import Config


class ScriptConfigData:
    """
    Manages script configuration data with thread-safe file operations.
    Stores script settings, schedules, recipients, and status.
    """

    def __init__(self, config_file: str = None):
        self.config_file = config_file or Config.SCRIPT_CONFIG_FILE
        self.lock = threading.Lock()
        self._initialize_config()

    def _initialize_config(self):
        """Initialize config file with default values if it doesn't exist"""
        if not os.path.exists(self.config_file):
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            # Create initial config from AVAILABLE_SCRIPTS
            initial_config = {'scripts': {}}

            for script_name, metadata in Config.AVAILABLE_SCRIPTS.items():
                initial_config['scripts'][script_name] = {
                    'enabled': False,  # Start disabled
                    'schedule_value': metadata['default_schedule'],
                    'email_recipients': metadata['default_recipients'],
                    'custom_params': metadata['default_custom_params'],
                    'last_run': None,
                    'next_run': None,
                    'run_count': 0,
                    'status': 'idle'  # idle, running, error
                }

            initial_config['global_config'] = {
                'default_schedule_interval': 1440,
                'max_concurrent_runs': Config.MAX_CONCURRENT_RUNS,
                'run_history_retention_days': Config.RUN_HISTORY_RETENTION_DAYS,
                'enable_email_notifications': True
            }

            self._write_with_retry(initial_config)

    def _read_with_retry(self, max_attempts: int = 5, delay: float = 0.1) -> Dict:
        """Read JSON file with retry logic"""
        for attempt in range(max_attempts):
            try:
                with self.lock:
                    with open(self.config_file, 'r') as f:
                        return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                if attempt == max_attempts - 1:
                    raise Exception(f"Failed to read {self.config_file} after {max_attempts} attempts: {e}")
                time.sleep(delay)
        return {}

    def _write_with_retry(self, data: Dict, max_attempts: int = 5, delay: float = 0.1):
        """Write JSON file with atomic operations and retry logic"""
        for attempt in range(max_attempts):
            try:
                with self.lock:
                    # Write to temp file first (atomic operation)
                    temp_file = self.config_file + '.tmp'
                    with open(temp_file, 'w') as f:
                        json.dump(data, f, indent=2)

                    # Atomic replace
                    os.replace(temp_file, self.config_file)
                return
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise Exception(f"Failed to write {self.config_file} after {max_attempts} attempts: {e}")
                time.sleep(delay)

    def get_all_scripts(self) -> Dict:
        """Get all script configurations"""
        data = self._read_with_retry()
        return data.get('scripts', {})

    def get_script_config(self, script_name: str) -> Optional[Dict]:
        """Get configuration for a specific script"""
        scripts = self.get_all_scripts()
        return scripts.get(script_name)

    def update_script_config(self, script_name: str, updates: Dict):
        """Update script configuration"""
        data = self._read_with_retry()

        if script_name not in data['scripts']:
            raise ValueError(f"Script {script_name} not found in configuration")

        data['scripts'][script_name].update(updates)
        self._write_with_retry(data)

    def toggle_script(self, script_name: str, enabled: bool):
        """Enable or disable a script"""
        self.update_script_config(script_name, {'enabled': enabled})

    def update_schedule(self, script_name: str, schedule_value: int):
        """Update script schedule interval (in minutes)"""
        self.update_script_config(script_name, {'schedule_value': schedule_value})

    def update_email_recipients(self, script_name: str, recipients: List[str]):
        """Update email recipients list"""
        self.update_script_config(script_name, {'email_recipients': recipients})

    def update_next_run(self, script_name: str, next_run_time: str):
        """Update next scheduled run time"""
        self.update_script_config(script_name, {'next_run': next_run_time})

    def update_status(self, script_name: str, status: str):
        """Update script status (idle, running, error)"""
        if status not in ['idle', 'running', 'error']:
            raise ValueError(f"Invalid status: {status}. Must be idle, running, or error")
        self.update_script_config(script_name, {'status': status})

    def increment_run_count(self, script_name: str):
        """Increment the run count for a script"""
        config = self.get_script_config(script_name)
        if config:
            new_count = config.get('run_count', 0) + 1
            self.update_script_config(script_name, {'run_count': new_count})

    def update_last_run(self, script_name: str, last_run_time: str):
        """Update last run timestamp"""
        self.update_script_config(script_name, {'last_run': last_run_time})


class RunHistoryData:
    """
    Manages script execution history with thread-safe file operations.
    Stores run details, SessionLog output, and execution results.
    """

    def __init__(self, history_file: str = None):
        self.history_file = history_file or Config.RUN_HISTORY_FILE
        self.lock = threading.Lock()
        self._initialize_history()

    def _initialize_history(self):
        """Initialize history file if it doesn't exist"""
        if not os.path.exists(self.history_file):
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            initial_data = {
                'runs': [],
                'stats': {
                    'total_runs': 0,
                    'successful_runs': 0,
                    'failed_runs': 0,
                    'last_run': None
                }
            }
            self._write_with_retry(initial_data)

    def _read_with_retry(self, max_attempts: int = 5, delay: float = 0.1) -> Dict:
        """Read JSON file with retry logic"""
        for attempt in range(max_attempts):
            try:
                with self.lock:
                    with open(self.history_file, 'r') as f:
                        return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                if attempt == max_attempts - 1:
                    raise Exception(f"Failed to read {self.history_file} after {max_attempts} attempts: {e}")
                time.sleep(delay)
        return {}

    def _write_with_retry(self, data: Dict, max_attempts: int = 5, delay: float = 0.1):
        """Write JSON file with atomic operations and retry logic"""
        for attempt in range(max_attempts):
            try:
                with self.lock:
                    # Write to temp file first
                    temp_file = self.history_file + '.tmp'
                    with open(temp_file, 'w') as f:
                        json.dump(data, f, indent=2)

                    # Atomic replace
                    os.replace(temp_file, self.history_file)
                return
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise Exception(f"Failed to write {self.history_file} after {max_attempts} attempts: {e}")
                time.sleep(delay)

    def add_run(self, script_name: str, trigger_type: str, triggered_by: str) -> int:
        """
        Create a new run record and return its ID

        Args:
            script_name: Name of the script
            trigger_type: 'manual' or 'scheduled'
            triggered_by: Username or 'system'

        Returns:
            Run ID
        """
        data = self._read_with_retry()

        # Generate new run ID
        run_id = max([run['id'] for run in data['runs']], default=0) + 1

        # Create run record
        new_run = {
            'id': run_id,
            'script_name': script_name,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'duration_seconds': None,
            'trigger_type': trigger_type,
            'triggered_by': triggered_by,
            'status': 'running',
            'error_flag': 0,
            'session_log': {},
            'result_summary': 'Running...',
            'email_sent': False
        }

        data['runs'].insert(0, new_run)  # Add to beginning
        data['stats']['total_runs'] += 1

        self._write_with_retry(data)
        return run_id

    def update_run(self, run_id: int, updates: Dict):
        """Update an existing run record"""
        data = self._read_with_retry()

        # Find and update the run
        for run in data['runs']:
            if run['id'] == run_id:
                run.update(updates)

                # Update stats
                if updates.get('status') == 'success':
                    data['stats']['successful_runs'] += 1
                elif updates.get('status') == 'error':
                    data['stats']['failed_runs'] += 1

                if updates.get('end_time'):
                    data['stats']['last_run'] = updates['end_time']

                break

        self._write_with_retry(data)

    def get_run_history(self, script_name: str = None, limit: int = 50,
                       status_filter: str = None) -> List[Dict]:
        """
        Get run history with optional filtering

        Args:
            script_name: Filter by script name (optional)
            limit: Maximum number of runs to return
            status_filter: Filter by status (success/error/running)

        Returns:
            List of run records
        """
        data = self._read_with_retry()
        runs = data.get('runs', [])

        # Apply filters
        if script_name:
            runs = [r for r in runs if r['script_name'] == script_name]

        if status_filter:
            runs = [r for r in runs if r['status'] == status_filter]

        # Apply limit
        return runs[:limit]

    def get_run_by_id(self, run_id: int) -> Optional[Dict]:
        """Get a specific run by ID"""
        data = self._read_with_retry()
        for run in data.get('runs', []):
            if run['id'] == run_id:
                return run
        return None

    def delete_run(self, run_id: int) -> bool:
        """Delete a specific run by ID"""
        data = self._read_with_retry()
        runs = data.get('runs', [])

        # Find and remove the run
        original_length = len(runs)
        data['runs'] = [run for run in runs if run['id'] != run_id]

        # Check if anything was deleted
        if len(data['runs']) < original_length:
            self._write_with_retry(data)
            return True
        return False

    def get_stats(self) -> Dict:
        """Get aggregate statistics"""
        data = self._read_with_retry()
        return data.get('stats', {})

    def cleanup_old_runs(self, retention_days: int = None):
        """Remove run history older than retention period"""
        retention_days = retention_days or Config.RUN_HISTORY_RETENTION_DAYS
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        data = self._read_with_retry()

        # Keep only recent runs
        data['runs'] = [
            run for run in data['runs']
            if run.get('start_time') and
            datetime.fromisoformat(run['start_time']) > cutoff_date
        ]

        self._write_with_retry(data)


class ErrorLogger:
    """
    Manages system/application error logging with email notifications.
    Separate from script execution errors (which are in run history).
    """

    def __init__(self, error_file: str = None):
        self.error_file = error_file or Config.ERROR_LOG_FILE
        self.lock = threading.Lock()
        self._initialize_log()

    def _initialize_log(self):
        """Initialize error log file if it doesn't exist"""
        if not os.path.exists(self.error_file):
            os.makedirs(os.path.dirname(self.error_file), exist_ok=True)
            initial_data = {
                'errors': [],
                'stats': {
                    'total_errors': 0,
                    'last_error': None
                }
            }
            self._write_with_retry(initial_data)

    def _read_with_retry(self, max_attempts: int = 5, delay: float = 0.1) -> Dict:
        """Read JSON file with retry logic"""
        for attempt in range(max_attempts):
            try:
                with self.lock:
                    with open(self.error_file, 'r') as f:
                        return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                if attempt == max_attempts - 1:
                    raise Exception(f"Failed to read {self.error_file} after {max_attempts} attempts: {e}")
                time.sleep(delay)
        return {}

    def _write_with_retry(self, data: Dict, max_attempts: int = 5, delay: float = 0.1):
        """Write JSON file with atomic operations and retry logic"""
        for attempt in range(max_attempts):
            try:
                with self.lock:
                    temp_file = self.error_file + '.tmp'
                    with open(temp_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    os.replace(temp_file, self.error_file)
                return
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise Exception(f"Failed to write {self.error_file} after {max_attempts} attempts: {e}")
                time.sleep(delay)

    def log_error(self, error_type: str, message: str, source: str,
                  details: Dict = None, user: str = 'system', send_email: bool = True):
        """
        Log an error with optional email notification

        Args:
            error_type: Type of error (scheduler_error, execution_error, etc.)
            message: Error message
            source: Source file:function
            details: Additional error details
            user: User who triggered the action (or 'system')
            send_email: Whether to send email notification
        """
        data = self._read_with_retry()

        # Create error record
        error_id = max([err['id'] for err in data['errors']], default=0) + 1
        timestamp = datetime.now().isoformat()

        error_record = {
            'id': error_id,
            'timestamp': timestamp,
            'error_type': error_type,
            'message': message,
            'source': source,
            'user': user,
            'details': details or {},
            'resolved': False
        }

        # Check for duplicates (prevent email spam)
        is_duplicate = any(
            err['message'] == message and
            err['source'] == source and
            not err['resolved'] and
            (datetime.now() - datetime.fromisoformat(err['timestamp'])).total_seconds() < 3600
            for err in data['errors']
        )

        # Add error to log
        data['errors'].insert(0, error_record)
        data['stats']['total_errors'] += 1
        data['stats']['last_error'] = timestamp

        self._write_with_retry(data)

        # Send email if not duplicate and email is enabled
        if send_email and not is_duplicate:
            self._send_email(error_record)

    def _send_email(self, error: Dict):
        """Send email notification for error"""
        try:
            if not Config.SMTP2GO_API_KEY:
                return

            subject = f"[VIS Error] {error['error_type']}: {error['message'][:50]}"

            html_body = f"""
            <h2>VariousInternalServices Error Report</h2>
            <p><strong>Error ID:</strong> {error['id']}</p>
            <p><strong>Time:</strong> {error['timestamp']}</p>
            <p><strong>Type:</strong> {error['error_type']}</p>
            <p><strong>Source:</strong> {error['source']}</p>
            <p><strong>User:</strong> {error['user']}</p>
            <p><strong>Message:</strong></p>
            <pre>{error['message']}</pre>
            <p><strong>Details:</strong></p>
            <pre>{json.dumps(error['details'], indent=2)}</pre>
            """

            url = "https://api.smtp2go.com/v3/email/send"
            payload = {
                "api_key": Config.SMTP2GO_API_KEY,
                "to": [Config.ADMIN_EMAIL],
                "sender": Config.SENDER_EMAIL,
                "subject": subject,
                "html_body": html_body
            }

            requests.post(url, json=payload, timeout=10)

        except Exception as e:
            # Don't fail if email fails
            print(f"Failed to send error email: {e}")

    def get_errors(self, limit: int = 50, unresolved_only: bool = False) -> List[Dict]:
        """Get error log with optional filtering"""
        data = self._read_with_retry()
        errors = data.get('errors', [])

        if unresolved_only:
            errors = [e for e in errors if not e['resolved']]

        return errors[:limit]

    def get_error_by_id(self, error_id: int) -> Optional[Dict]:
        """Get a specific error by ID"""
        data = self._read_with_retry()
        for error in data.get('errors', []):
            if error['id'] == error_id:
                return error
        return None

    def mark_resolved(self, error_id: int):
        """Mark an error as resolved"""
        data = self._read_with_retry()

        for error in data['errors']:
            if error['id'] == error_id:
                error['resolved'] = True
                break

        self._write_with_retry(data)

    def clear_all_errors(self):
        """Clear all errors from the log"""
        data = {
            'errors': [],
            'stats': {
                'total_errors': 0,
                'last_error': None
            }
        }
        self._write_with_retry(data)

    def get_stats(self) -> Dict:
        """Get error statistics"""
        data = self._read_with_retry()
        return data.get('stats', {})
