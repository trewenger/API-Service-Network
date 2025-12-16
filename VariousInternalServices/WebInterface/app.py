"""
Flask Application for VariousInternalServices Web Interface

Provides web UI and API for managing 4 automation scripts with scheduling.
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import logging

from config import Config
from data import ScriptConfigData, RunHistoryData, ErrorLogger
from executor import ScriptExecutor

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize data layer and executor
config_data = ScriptConfigData()
history_data = RunHistoryData()
error_logger = ErrorLogger()
executor = ScriptExecutor()

# Initialize APScheduler
scheduler = BackgroundScheduler()
script_jobs = {}  # {script_name: job}


# ========================= Authentication =========================

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username in Config.USERS and Config.USERS[username] == password:
            session['username'] = username
            logger.info(f"User {username} logged in")
            return redirect(url_for('dashboard'))
        else:
            logger.warning(f"Failed login attempt for user {username}")
            return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout user"""
    username = session.get('username')
    session.pop('username', None)
    logger.info(f"User {username} logged out")
    return redirect(url_for('login'))


# ========================= Page Routes =========================

@app.route('/')
@login_required
def dashboard():
    """Main dashboard with 4 script cards"""
    scripts = config_data.get_all_scripts()

    # Enhance with metadata
    for script_name in scripts:
        if script_name in Config.AVAILABLE_SCRIPTS:
            scripts[script_name].update({
                'display_name': Config.AVAILABLE_SCRIPTS[script_name]['display_name'],
                'description': Config.AVAILABLE_SCRIPTS[script_name]['description'],
                'icon': Config.AVAILABLE_SCRIPTS[script_name]['icon']
            })
        # Check if currently running
        scripts[script_name]['is_running'] = executor.is_script_running(script_name)

    return render_template('dashboard.html', scripts=scripts, username=session.get('username'))


@app.route('/script/<script_name>')
@login_required
def script_detail(script_name):
    """Script detail page with run history"""
    if script_name not in Config.AVAILABLE_SCRIPTS:
        return "Script not found", 404

    script_config = config_data.get_script_config(script_name)
    script_meta = Config.AVAILABLE_SCRIPTS[script_name]
    run_history = history_data.get_run_history(script_name=script_name, limit=50)

    return render_template(
        'script_detail.html',
        script_name=script_name,
        script_config=script_config,
        script_meta=script_meta,
        run_history=run_history,
        username=session.get('username')
    )


# ========================= API Routes - Script Management =========================

@app.route('/api/scripts', methods=['GET'])
@login_required
def api_get_all_scripts():
    """Get all script configurations"""
    scripts = config_data.get_all_scripts()

    # Enhance with runtime info
    for script_name in scripts:
        scripts[script_name]['is_running'] = executor.is_script_running(script_name)
        if script_name in Config.AVAILABLE_SCRIPTS:
            scripts[script_name]['display_name'] = Config.AVAILABLE_SCRIPTS[script_name]['display_name']
            scripts[script_name]['icon'] = Config.AVAILABLE_SCRIPTS[script_name]['icon']

    return jsonify(scripts)


@app.route('/api/scripts/<script_name>', methods=['GET'])
@login_required
def api_get_script(script_name):
    """Get specific script configuration"""
    script_config = config_data.get_script_config(script_name)
    if not script_config:
        return jsonify({'error': 'Script not found'}), 404

    script_config['is_running'] = executor.is_script_running(script_name)
    if script_name in Config.AVAILABLE_SCRIPTS:
        script_config['display_name'] = Config.AVAILABLE_SCRIPTS[script_name]['display_name']

    return jsonify(script_config)


@app.route('/api/scripts/<script_name>/execute', methods=['POST'])
@login_required
def api_execute_script(script_name):
    """Trigger manual script execution"""
    result = executor.execute_script(
        script_name=script_name,
        trigger_type='manual',
        triggered_by=session.get('username', 'unknown')
    )

    if result['success']:
        logger.info(f"Manual execution of {script_name} started by {session.get('username')}")
        return jsonify(result), 200
    else:
        logger.error(f"Failed to start {script_name}: {result.get('error')}")
        return jsonify(result), 400


@app.route('/api/scripts/<script_name>/toggle', methods=['POST'])
@login_required
def api_toggle_script(script_name):
    """Enable or disable a script"""
    data = request.get_json()
    enabled = data.get('enabled', False)

    try:
        config_data.toggle_script(script_name, enabled)

        # Reschedule (add or remove job)
        reschedule_script(script_name)

        logger.info(f"Script {script_name} {'enabled' if enabled else 'disabled'} by {session.get('username')}")
        return jsonify({'success': True, 'enabled': enabled})
    except Exception as e:
        logger.error(f"Error toggling {script_name}: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/scripts/<script_name>/schedule', methods=['PUT'])
@login_required
def api_update_schedule(script_name):
    """Update script schedule interval"""
    data = request.get_json()
    schedule_value = data.get('schedule_value')

    if not schedule_value or not isinstance(schedule_value, int) or schedule_value < 1:
        return jsonify({'error': 'Invalid schedule_value'}), 400

    try:
        config_data.update_schedule(script_name, schedule_value)

        # Reschedule job with new interval
        reschedule_script(script_name)

        logger.info(f"Script {script_name} schedule updated to {schedule_value} minutes by {session.get('username')}")
        return jsonify({'success': True, 'schedule_value': schedule_value})
    except Exception as e:
        logger.error(f"Error updating schedule for {script_name}: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/scripts/<script_name>/recipients', methods=['PUT'])
@login_required
def api_update_recipients(script_name):
    """Update email recipients list"""
    data = request.get_json()
    recipients = data.get('recipients', [])

    if not isinstance(recipients, list):
        return jsonify({'error': 'recipients must be a list'}), 400

    try:
        config_data.update_email_recipients(script_name, recipients)
        logger.info(f"Script {script_name} recipients updated by {session.get('username')}")
        return jsonify({'success': True, 'recipients': recipients})
    except Exception as e:
        logger.error(f"Error updating recipients for {script_name}: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/scripts/<script_name>/config', methods=['PUT'])
@login_required
def api_update_config(script_name):
    """Update script configuration"""
    data = request.get_json()

    try:
        config_data.update_script_config(script_name, data)
        logger.info(f"Script {script_name} config updated by {session.get('username')}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating config for {script_name}: {e}")
        return jsonify({'error': str(e)}), 400


# ========================= API Routes - Run History =========================

@app.route('/api/runs', methods=['GET'])
@login_required
def api_get_all_runs():
    """Get all run history with optional filters"""
    limit = request.args.get('limit', 50, type=int)
    status_filter = request.args.get('status')

    runs = history_data.get_run_history(limit=limit, status_filter=status_filter)
    return jsonify(runs)


@app.route('/api/runs/<int:run_id>', methods=['GET'])
@login_required
def api_get_run(run_id):
    """Get specific run details"""
    run = history_data.get_run_by_id(run_id)
    if not run:
        return jsonify({'error': 'Run not found'}), 404

    return jsonify(run)


@app.route('/api/runs/<int:run_id>', methods=['DELETE'])
@login_required
def api_delete_run(run_id):
    """Delete a specific run"""
    try:
        success = history_data.delete_run(run_id)
        if success:
            return jsonify({'success': True, 'message': f'Run {run_id} deleted'})
        else:
            return jsonify({'success': False, 'error': 'Run not found'}), 404
    except Exception as e:
        error_logger.log_error(
            error_type='api_error',
            message=f'Failed to delete run {run_id}',
            source='app:api_delete_run',
            user=session.get('username', 'unknown'),
            details={'run_id': run_id, 'error': str(e)}
        )
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/scripts/<script_name>/runs', methods=['GET'])
@login_required
def api_get_script_runs(script_name):
    """Get run history for specific script"""
    limit = request.args.get('limit', 50, type=int)
    status_filter = request.args.get('status')

    runs = history_data.get_run_history(
        script_name=script_name,
        limit=limit,
        status_filter=status_filter
    )
    return jsonify(runs)


@app.route('/api/runs/cleanup', methods=['DELETE'])
@login_required
def api_cleanup_runs():
    """Cleanup old run history"""
    try:
        history_data.cleanup_old_runs()
        logger.info(f"Run history cleaned up by {session.get('username')}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error cleaning up run history: {e}")
        return jsonify({'error': str(e)}), 400


# ========================= API Routes - Scheduler Management =========================

@app.route('/api/scheduler/status', methods=['GET'])
@login_required
def api_scheduler_status():
    """Get scheduler status for all scripts"""
    status = {}

    for script_name in Config.AVAILABLE_SCRIPTS.keys():
        script_config = config_data.get_script_config(script_name)
        if script_config:
            status[script_name] = {
                'enabled': script_config.get('enabled', False),
                'schedule_value': script_config.get('schedule_value'),
                'last_run': script_config.get('last_run'),
                'next_run': script_config.get('next_run'),
                'status': script_config.get('status'),
                'is_running': executor.is_script_running(script_name)
            }

    status['scheduler_running'] = scheduler.running

    return jsonify(status)


@app.route('/api/scheduler/reschedule/<script_name>', methods=['POST'])
@login_required
def api_reschedule_script(script_name):
    """Reschedule a specific script"""
    try:
        reschedule_script(script_name)
        logger.info(f"Script {script_name} rescheduled by {session.get('username')}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error rescheduling {script_name}: {e}")
        return jsonify({'error': str(e)}), 400


# ========================= API Routes - Error Logging =========================

@app.route('/api/errors', methods=['GET'])
@login_required
def api_get_errors():
    """Get error logs"""
    limit = request.args.get('limit', 50, type=int)
    unresolved_only = request.args.get('unresolved_only', 'false').lower() == 'true'

    errors = error_logger.get_errors(limit=limit, unresolved_only=unresolved_only)
    return jsonify(errors)


@app.route('/api/errors/<int:error_id>', methods=['GET'])
@login_required
def api_get_error(error_id):
    """Get specific error"""
    error = error_logger.get_error_by_id(error_id)
    if not error:
        return jsonify({'error': 'Error not found'}), 404

    return jsonify(error)


@app.route('/api/errors/<int:error_id>/resolve', methods=['POST'])
@login_required
def api_resolve_error(error_id):
    """Mark error as resolved"""
    try:
        error_logger.mark_resolved(error_id)
        logger.info(f"Error {error_id} resolved by {session.get('username')}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/errors/clear', methods=['POST'])
@login_required
def api_clear_errors():
    """Clear all errors"""
    try:
        error_logger.clear_all_errors()
        logger.info(f"All errors cleared by {session.get('username')}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/errors/stats', methods=['GET'])
@login_required
def api_error_stats():
    """Get error statistics"""
    stats = error_logger.get_stats()
    return jsonify(stats)


# ========================= Scheduler Functions =========================

def reschedule_script(script_name: str):
    """
    Schedule or reschedule a script based on its configuration.

    Args:
        script_name: Name of the script to schedule
    """
    script_config = config_data.get_script_config(script_name)

    if not script_config or not script_config.get('enabled'):
        # Remove job if it exists
        job_id = f'script_{script_name}'
        if job_id in [job.id for job in scheduler.get_jobs()]:
            scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled job for {script_name}")
        return

    # Get schedule interval
    schedule_value = script_config.get('schedule_value', 1440)  # Default daily

    # Remove existing job if present
    job_id = f'script_{script_name}'
    if job_id in [job.id for job in scheduler.get_jobs()]:
        scheduler.remove_job(job_id)

    # Add new job
    job = scheduler.add_job(
        func=lambda: executor.execute_script(script_name, 'scheduled', 'system'),
        trigger='interval',
        minutes=schedule_value,
        id=job_id,
        name=f'Execute {script_name}',
        replace_existing=True
    )

    # Calculate next run time
    next_run = datetime.now() + timedelta(minutes=schedule_value)
    config_data.update_next_run(script_name, next_run.isoformat())

    logger.info(f"Scheduled {script_name} with {schedule_value} minute interval (next run: {next_run})")


def initialize_scheduler():
    """Initialize scheduler with all enabled scripts"""
    logger.info("Initializing scheduler...")

    for script_name in Config.AVAILABLE_SCRIPTS.keys():
        reschedule_script(script_name)

    scheduler.start()
    logger.info("Scheduler started")


# ========================= Application Startup =========================

if __name__ == '__main__':
    # Initialize scheduler on startup
    initialize_scheduler()

    # Run Flask development server
    logger.info("Starting VariousInternalServices Web Interface on http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)
