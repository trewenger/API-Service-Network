"""
Configuration module for VariousInternalServices Web Interface

Loads environment variables and defines script metadata for the 4 automation scripts.
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""

    # Flask settings
    SECRET_KEY = os.getenv('VIS_SECRET_KEY', 'dev-secret-key-change-in-production')

    # Admin credentials (separate from RetailInventoryManager)
    ADMIN_USERNAME = os.getenv('VIS_ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('VIS_ADMIN_PASSWORD', 'changeme')

    # Additional users
    USER2_USERNAME = os.getenv('VIS_USER2_USERNAME', 'user2')
    USER2_PASSWORD = os.getenv('VIS_USER2_PASSWORD', 'changeme')

    # Email settings (SMTP2GO)
    SMTP2GO_API_KEY = os.getenv('SMTP2GO_API_KEY')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')
    SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'noreply@example.com')

    # Data files (relative to WebInterface directory)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SCRIPT_CONFIG_FILE = os.path.join(BASE_DIR, 'data', 'script_config.json')
    RUN_HISTORY_FILE = os.path.join(BASE_DIR, 'data', 'run_history.json')
    ERROR_LOG_FILE = os.path.join(BASE_DIR, 'data', 'error_log.json')

    # Script execution settings
    MAX_CONCURRENT_RUNS = int(os.getenv('MAX_CONCURRENT_RUNS', '1'))
    RUN_HISTORY_RETENTION_DAYS = int(os.getenv('RUN_HISTORY_RETENTION_DAYS', '90'))
    SCRIPT_TIMEOUT_MINUTES = int(os.getenv('SCRIPT_TIMEOUT_MINUTES', '60'))

    # Script definitions - metadata for each automation script
    AVAILABLE_SCRIPTS = {
        'OnTimePerformance': {
            'display_name': 'On-Time Performance',
            'description': 'Daily sync of fulfilled orders to On-Time Performance tracker',
            'module': 'OnTimePerformance',
            'function': 'on_time_performance',
            'icon': '📦',
            'default_schedule': 1440,  # daily (24 hours * 60 minutes)
            'default_recipients': [ADMIN_EMAIL],
            'default_custom_params': {
                'query_name': 'OnTimePerformance.sql',
                'custom_headers': [],
                'last_row': 200000
            }
        },
        'TaxSystemHealth': {
            'display_name': 'Tax System Health',
            'description': 'Validates product tax codes and customer exempt statuses',
            'module': 'TaxSystemHealth',
            'function': 'tax_system_health',
            'icon': '💰',
            'default_schedule': 10080,  # weekly (7 days * 24 hours * 60 minutes)
            'default_recipients': [ADMIN_EMAIL],
            'default_custom_params': {
                'product_query_name': 'TaxHealthProductCheck',
                'customer_query_name': 'TaxHealthCustomerCheck'
            }
        },
        'VendorTracker': {
            'display_name': 'Vendor Tracker',
            'description': 'Tracks parts at vendor (outsourced parts shipped but not received)',
            'module': 'VendorTracker',
            'function': 'vendor_tracker',
            'icon': '🚚',
            'default_schedule': 1440,  # daily
            'default_recipients': [ADMIN_EMAIL],
            'default_custom_params': {
                'column_order': ['PartNumber', 'Description', 'Qty', 'WipName'],
                'sheet_name': 'import',
                'query_name': 'VendorTracker',
                'paste_range': 'A3:D',
                'last_updated_cell': 'E3:E3',
                'wip_name_range': 'Q2:Q'
            }
        },
        'WipUpdate': {
            'display_name': 'WIP Tracker Update',
            'description': 'Updates WIP tracker with inventory data, shipped reports, and backorders',
            'module': 'WipUpdate',
            'function': 'wip_update',
            'icon': '🔄',
            'default_schedule': 10080,  # weekly
            'default_recipients': [ADMIN_EMAIL],
            'default_custom_params': {
                'last_week_ship_query_name': 'WipLastWeekShip',
                'six_month_ship_query_name': 'WipSixMonthShip',
                'bo_query_name': 'WipBO'
            }
        }
    }

    # User credentials mapping
    USERS = {
        ADMIN_USERNAME: ADMIN_PASSWORD,
        USER2_USERNAME: USER2_PASSWORD
    }
