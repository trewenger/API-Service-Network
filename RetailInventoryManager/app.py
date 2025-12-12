from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging

from config import Config
from data import InventoryData, ErrorLogger
from sync import FishbowlSync

app = Flask(__name__)
app.config.from_object(Config)

# Initialize
data = InventoryData()
error_logger = ErrorLogger()
sync_manager = FishbowlSync()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ------------------------------ background scheduler --------------------------------- #
scheduler = BackgroundScheduler()
SYNC_JOB = None
SALES_JOB = None

def remove_job(job_name:str) -> bool:
    """ removes the job from the default store. """
    job_removed = False
    global SYNC_JOB
    global SALES_JOB
    
    if job_name == "fishbowl_sales":
            if scheduler.get_job('fishbowl_sales') is not None:
                    # attempt both methods to remove the job if not init
                    try:
                        scheduler.remove_job('fishbowl_sales', 'default')
                        job_removed = True
                    except:
                        try:
                            SALES_JOB.remove()
                            job_removed = True
                        except Exception as e:
                            print(f"\n WARNING UNABLE TO REMOVE THE SALES JOB: {e} \n ")
                            error_logger.log_error(
                                error_type='scheduler_error',
                                message=f"Failed to remove sales job: {str(e)}",
                                source='app.py:remove_job',
                                details={'job_name': 'fishbowl_sales', 'error': str(e)}
                            )
            else:
                job_removed = True

    else:
            if scheduler.get_job('fishbowl_sync') is not None:
                # attempt both methods to remove the job if not init
                try:
                    scheduler.remove_job('fishbowl_sync', 'default')
                    job_removed = True
                except:
                    try:
                        SYNC_JOB.remove()
                        job_removed = True
                    except Exception as e:
                        print(f"\n WARNING UNABLE TO REMOVE THE PREVIOUS SYNC JOB: {e} \n ")
                        error_logger.log_error(
                            error_type='scheduler_error',
                            message=f"Failed to remove sync job: {str(e)}",
                            source='app.py:remove_job',
                            details={'job_name': 'fishbowl_sync', 'error': str(e)}
                        )
            else:
                job_removed = True

    return job_removed

def get_sync_interval():
    """Dynamically get sync interval from config"""
    config = data.get_config()
    return config.get('sync_interval_minutes', Config.SYNC_INTERVAL_MINUTES)

def get_sales_interval():
    """Dynamically get sales check interval from config"""
    config = data.get_config()
    return config.get('sales_interval_minutes', Config.SALES_INTERVAL_MINUTES)

def reschedule_sync():
    """Reschedule the sync job with new interval"""

    # attempt both methods to remove the job if not init
    global SYNC_JOB
    job_removed = remove_job("fishbowl_sync")
    
    # create a new job in the scheduler. Allows init to create the first job.
    if not SYNC_JOB or job_removed is True:
        interval = get_sync_interval()
        job = scheduler.add_job(
            func=sync_manager.determine_sync,
            trigger='interval',
            minutes=interval,
            id='fishbowl_sync',
            name='Sync Fishbowl inventory',
            replace_existing=True
        )
        logger.info(f"Sync job scheduled with {interval} minute interval")
        # return the new job only if the previous was removed. 
        scheduler.print_jobs()
        print('\n')
        return job
    else:
        # return the existing job.
        print(" \n WARNING UNABLE TO REMOVE THE PREVIOUS SYNC JOB SCHEDULE \n ")
        return SYNC_JOB

def reschedule_sales():
    """Reschedule the sync job with new interval"""

    # attempt both methods to remove the job if not init
    global SALES_JOB
    job_removed = remove_job("fishbowl_sales")
    
    # create a new job in the scheduler. Allows init to create the first job.
    if not SALES_JOB or job_removed is True:
        interval = get_sales_interval()
        job = scheduler.add_job(
            func=sync_manager.run_sales_check,
            trigger='interval',
            minutes=interval,
            id='fishbowl_sales',
            name='Sync Fishbowl Sales',
            replace_existing=True
        )
        logger.info(f"Sales check job scheduled with {interval} minute interval")
        # return the new job only if the previous was removed. 
        return job
    else:
        # return the existing job.
        print(" \n WARNING UNABLE TO REMOVE THE PREVIOUS SALES JOB SCHEDULE \n ")
        return SALES_JOB

# Initial schedule
config = data.get_config()
mode = config["inventory_method"]
# only enabling the sales job on start if method is manual.
if mode == 'manual':
    SALES_JOB = reschedule_sales()
SYNC_JOB = reschedule_sync()
scheduler.start()

# ---------------------------------- Routes ------------------------------------------- #

# Auth decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        elif username == Config.RYAN_USERNAME and password == Config.RYAN_PW:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        elif username == Config.JAKE_USERNAME and password == Config.JAKE_PW:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    skus = data.get_all_skus()
    config = data.get_config()

    # Calculate stats
    total_skus = len(skus)
    sold_out = sum(1 for s in skus.values() if s['available_qty'] <= 0)
    low_stock = sum(1 for s in skus.values() if 0 < s['available_qty'] <= 10)

    return render_template('index.html',
                         skus=skus,
                         config=config,
                         stats={
                             'total': total_skus,
                             'sold_out': sold_out,
                             'low_stock': low_stock
                         })

@app.route('/how-to')
@login_required
def how_to():
    return render_template('how_to.html')

#---------------------------------- Config R/W -----------------------------------------#
# get the config
@app.route('/api/config', methods=['GET'])
@login_required
def api_get_config():
    config = data.get_config()
    return jsonify(config)

# update the config
@app.route('/api/config', methods=['PUT'])
@login_required
def api_update_config():
    try:
        req_data = request.get_json()
        
        updates = {}
        requires_restart = False
        
        if 'inventory_method' in req_data:
            method = req_data['inventory_method']
            if method not in ['manual', 'automated']:
                return jsonify({'error': 'Invalid inventory method'}), 400
            updates['inventory_method'] = method
            logger.info(f"Inventory method changed to: {method} by {session.get('username')}")
        
        if 'sync_interval_minutes' in req_data:
            interval = int(req_data['sync_interval_minutes'])
            if interval < 1 or interval > 180:
                return jsonify({'error': 'Interval must be between 1 and 180 minutes'}), 400
            updates['sync_interval_minutes'] = interval
            requires_restart = True
            logger.info(f"Sync interval changed to: {interval} minutes by {session.get('username')}")

        if 'sales_interval_minutes' in req_data:
            interval = int(req_data['sales_interval_minutes'])
            if interval < 1 or interval > 180:
                return jsonify({'error': 'Interval must be between 1 and 180 minutes'}), 400
            updates['sales_interval_minutes'] = interval
            requires_restart = True
            logger.info(f"Sales interval changed to: {interval} minutes by {session.get('username')}")
        
        data.update_config(updates)
        
        return jsonify({
            'success': True,
            'requires_restart': requires_restart
        })
    
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        error_logger.log_error(
            error_type='api_error',
            message=f"Failed to update config: {str(e)}",
            source='app.py:api_update_config',
            details={'updates': req_data, 'error': str(e)},
            user=session.get('username', 'unknown')
        )
        return jsonify({'error': str(e)}), 500


# Endpoint to reschedule sales without restart (if sales interval changed)
@app.route('/api/reschedule-sales', methods=['POST'])
@login_required
def api_reschedule_sales():
    try:
        reschedule_sales()
        interval = get_sales_interval()
        return jsonify({
            'success': True,
            'message': f'Sales check rescheduled to run every {interval} minutes'
        })
    except Exception as e:
        logger.error(f"Error rescheduling sales check: {e}")
        error_logger.log_error(
            error_type='scheduler_error',
            message=f"Failed to reschedule sales check: {str(e)}",
            source='app.py:api_reschedule_sales',
            details={'error': str(e)},
            user=session.get('username', 'unknown')
        )
        return jsonify({'error': str(e)}), 500

# Endpoint to reschedule sync without restart (if sync interval changed)
@app.route('/api/reschedule-sync', methods=['POST'])
@login_required
def api_reschedule_sync():
    try:
        reschedule_sync()
        interval = get_sync_interval()
        return jsonify({
            'success': True,
            'message': f'Sync rescheduled to run every {interval} minutes'
        })
    except Exception as e:
        logger.error(f"Error rescheduling sync: {e}")
        error_logger.log_error(
            error_type='scheduler_error',
            message=f"Failed to reschedule sync: {str(e)}",
            source='app.py:api_reschedule_sync',
            details={'error': str(e)},
            user=session.get('username', 'unknown')
        )
        return jsonify({'error': str(e)}), 500

# Endpoint to remove scheduled syncs
@app.route('/api/remove-job', methods=['POST'])
@login_required
def api_remove_job():
    try:
        result = remove_job('fishbowl_sales')

        return jsonify({
            'success': True,
            'message': f'Job removed from scheduler'
        })
    except Exception as e:
        logger.error(f"Error removing job: {e}")
        error_logger.log_error(
            error_type='scheduler_error',
            message=f"Failed to remove job: {str(e)}",
            source='app.py:api_remove_job',
            details={'error': str(e)},
            user=session.get('username', 'unknown')
        )
        return jsonify({'error': str(e)}), 500

# API Routes
@app.route('/api/skus', methods=['GET'])
@login_required
def api_get_skus():
    skus = data.get_all_skus()
    return jsonify(skus)

@app.route('/api/skus', methods=['POST'])
@login_required
def api_add_sku():
    try:
        req_data = request.get_json()
        sku = req_data.get('sku', '').strip().upper()
        product_name = req_data.get('product_name', '').strip()
        available_qty = int(req_data.get('available_qty', 0))
        notes = req_data.get('notes', '').strip()
        sn_flag = req_data.get('sn_flag', False)
        part_num = req_data.get('part_num', '').strip().upper()
        
        if not sku or not product_name:
            return jsonify({'error': 'SKU and product name required'}), 400
        
        # Check if SKU already exists
        if data.get_sku(sku):
            return jsonify({'error': 'SKU already exists'}), 400
        
        sku_data = data.add_sku(
            sku=sku,
            product_name=product_name,
            available_qty=available_qty,
            modified_by=session.get('username', 'unknown'),
            notes=notes,
            sn_flag=sn_flag,
            part_num=part_num
        )
        
        return jsonify({'success': True, 'data': sku_data})

    except Exception as e:
        logger.error(f"Error adding SKU: {e}")
        error_logger.log_error(
            error_type='api_error',
            message=f"Failed to add SKU: {str(e)}",
            source='app.py:api_add_sku',
            details={'sku': req_data.get('sku'), 'error': str(e)},
            user=session.get('username', 'unknown')
        )
        return jsonify({'error': str(e)}), 500

@app.route('/api/sku-check', methods=['POST'])
@login_required
def api_sku_check():
    try:
        req_data = request.get_json()
        sku = req_data.get('sku', '').strip().upper()
        
        if not sku:
            return jsonify({'error': 'SKU and product name required'}), 400
        
        result = sync_manager.get_sku_info(sku)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error validating new SKU: {e}")
        error_logger.log_error(
            error_type='api_error',
            message=f"Failed to validate SKU: {str(e)}",
            source='app.py:api_sku_check',
            details={'sku': req_data.get('sku'), 'error': str(e)},
            user=session.get('username', 'unknown')
        )
        return jsonify({'error': str(e)}), 500

@app.route('/api/skus/<sku>', methods=['PUT'])
@login_required
def api_update_sku(sku):
    try:
        req_data = request.get_json()
        
        updates = {}
        if 'product_name' in req_data:
            updates['product_name'] = req_data['product_name'].strip()
        if 'available_qty' in req_data:
            updates['available_qty'] = int(req_data['available_qty'])
        if 'notes' in req_data:
            updates['notes'] = req_data['notes'].strip()
        
        sku_data = data.update_sku(
            sku=sku,
            updates=updates,
            modified_by=session.get('username', 'unknown')
        )
        
        if not sku_data:
            return jsonify({'error': 'SKU not found'}), 404
        
        return jsonify({'success': True, 'data': sku_data})

    except Exception as e:
        logger.error(f"Error updating SKU {sku}: {e}")
        error_logger.log_error(
            error_type='api_error',
            message=f"Failed to update SKU {sku}: {str(e)}",
            source='app.py:api_update_sku',
            details={'sku': sku, 'updates': req_data, 'error': str(e)},
            user=session.get('username', 'unknown')
        )
        return jsonify({'error': str(e)}), 500

@app.route('/api/skus/<sku>', methods=['DELETE'])
@login_required
def api_delete_sku(sku):
    try:
        success = data.delete_sku(sku, modified_by=session.get('username', 'unknown'))
        if not success:
            return jsonify({'error': 'SKU not found'}), 404
        
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error deleting SKU {sku}: {e}")
        error_logger.log_error(
            error_type='api_error',
            message=f"Failed to delete SKU {sku}: {str(e)}",
            source='app.py:api_delete_sku',
            details={'sku': sku, 'error': str(e)},
            user=session.get('username', 'unknown')
        )
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync', methods=['POST'])
@login_required
def api_sync():
    try:
        result = sync_manager.determine_sync()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        error_logger.log_error(
            error_type='api_error',
            message=f"Failed to trigger sync: {str(e)}",
            source='app.py:api_sync',
            details={'error': str(e)},
            user=session.get('username', 'unknown')
        )
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/check', methods=['POST'])
@login_required
def api_check():
    try:
        result = sync_manager.run_sales_check()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error triggering sales check: {e}")
        error_logger.log_error(
            error_type='api_error',
            message=f"Failed to trigger sales check: {str(e)}",
            source='app.py:api_check',
            details={'error': str(e)},
            user=session.get('username', 'unknown')
        )
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
@login_required
def api_status():
    config = data.get_config()
    return jsonify({
        'last_sync_run': config.get('last_sync_run'),
        'sync_interval_minutes': config.get('sync_interval_minutes'),
        'scheduler_running': scheduler.running
    })



# Error log endpoints
@app.route('/api/errors', methods=['GET'])
@login_required
def api_get_errors():
    """Get error logs with optional filtering"""
    try:
        limit = request.args.get('limit', 50, type=int)
        unresolved_only = request.args.get('unresolved_only', 'false').lower() == 'true'

        errors = error_logger.get_errors(limit=limit, unresolved_only=unresolved_only)
        return jsonify({
            'success': True,
            'errors': errors
        })
    except Exception as e:
        logger.error(f"Error fetching error logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/errors/stats', methods=['GET'])
@login_required
def api_get_error_stats():
    """Get error statistics"""
    try:
        stats = error_logger.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error fetching error stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/errors/<int:error_id>', methods=['GET'])
@login_required
def api_get_error(error_id):
    """Get a specific error by ID"""
    try:
        error = error_logger.get_error_by_id(error_id)
        if error:
            return jsonify({
                'success': True,
                'error': error
            })
        else:
            return jsonify({'error': 'Error not found'}), 404
    except Exception as e:
        logger.error(f"Error fetching error {error_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/errors/<int:error_id>/resolve', methods=['POST'])
@login_required
def api_resolve_error(error_id):
    """Mark an error as resolved"""
    try:
        success = error_logger.mark_resolved(error_id, resolved_by=session.get('username', 'system'))
        if success:
            return jsonify({
                'success': True,
                'message': f'Error {error_id} marked as resolved'
            })
        else:
            return jsonify({'error': 'Error not found'}), 404
    except Exception as e:
        logger.error(f"Error resolving error {error_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/errors/clear', methods=['POST'])
@login_required
def api_clear_errors():
    """Clear all errors from the log"""
    try:
        count = error_logger.clear_all_errors()
        logger.info(f"All error logs cleared by {session.get('username')}")
        return jsonify({
            'success': True,
            'message': f'Cleared {count} errors',
            'count': count
        })
    except Exception as e:
        logger.error(f"Error clearing error logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/errors', methods=['POST'])
@login_required
def api_log_error():
    """Manually log an error (for testing or manual error reporting)"""
    try:
        req_data = request.get_json()

        error_type = req_data.get('error_type', 'manual_error')
        message = req_data.get('message')
        source = req_data.get('source', 'webapp')
        details = req_data.get('details', {})

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        error_entry = error_logger.log_error(
            error_type=error_type,
            message=message,
            source=source,
            details=details,
            user=session.get('username', 'system')
        )

        return jsonify({
            'success': True,
            'error': error_entry
        })
    except Exception as e:
        logger.error(f"Error logging error: {e}")
        return jsonify({'error': str(e)}), 500
    


# Audit log endpoints
@app.route('/api/logs', methods=['GET'])
@login_required
def api_get_logs():
    """Get audit logs with optional filtering"""
    try:
        limit = request.args.get('limit', 50, type=int)

        logs = data.get_audit_log(limit=limit)
        return jsonify({
            'success': True,
            'logs': logs
        })
    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs/stats', methods=['GET'])
@login_required
def api_get_log_stats():
    """Get log statistics"""
    try:
        stats = error_logger.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error fetching audit log stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs/<int:log_id>', methods=['GET'])
@login_required
def api_get_log(log_id):
    """Get a specific audit log entry by ID"""
    try:
        log = data.get_log_by_id(log_id)
        if log:
            return jsonify({
                'success': True,
                'error': log
            })
        else:
            return jsonify({'error': 'Audit Log entry not found'}), 404
    except Exception as e:
        logger.error(f"Error fetching audit log id {log_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs/clear', methods=['POST'])
@login_required
def api_clear_logs():
    """Clear all logs from the audit log"""
    try:
        count = data.clear_all_logs()
        logger.info(f"All audit logs cleared by {session.get('username')}")
        return jsonify({
            'success': True,
            'message': f'Cleared {count} audit log entries',
            'count': count
        })
    except Exception as e:
        logger.error(f"Error clearing audit logs: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    