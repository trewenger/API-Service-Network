import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-to-random-secret-key')

    # Admin email for triggered error email logging
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'user@example.com')
    SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'sender@example.com')
    
    # Admin credentials
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'changeme')

    # Ryan's credentials
    RYAN_USERNAME = os.getenv('RYAN_USERNAME', 'none')
    RYAN_PW = os.getenv('RYAN_PW', 'none')

    # Jake's credentials
    JAKE_USERNAME = os.getenv('JAKE_USERNAME', 'none')
    JAKE_PW = os.getenv('JAKE_PW', 'none')
    
    # Fishbowl API settings
    FISHBOWL_SERVER_ADDRESS = os.getenv('FISHBOWL_SERVER_ADDRESS', 'localhost')
    FISHBOWL_PROD_PORT = os.getenv('FISHBOWL_PROD_PORT')
    FISHBOWL_TEST_PORT = os.getenv('FISHBOWL_TEST_PORT')
    FISHBOWL_APP_NAME = os.getenv('FISHBOWL_APP_NAME')
    FISHBOWL_APP_DESCRIPTION = os.getenv('FISHBOWL_APP_DESCRIPTION')
    FISHBOWL_APP_ID = os.getenv('FISHBOWL_APP_ID')
    FISHBOWL_USERNAME = os.getenv('FISHBOWL_USERNAME', 'admin')
    FISHBOWL_PASSWORD = os.getenv('FISHBOWL_PASSWORD', 'password')
    USE_TEST_DB = os.getenv('USE_TEST_DB', 'False').lower() == 'true'
    COMPANY_NAME = os.getenv('COMPANY_NAME', 'Fishbowl Company Name Example')
    
    # Sync settings
    SYNC_INTERVAL_MINUTES = int(os.getenv('SYNC_INTERVAL_MINUTES', '5'))
    SALES_INTERVAL_MINUTES = int(os.getenv('SYNC_INTERVAL_MINUTES', '5'))
    
    # Data files
    DATA_FILE = os.getenv('DATA_FILE', 'RetailInventoryManager/inventory.json')
    ERROR_LOG_FILE = os.getenv('ERROR_LOG_FILE', 'RetailInventoryManager/error_log.json')
    