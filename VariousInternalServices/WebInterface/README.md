# VariousInternalServices Web Interface

Web-based management interface for the 4 automation scripts in VariousInternalServices:
- **OnTimePerformance** - Order fulfillment tracking
- **TaxSystemHealth** - Tax compliance validation
- **VendorTracker** - Parts at vendor monitoring
- **WipUpdate** - WIP tracker updates

## Features

- **On-Demand Execution**: Manually trigger any script with a button click
- **Automated Scheduling**: Configure schedules for automatic script execution (APScheduler)
- **Run History**: View detailed execution history with SessionLog output
- **Email Configuration**: Customize email recipients per script
- **Enable/Disable**: Toggle scripts on/off without deleting configuration
- **Real-Time Status**: Live status updates showing running/idle/error states
- **Error Logging**: Centralized error tracking with email notifications

## Quick Start

### 1. Install Dependencies

```bash
cd VariousInternalServices/WebInterface
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the `.env.example` to create your `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Flask
VIS_SECRET_KEY=your-random-secret-key

# Authentication
VIS_ADMIN_USERNAME=admin
VIS_ADMIN_PASSWORD=yourpassword
VIS_USER2_USERNAME=user2
VIS_USER2_PASSWORD=user2password

# These should already be in parent .env:
SMTP2GO_API_KEY=your_key
ADMIN_EMAIL=admin@example.com
```

### 3. Run the Application

**Development Mode:**
```bash
python app.py
```

**Production Mode:**
```bash
python prod_server.py
# Or on Windows:
start_server.bat
```

### 4. Access the Interface

Open your browser and navigate to:
- Local: `http://localhost:5001`
- Network: `http://[your-ip]:5001`

Login with the credentials from your `.env` file.

## Architecture

### Data Storage

All configuration and run history is stored in JSON files:

- **`data/script_config.json`** - Script configurations, schedules, recipients, status
- **`data/run_history.json`** - Execution history with full SessionLog output
- **`data/error_log.json`** - System/application errors

These files are created automatically on first run with default values.

### Background Scheduler

The application uses APScheduler to run scripts automatically:

- One job per script
- Configurable intervals (in minutes)
- Dynamic rescheduling without restart
- Jobs can be enabled/disabled individually

### Script Execution

Scripts are executed in separate threads:

- **Direct Import**: Scripts are imported as Python modules
- **SessionLog Capture**: Full SessionLog output is captured and stored
- **Concurrency Control**: Maximum 1 concurrent run per script
- **Thread-Safe**: All data operations use locks for thread safety

## Usage Guide

### Dashboard

The main dashboard shows 4 cards (one for each script):

- **Status Indicator**: Shows idle (blue), running (orange), or error (red)
- **Last Run**: Timestamp of last execution
- **Next Run**: Next scheduled execution time (if enabled)
- **Schedule**: Current interval configuration
- **Recipients**: Number of email recipients
- **Total Runs**: Total execution count

### Script Actions

**Run Now**: Manually trigger script execution
- Button is disabled while script is running
- Toast notification shows execution status
- Dashboard auto-refreshes when complete

**Enable/Disable**: Toggle automatic scheduling
- Disabling removes the scheduled job
- Enabling creates a new scheduled job
- Changes take effect immediately

**History**: View detailed run history
- Shows all past executions
- Full SessionLog output available
- Filter by status (success/error)

### Script Configuration

Each script can be configured with:

- **Schedule Interval**: Minutes between automatic runs
  - Daily: 1440 minutes
  - Weekly: 10080 minutes
  - Custom: any value 1-10080

- **Email Recipients**: List of email addresses for summary reports
  - Scripts send their own emails (not duplicated by web interface)
  - System errors send separate notifications to admin

- **Custom Parameters**: Script-specific settings
  - Query names
  - Custom headers
  - Sheet ranges
  - Other script-specific options

## API Endpoints

### Authentication
- `POST /login` - User login
- `GET /logout` - User logout

### Script Management
- `GET /api/scripts` - Get all script configurations
- `GET /api/scripts/<name>` - Get specific script config
- `POST /api/scripts/<name>/execute` - Trigger manual execution
- `POST /api/scripts/<name>/toggle` - Enable/disable script
- `PUT /api/scripts/<name>/schedule` - Update schedule interval
- `PUT /api/scripts/<name>/recipients` - Update email recipients

### Run History
- `GET /api/runs` - Get all run history
- `GET /api/runs/<id>` - Get specific run details
- `GET /api/scripts/<name>/runs` - Get runs for specific script

### Scheduler
- `GET /api/scheduler/status` - Get scheduler status for all scripts
- `POST /api/scheduler/reschedule/<name>` - Reschedule specific script

### Error Logging
- `GET /api/errors` - Get error logs
- `GET /api/errors/<id>` - Get specific error
- `POST /api/errors/<id>/resolve` - Mark error as resolved
- `POST /api/errors/clear` - Clear all errors

## Deployment

### Development

```bash
python app.py
```

Runs Flask development server on `http://0.0.0.0:5001`

### Production

```bash
python prod_server.py
```

Runs Waitress WSGI server with 6 threads on `http://0.0.0.0:5001`

### Windows Service (Optional)

Install as a Windows service using NSSM:

```cmd
nssm install VariousInternalServices "C:\path\to\venv\Scripts\python.exe" "C:\path\to\WebInterface\prod_server.py"
nssm set VariousInternalServices AppDirectory "C:\path\to\WebInterface"
nssm set VariousInternalServices DisplayName "Various Internal Services Manager"
nssm set VariousInternalServices Description "Web interface for managing automation scripts"
nssm start VariousInternalServices
```

## Security

- **Authentication**: Session-based with username/password
- **Credentials**: Stored in environment variables (never hardcoded)
- **Network**: Designed for internal network deployment only
- **Port**: 5001 (separate from RetailInventoryManager on 5000)
- **Data Integrity**: Thread-safe atomic writes for all JSON files

## Troubleshooting

### Scripts Not Importing

If scripts fail to import:
1. Check that parent directory is in Python path (handled by executor.py)
2. Verify all dependencies are installed
3. Check that script files exist in VariousInternalServices/ directory

### Scheduler Not Running

If scheduled jobs don't execute:
1. Check that script is enabled (toggle switch)
2. Verify schedule_value is set correctly
3. Check APScheduler logs in console output
4. Ensure server wasn't restarted (jobs reschedule on startup)

### JSON File Errors

If JSON files become corrupted:
1. Stop the server
2. Delete the corrupted file from `data/` directory
3. Restart server (file will be recreated with defaults)

### Email Notifications Not Sending

If emails aren't being sent:
1. Verify SMTP2GO_API_KEY in .env
2. Check ADMIN_EMAIL and SENDER_EMAIL are set
3. Scripts send their own emails - web interface only sends system error emails
4. Check error logs via API or in data/error_log.json

## File Structure

```
WebInterface/
├── app.py                  # Flask application & routes
├── config.py               # Configuration & script metadata
├── data.py                 # Data layer (JSON operations)
├── executor.py             # Script execution orchestration
├── prod_server.py          # Production server
├── start_server.bat        # Windows startup script
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── data/                   # JSON data files (auto-created)
│   ├── script_config.json
│   ├── run_history.json
│   └── error_log.json
├── templates/              # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   └── script_detail.html
└── static/                 # Static assets
    └── js/
        └── app.js          # Frontend JavaScript
```

## Future Enhancements

Potential improvements:
- Script detail page with run history table
- Real-time log streaming via WebSockets
- Cron expression support for complex schedules
- Role-based access control
- Slack/Teams notifications
- Dashboard widgets with charts
- Export run history to CSV

## Support

For issues or questions, refer to the main repository README or contact the system administrator.
