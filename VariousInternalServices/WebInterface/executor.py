"""
Script Execution Orchestration for VariousInternalServices Web Interface

Manages execution of the 4 automation scripts in separate threads,
captures SessionLog output, and updates run history.
"""

import sys
import os
import importlib
from datetime import datetime
import threading
import traceback
from typing import Dict, Optional
import logging

# Add parent directory to path to import scripts
PARENT_DIR = os.path.join(os.path.dirname(__file__), '..')
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from config import Config
from data import ScriptConfigData, RunHistoryData, ErrorLogger

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScriptExecutor:
    """
    Manages execution of VariousInternalServices scripts in separate threads.
    Captures SessionLog output and updates run history.
    """

    def __init__(self):
        self.config_data = ScriptConfigData()
        self.history_data = RunHistoryData()
        self.error_logger = ErrorLogger()
        self.running_scripts = {}  # {script_name: thread}
        self.lock = threading.Lock()

    def execute_script(self, script_name: str, trigger_type: str = 'manual',
                      triggered_by: str = 'system') -> Dict:
        """
        Execute a script in a separate thread.

        Args:
            script_name: Name of script (OnTimePerformance, TaxSystemHealth, VendorTracker, WipUpdate)
            trigger_type: 'manual' or 'scheduled'
            triggered_by: Username or 'system'

        Returns:
            Dict with execution result {'success': bool, 'run_id': int, 'message': str}
        """
        try:
            # Check if script is already running
            with self.lock:
                if script_name in self.running_scripts:
                    return {
                        'success': False,
                        'error': f'{script_name} is already running'
                    }

            # Get script config
            script_config = self.config_data.get_script_config(script_name)
            if not script_config:
                return {
                    'success': False,
                    'error': f'Script {script_name} not found in configuration'
                }

            # Create run history entry
            run_id = self.history_data.add_run(
                script_name=script_name,
                trigger_type=trigger_type,
                triggered_by=triggered_by
            )

            # Update script status to "running"
            self.config_data.update_status(script_name, 'running')

            # Start execution thread
            thread = threading.Thread(
                target=self._run_script_thread,
                args=(script_name, run_id),
                daemon=True,
                name=f'ScriptExecutor-{script_name}-{run_id}'
            )

            with self.lock:
                self.running_scripts[script_name] = thread

            thread.start()

            logger.info(f"Started execution of {script_name} (run_id={run_id}, trigger={trigger_type}, user={triggered_by})")

            return {
                'success': True,
                'run_id': run_id,
                'message': f'{script_name} execution started'
            }

        except Exception as e:
            logger.error(f"Error starting script {script_name}: {e}")
            self.error_logger.log_error(
                error_type='execution_start_error',
                message=f"Failed to start {script_name}: {str(e)}",
                source='executor.py:execute_script',
                details={'script_name': script_name, 'error': str(e), 'traceback': traceback.format_exc()},
                user=triggered_by
            )
            return {
                'success': False,
                'error': str(e)
            }

    def _run_script_thread(self, script_name: str, run_id: int):
        """
        Thread worker that actually executes the script.
        Captures SessionLog output and updates run history.

        Args:
            script_name: Name of the script to execute
            run_id: Run ID from run_history
        """
        start_time = datetime.now()
        session_log = None

        try:
            # Get script metadata
            script_meta = Config.AVAILABLE_SCRIPTS.get(script_name)
            if not script_meta:
                raise Exception(f"Script {script_name} not defined in AVAILABLE_SCRIPTS")

            # Get script configuration
            script_config = self.config_data.get_script_config(script_name)

            # Dynamically import the script module
            logger.info(f"Importing module '{script_meta['module']}' for {script_name}")
            module = importlib.import_module(script_meta['module'])
            script_function = getattr(module, script_meta['function'])

            # Build function arguments
            kwargs = self._build_script_arguments(script_name, script_config)

            # Execute the script function
            logger.info(f"Executing {script_name} with args: {list(kwargs.keys())}")
            session_log = script_function(**kwargs)

            # Calculate duration
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Extract logs from SessionLog object
            logs = {}
            error_flag = 0

            if session_log and hasattr(session_log, 'get_log'):
                logs = session_log.get_log()

            if session_log and hasattr(session_log, 'error_flag'):
                error_flag = session_log.error_flag()

            # Determine status
            status = 'success' if error_flag == 0 else 'error'

            # Generate summary
            result_summary = self._generate_summary(script_name, logs, error_flag)

            # Update run history
            self.history_data.update_run(run_id, {
                'end_time': end_time.isoformat(),
                'duration_seconds': int(duration),
                'status': status,
                'error_flag': error_flag,
                'session_log': logs,
                'result_summary': result_summary,
                'email_sent': True  # Scripts send their own emails
            })

            # Update script status and metadata
            self.config_data.update_status(script_name, 'error' if error_flag else 'idle')
            self.config_data.increment_run_count(script_name)
            self.config_data.update_last_run(script_name, end_time.isoformat())

            logger.info(f"Completed {script_name} in {duration:.2f}s with status: {status} (run_id={run_id})")

        except Exception as e:
            # Handle execution errors
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            error_msg = str(e)
            error_trace = traceback.format_exc()

            logger.error(f"Error executing {script_name} (run_id={run_id}): {error_msg}")
            logger.error(error_trace)

            # Update run history with error
            self.history_data.update_run(run_id, {
                'end_time': end_time.isoformat(),
                'duration_seconds': int(duration),
                'status': 'error',
                'error_flag': 1,
                'session_log': {
                    'execution_error': [error_msg],
                    'traceback': [error_trace]
                },
                'result_summary': f'Failed: {error_msg}',
                'email_sent': False
            })

            # Update script status to error
            self.config_data.update_status(script_name, 'error')

            # Log to error logger
            self.error_logger.log_error(
                error_type='script_execution_error',
                message=f"{script_name} execution failed: {error_msg}",
                source='executor.py:_run_script_thread',
                details={
                    'script_name': script_name,
                    'run_id': run_id,
                    'traceback': error_trace
                }
            )

        finally:
            # Remove from running scripts
            with self.lock:
                if script_name in self.running_scripts:
                    del self.running_scripts[script_name]

    def _build_script_arguments(self, script_name: str, script_config: Dict) -> Dict:
        """
        Build function arguments for each script based on its signature.
        Maps script_config custom_params to the function's expected parameters.

        Args:
            script_name: Name of the script
            script_config: Script configuration from script_config.json

        Returns:
            Dict of keyword arguments to pass to the script function
        """
        custom_params = script_config.get('custom_params', {})
        email_recipients = script_config.get('email_recipients', [])

        # Each script has different parameters - map them here
        if script_name == 'OnTimePerformance':
            return {
                'result_recipients': email_recipients,
                'custom_headers': custom_params.get('custom_headers', []),
                'query_name': custom_params.get('query_name', 'OnTimePerformance.sql'),
                'last_row': custom_params.get('last_row', 200000)
            }

        elif script_name == 'TaxSystemHealth':
            return {
                'result_recipients': email_recipients,
                'product_query_name': custom_params.get('product_query_name', 'TaxHealthProductCheck'),
                'customer_query_name': custom_params.get('customer_query_name', 'TaxHealthCustomerCheck')
            }

        elif script_name == 'VendorTracker':
            return {
                'email_rec': email_recipients,
                'column_order': custom_params.get('column_order', []),
                'sheet_name': custom_params.get('sheet_name', 'import'),
                'query_name': custom_params.get('query_name', 'VendorTracker'),
                'paste_range': custom_params.get('paste_range', 'A3:D'),
                'last_updated_cell': custom_params.get('last_updated_cell', 'E3:E3'),
                'wip_name_range': custom_params.get('wip_name_range', 'Q2:Q')
            }

        elif script_name == 'WipUpdate':
            return {
                'email_recipients': email_recipients,
                'last_week_ship_query_name': custom_params.get('last_week_ship_query_name', 'WipLastWeekShip'),
                'six_month_ship_query_name': custom_params.get('six_month_ship_query_name', 'WipSixMonthShip'),
                'bo_query_name': custom_params.get('bo_query_name', 'WipBO')
            }

        else:
            # Fallback for unknown scripts
            logger.warning(f"Unknown script {script_name}, using default parameters")
            return {'result_recipients': email_recipients}

    def _generate_summary(self, script_name: str, logs: Dict, error_flag: int) -> str:
        """
        Generate human-readable summary from session logs.

        Args:
            script_name: Name of the script
            logs: SessionLog dictionary
            error_flag: Error flag from SessionLog

        Returns:
            Summary string
        """
        if error_flag:
            # Find first error message in logs
            for func, messages in logs.items():
                if not isinstance(messages, list):
                    continue
                for msg in messages:
                    if isinstance(msg, str) and ('error' in msg.lower() or 'fail' in msg.lower()):
                        return f"Failed: {msg[:100]}"
            return "Failed: Unknown error"
        else:
            # Success - try to extract meaningful info
            entry_count = 0

            # Look for common success patterns
            for func, messages in logs.items():
                if not isinstance(messages, list):
                    continue
                for msg in messages:
                    if isinstance(msg, str):
                        if 'pasted' in msg.lower() and 'entries' in msg.lower():
                            return f"Success: {msg}"
                        if 'entries to the Database' in msg:
                            return f"Success: {msg}"
                        if 'completed' in msg.lower():
                            entry_count += 1

            if entry_count > 0:
                return f"Success: Completed without errors ({entry_count} operations)"

            return "Success: Completed without errors"

    def is_script_running(self, script_name: str) -> bool:
        """
        Check if a script is currently running.

        Args:
            script_name: Name of the script

        Returns:
            True if running, False otherwise
        """
        with self.lock:
            return script_name in self.running_scripts

    def get_running_scripts(self) -> list:
        """
        Get list of currently running scripts.

        Returns:
            List of script names currently running
        """
        with self.lock:
            return list(self.running_scripts.keys())

    def get_script_status(self, script_name: str) -> Dict:
        """
        Get current status of a script.

        Args:
            script_name: Name of the script

        Returns:
            Dict with status information
        """
        config = self.config_data.get_script_config(script_name)
        is_running = self.is_script_running(script_name)

        if not config:
            return {'error': 'Script not found'}

        return {
            'script_name': script_name,
            'status': 'running' if is_running else config.get('status', 'idle'),
            'enabled': config.get('enabled', False),
            'last_run': config.get('last_run'),
            'next_run': config.get('next_run'),
            'run_count': config.get('run_count', 0),
            'is_running': is_running
        }
