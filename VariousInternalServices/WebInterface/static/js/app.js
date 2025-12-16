/**
 * Frontend JavaScript for VariousInternalServices Web Interface
 * Handles script execution, configuration updates, and UI interactions
 */

// ========================= Card Collapse/Expand =========================

function toggleCard(scriptName) {
    const detailsDiv = document.getElementById(`details-${scriptName}`);
    const chevron = document.getElementById(`chevron-${scriptName}`);

    if (detailsDiv.classList.contains('hidden')) {
        // Expand
        detailsDiv.classList.remove('hidden');
        chevron.classList.add('rotate-180');

        // Load error log and run history when card is expanded
        refreshScriptErrors(scriptName);
        refreshRunHistory(scriptName);
    } else {
        // Collapse
        detailsDiv.classList.add('hidden');
        chevron.classList.remove('rotate-180');
    }
}

function toggleScheduleConfig(scriptName) {
    const configDiv = document.getElementById(`schedule-config-${scriptName}`);
    const chevron = document.getElementById(`schedule-chevron-${scriptName}`);

    if (configDiv.classList.contains('hidden')) {
        // Expand
        configDiv.classList.remove('hidden');
        chevron.classList.add('rotate-180');
    } else {
        // Collapse
        configDiv.classList.add('hidden');
        chevron.classList.remove('rotate-180');
    }
}

function toggleRecipientsConfig(scriptName) {
    const configDiv = document.getElementById(`recipients-config-${scriptName}`);
    const chevron = document.getElementById(`recipients-chevron-${scriptName}`);

    if (configDiv.classList.contains('hidden')) {
        // Expand
        configDiv.classList.remove('hidden');
        chevron.classList.add('rotate-180');
    } else {
        // Collapse
        configDiv.classList.add('hidden');
        chevron.classList.remove('rotate-180');
    }
}

// ========================= Toast Notifications =========================

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// ========================= Display Status Helpers =========================

// set the loading bar
function setRunningUI(scriptName) {
    const status = document.getElementById(`status-${scriptName}`);
    const button = document.querySelector(`button[onclick*="${scriptName}"]`);

    status.innerHTML = `
        <span class="flex items-center space-x-1 text-amber-600 text-sm font-semibold">
            <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Running</span>
        </span>
    `;

    button.disabled = true;
}

// clear the loading bar
function setCompletedUI(scriptName, status) {
    const statusEl = document.getElementById(`status-${scriptName}`);
    const button = document.querySelector(`button[onclick*="${scriptName}"]`);

    if (status === 'error') {
        statusEl.innerHTML = `<span class="text-red-600 text-sm font-semibold">● Error</span>`;
    } else {
        statusEl.innerHTML = `<span class="text-blue-600 text-sm font-semibold">● Enabled</span>`;
    }

    button.disabled = false;
}


// ========================= Script Execution =========================

async function executeScript(scriptName) {
    try {
        showToast(`Starting ${scriptName}...`, 'info');

        const response = await fetch(`/api/scripts/${scriptName}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();
        console.log(data)
        if (response.ok && data.success) {
            showToast(`${scriptName} execution started successfully!`, 'success');

            // start the loading bar
            setRunningUI(scriptName);
            // Start polling for status updates
            pollScriptStatus(scriptName);

            // Reload page after a short delay to show updated status
            //setTimeout(() => location.reload(), 1000);
        } else {
            showToast(`Error: ${data.error || 'Failed to start script'}`, 'error');
        }
    } catch (error) {
        console.error('Error executing script:', error);
        showToast('Network error - please try again', 'error');
    }
}

// ========================= Script Status Polling =========================

let pollInterval = null;

function pollScriptStatus(scriptName) {
    if (pollInterval) return; // prevent multiple pollers

    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/scripts/${scriptName}`);
            const data = await response.json();
            console.log("Polling!", data);

            if (!data.is_running) {
                clearInterval(pollInterval);
                pollInterval = null;

                setCompletedUI(scriptName, data.status);

                if (data.status === 'error') {
                    showToast(`${scriptName} completed with errors`, 'error');
                } else {
                    showToast(`${scriptName} completed successfully!`, 'success');
                }

                return; // STOP polling
            }
        } catch (error) {
            console.error('Error polling status:', error);
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }, 5000);
}


// ========================= Script Toggle (Enable/Disable) =========================

async function toggleScript(scriptName, enabled) {
    try {
        const response = await fetch(`/api/scripts/${scriptName}/toggle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(`${scriptName} ${enabled ? 'enabled' : 'disabled'} successfully`, 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showToast(`Error: ${data.error || 'Failed to toggle script'}`, 'error');
            // Revert toggle
            event.target.checked = !enabled;
        }
    } catch (error) {
        console.error('Error toggling script:', error);
        showToast('Network error - please try again', 'error');
        // Revert toggle
        event.target.checked = !enabled;
    }
}

// ========================= Email Notifications Toggle =========================

async function toggleEmailNotifications(scriptName, enabled) {
    if (enabled) {
        // Enabling: Fetch script config to get default recipients
        try {
            const configResponse = await fetch(`/api/scripts/${scriptName}`);
            const configData = await configResponse.json();

            // Use default recipients from script metadata
            // This will be set in config.py for each script
            const defaultRecipients = ['admin@example.com']; // Placeholder - user should update

            const response = await fetch(`/api/scripts/${scriptName}/recipients`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ recipients: defaultRecipients })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                showToast('Email notifications enabled. Please update recipients.', 'info');
                setTimeout(() => location.reload(), 1000);
            } else {
                showToast(`Error: ${data.error || 'Failed to enable notifications'}`, 'error');
                // Revert toggle
                event.target.checked = false;
            }
        } catch (error) {
            console.error('Error enabling email notifications:', error);
            showToast('Network error - please try again', 'error');
            // Revert toggle
            event.target.checked = false;
        }
    } else {
        // Disabling: Clear all recipients
        if (!confirm(`Disable email notifications for ${scriptName}? This will remove all recipients.`)) {
            // Revert toggle
            event.target.checked = true;
            return;
        }

        try {
            const response = await fetch(`/api/scripts/${scriptName}/recipients`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ recipients: [] })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                showToast('Email notifications disabled successfully', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                showToast(`Error: ${data.error || 'Failed to disable notifications'}`, 'error');
                // Revert toggle
                event.target.checked = true;
            }
        } catch (error) {
            console.error('Error disabling email notifications:', error);
            showToast('Network error - please try again', 'error');
            // Revert toggle
            event.target.checked = true;
        }
    }
}

// ========================= Schedule Update =========================

function saveSchedule(scriptName) {
    const input = document.getElementById(`schedule-${scriptName}`);
    const scheduleValue = parseInt(input.value);

    if (!scheduleValue || scheduleValue < 1 || scheduleValue > 10080) {
        showToast('Please enter a valid schedule (1-10080 minutes)', 'error');
        return;
    }

    updateSchedule(scriptName, scheduleValue);
}

async function updateSchedule(scriptName, scheduleValue) {
    try {
        const response = await fetch(`/api/scripts/${scriptName}/schedule`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ schedule_value: parseInt(scheduleValue) })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(`Schedule updated to ${scheduleValue} minutes`, 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showToast(`Error: ${data.error || 'Failed to update schedule'}`, 'error');
        }
    } catch (error) {
        console.error('Error updating schedule:', error);
        showToast('Network error - please try again', 'error');
    }
}

// ========================= Email Recipients Update =========================

function addRecipient(scriptName) {
    const container = document.getElementById(`recipients-${scriptName}`);

    const recipientDiv = document.createElement('div');
    recipientDiv.className = 'flex items-center space-x-2';
    recipientDiv.innerHTML = `
        <input
            type="email"
            placeholder="email@example.com"
            class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            onclick="event.stopPropagation()"
        >
        <button
            onclick="removeRecipient(this); event.stopPropagation();"
            class="bg-red-500 hover:bg-red-600 text-white px-3 py-2 rounded-lg transition"
            title="Remove"
        >
            ✕
        </button>
    `;

    container.appendChild(recipientDiv);
}

function removeRecipient(button) {
    const recipientDiv = button.parentElement;
    recipientDiv.remove();
}

function saveRecipients(scriptName) {
    const container = document.getElementById(`recipients-${scriptName}`);
    const emailInputs = container.querySelectorAll('input[type="email"]');

    const recipients = [];
    let hasInvalid = false;

    emailInputs.forEach(input => {
        const email = input.value.trim();
        if (email) {
            // Basic email validation
            if (email.includes('@') && email.includes('.')) {
                recipients.push(email);
            } else {
                hasInvalid = true;
                input.classList.add('border-red-500');
            }
        }
    });

    if (hasInvalid) {
        showToast('Please enter valid email addresses', 'error');
        return;
    }

    if (recipients.length === 0) {
        showToast('Please add at least one recipient', 'error');
        return;
    }

    updateRecipients(scriptName, recipients);
}

async function updateRecipients(scriptName, recipients) {
    try {
        const response = await fetch(`/api/scripts/${scriptName}/recipients`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ recipients })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast('Email recipients updated successfully', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showToast(`Error: ${data.error || 'Failed to update recipients'}`, 'error');
        }
    } catch (error) {
        console.error('Error updating recipients:', error);
        showToast('Network error - please try again', 'error');
    }
}

// ========================= Run History =========================

async function loadRunHistory(scriptName, limit = 50) {
    try {
        const response = await fetch(`/api/scripts/${scriptName}/runs?limit=${limit}`);
        const data = await response.json();

        return data;
    } catch (error) {
        console.error('Error loading run history:', error);
        return [];
    }
}

async function showRunDetails(runId) {
    try {
        const response = await fetch(`/api/runs/${runId}`);
        const data = await response.json();

        if (response.ok) {
            // Display run details in a modal (would need to implement modal HTML)
            console.log('Run details:', data);
            // TODO: Implement modal display
        } else {
            showToast('Failed to load run details', 'error');
        }
    } catch (error) {
        console.error('Error loading run details:', error);
        showToast('Network error - please try again', 'error');
    }
}

// ========================= Dashboard Refresh =========================

function refreshDashboard() {
    location.reload();
}

// ========================= Auto-refresh for Running Scripts =========================

// Check if any scripts are running on page load
document.addEventListener('DOMContentLoaded', () => {
    // Find all script cards to check for running status
    const runningScripts = document.querySelectorAll('[data-running="true"]');

    if (runningScripts.length > 0) {
        // Auto-refresh every 10 seconds if scripts are running
        setTimeout(() => location.reload(), 10000);
    }

    // Format all timestamps to be more human-readable
    formatAllTimestamps();
});

// ========================= Timestamp Formatting =========================

function formatAllTimestamps() {
    const timestamps = document.querySelectorAll('.timestamp-relative');

    timestamps.forEach(element => {
        const isoTimestamp = element.getAttribute('data-timestamp');
        const label = element.parentElement.textContent.trim().startsWith('Last') ? 'last' : 'next';

        if (isoTimestamp) {
            if (label === 'last') {
                // For "last run", show "X minutes/hours/days ago"
                element.textContent = formatTimestamp(isoTimestamp);
            } else {
                // For "next run", show countdown or readable date
                element.textContent = formatNextRunTime(isoTimestamp);
            }
        }
    });
}

function formatNextRunTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = date - now;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 0) {
        return 'soon';
    } else if (diffMins < 1) {
        return 'in < 1 minute';
    } else if (diffMins < 60) {
        return `in ${diffMins} minute${diffMins !== 1 ? 's' : ''}`;
    } else if (diffMins < 1440) {
        const hours = Math.floor(diffMins / 60);
        return `in ${hours} hour${hours !== 1 ? 's' : ''}`;
    } else if (diffMins < 10080) {
        const days = Math.floor(diffMins / 1440);
        return `in ${days} day${days !== 1 ? 's' : ''}`;
    } else {
        // For far future dates, show actual date/time
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit'
        });
    }
}

// ========================= Utility Functions =========================

function formatDuration(seconds) {
    if (seconds < 60) {
        return `${seconds}s`;
    } else if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${minutes}m ${secs}s`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }
}

function formatTimestamp(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) {
        return 'just now';
    } else if (diffMins < 60) {
        return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    } else if (diffMins < 1440) {
        const hours = Math.floor(diffMins / 60);
        return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
    } else {
        const days = Math.floor(diffMins / 1440);
        return `${days} day${days !== 1 ? 's' : ''} ago`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========================= Script Error Log =========================

async function refreshScriptErrors(scriptName) {
    try {
        const response = await fetch(`/api/scripts/${scriptName}/runs?limit=50`);
        const data = await response.json();

        if (response.ok) {
            // Filter runs with errors
            const errorRuns = data.filter(run => run.status === 'error' || run.error_flag === 1);
            displayScriptErrors(scriptName, errorRuns);

            // Update error count badge
            const badge = document.getElementById(`error-count-badge-${scriptName}`);
            if (badge) {
                badge.textContent = errorRuns.length;
            }
        } else {
            console.error('Failed to fetch script errors:', data.error);
        }
    } catch (error) {
        console.error('Error fetching script errors:', error);
        const container = document.getElementById(`error-log-container-${scriptName}`);
        if (container) {
            container.innerHTML = `
                <div class="text-center text-red-500 py-4">
                    <span class="text-sm">Failed to load errors</span>
                </div>
            `;
        }
    }
}

function displayScriptErrors(scriptName, errorRuns) {
    const container = document.getElementById(`error-log-container-${scriptName}`);
    if (!container) return;

    if (!errorRuns || errorRuns.length === 0) {
        container.innerHTML = `
            <div class="text-center text-gray-500 py-4">
                <span class="text-sm">✅ No errors logged</span>
            </div>
        `;
        return;
    }

    let html = '<div class="space-y-2">';

    errorRuns.forEach(run => {
        const timestamp = new Date(run.start_time);
        const timeAgo = formatTimestamp(run.start_time);

        html += `
            <div class="border rounded p-3 bg-red-50 border-red-200">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="flex items-center gap-2 mb-1">
                            <span class="text-xs font-bold text-red-600 uppercase">
                                Run #${run.id} - ${run.trigger_type}
                            </span>
                        </div>
                        <div class="text-sm text-gray-800 mb-1">
                            ${escapeHtml(run.result_summary || 'Execution failed with errors')}
                        </div>
                        <div class="text-xs text-gray-500">
                            <span class="font-semibold">Started:</span> ${run.start_time.substring(0, 19).replace('T', ' ')} |
                            <span class="font-semibold">Time:</span> ${timeAgo} |
                            <span class="font-semibold">Triggered by:</span> ${run.triggered_by}
                        </div>
                    </div>
                    <div class="flex gap-1 ml-2">
                        <button onclick="showRunDetailsModal(${run.id}); event.stopPropagation();"
                                class="text-blue-600 hover:text-blue-800 text-xs font-bold px-2 py-1 border border-blue-600 rounded hover:bg-blue-50 transition"
                                title="View details">
                            ⓘ
                        </button>
                    </div>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

async function clearScriptErrors(scriptName) {
    if (!confirm(`Clear all error logs for ${scriptName}? This will remove all error run history entries.`)) {
        return;
    }

    try {
        // Delete all error runs for this script
        const response = await fetch(`/api/scripts/${scriptName}/runs`);
        const data = await response.json();

        if (response.ok) {
            const errorRuns = data.filter(run => run.status === 'error' || run.error_flag === 1);

            for (const run of errorRuns) {
                await fetch(`/api/runs/${run.id}`, { method: 'DELETE' });
            }

            showToast(`Cleared ${errorRuns.length} error entries for ${scriptName}`, 'success');
            refreshScriptErrors(scriptName);
        }
    } catch (error) {
        console.error('Error clearing script errors:', error);
        showToast('Failed to clear errors', 'error');
    }
}

// ========================= Run History =========================

async function refreshRunHistory(scriptName) {
    try {
        const response = await fetch(`/api/scripts/${scriptName}/runs?limit=20`);
        const data = await response.json();

        if (response.ok) {
            displayRunHistory(scriptName, data);

            // Update run count badge
            const badge = document.getElementById(`run-count-badge-${scriptName}`);
            if (badge) {
                badge.textContent = data.length;
            }
        } else {
            console.error('Failed to fetch run history:', data.error);
        }
    } catch (error) {
        console.error('Error fetching run history:', error);
        const container = document.getElementById(`run-history-container-${scriptName}`);
        if (container) {
            container.innerHTML = `
                <div class="text-center text-red-500 py-4">
                    <span class="text-sm">Failed to load run history</span>
                </div>
            `;
        }
    }
}

function displayRunHistory(scriptName, runs) {
    const container = document.getElementById(`run-history-container-${scriptName}`);
    if (!container) return;

    if (!runs || runs.length === 0) {
        container.innerHTML = `
            <div class="text-center text-gray-500 py-4">
                <span class="text-sm">No runs yet</span>
            </div>
        `;
        return;
    }

    let html = '<div class="space-y-2">';

    runs.forEach(run => {
        const timeAgo = formatTimestamp(run.start_time);
        const statusColor = run.status === 'success' ? 'green' : run.status === 'error' ? 'red' : 'amber';
        const statusIcon = run.status === 'success' ? '✓' : run.status === 'error' ? '✗' : '⟳';

        html += `
            <div class="border rounded p-3 bg-gray-50 hover:bg-gray-100 transition cursor-pointer"
                 onclick="showRunDetailsModal(${run.id}); event.stopPropagation();">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="flex items-center gap-2 mb-1">
                            <span class="text-xs font-bold text-${statusColor}-600 uppercase">
                                ${statusIcon} Run #${run.id}
                            </span>
                            <span class="text-xs px-2 py-0.5 rounded ${run.trigger_type === 'manual' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'}">
                                ${run.trigger_type}
                            </span>
                        </div>
                        <div class="text-sm text-gray-800 mb-1">
                            ${escapeHtml(run.result_summary || 'No summary available')}
                        </div>
                        <div class="text-xs text-gray-500">
                            <span class="font-semibold">Started:</span> ${run.start_time.substring(0, 19).replace('T', ' ')} |
                            <span class="font-semibold">Duration:</span> ${run.duration_seconds ? formatDuration(run.duration_seconds) : '-'} |
                            <span class="font-semibold">By:</span> ${run.triggered_by}
                        </div>
                    </div>
                    <div class="ml-2">
                        <button class="text-blue-600 hover:text-blue-800 text-xs font-bold px-2 py-1 border border-blue-600 rounded hover:bg-blue-50 transition"
                                title="View details">
                            ⓘ
                        </button>
                    </div>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

async function clearRunHistory(scriptName) {
    if (!confirm(`Clear all run history for ${scriptName}? This will remove all execution records.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/scripts/${scriptName}/runs`);
        const data = await response.json();

        if (response.ok) {
            for (const run of data) {
                await fetch(`/api/runs/${run.id}`, { method: 'DELETE' });
            }

            showToast(`Cleared ${data.length} run history entries for ${scriptName}`, 'success');
            refreshRunHistory(scriptName);
        }
    } catch (error) {
        console.error('Error clearing run history:', error);
        showToast('Failed to clear run history', 'error');
    }
}

// ========================= Run Details Modal =========================

async function showRunDetailsModal(runId) {
    const modal = document.getElementById('run-details-modal');
    const content = document.getElementById('run-details-content');

    modal.classList.remove('hidden');
    content.innerHTML = '<p class="text-gray-500">Loading...</p>';

    try {
        const response = await fetch(`/api/runs/${runId}`);
        const data = await response.json();

        if (response.ok) {
            let html = `
                <div class="space-y-4">
                    <div class="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <span class="text-gray-600">Run ID:</span>
                            <span class="text-gray-800 font-medium ml-2">#${data.id}</span>
                        </div>
                        <div>
                            <span class="text-gray-600">Status:</span>
                            <span class="text-gray-800 font-medium ml-2">${data.status}</span>
                        </div>
                        <div>
                            <span class="text-gray-600">Trigger Type:</span>
                            <span class="text-gray-800 font-medium ml-2">${data.trigger_type}</span>
                        </div>
                        <div>
                            <span class="text-gray-600">Triggered By:</span>
                            <span class="text-gray-800 font-medium ml-2">${data.triggered_by}</span>
                        </div>
                        <div>
                            <span class="text-gray-600">Start Time:</span>
                            <span class="text-gray-800 font-medium ml-2">${data.start_time.substring(0, 19).replace('T', ' ')}</span>
                        </div>
                        <div>
                            <span class="text-gray-600">Duration:</span>
                            <span class="text-gray-800 font-medium ml-2">${data.duration_seconds ? formatDuration(data.duration_seconds) : '-'}</span>
                        </div>
                    </div>

                    <div class="bg-gray-50 p-4 rounded">
                        <p class="text-sm font-semibold text-gray-700 mb-2">Summary:</p>
                        <p class="text-sm text-gray-600">${escapeHtml(data.result_summary || 'No summary available')}</p>
                    </div>

                    <div class="bg-gray-50 p-4 rounded">
                        <p class="text-sm font-semibold text-gray-700 mb-2">Session Log:</p>
                        <div class="space-y-2 text-sm">
            `;

            if (data.session_log && Object.keys(data.session_log).length > 0) {
                for (const [func, messages] of Object.entries(data.session_log)) {
                    html += `
                        <div class="border-l-2 border-blue-300 pl-3">
                            <p class="font-semibold text-gray-700">${func}:</p>
                            <ul class="ml-4 mt-1 space-y-1">
                    `;
                    if (Array.isArray(messages)) {
                        messages.forEach(msg => {
                            if (msg) {
                                html += `<li class="text-gray-600">• ${escapeHtml(msg)}</li>`;
                            }
                        });
                    }
                    html += `</ul></div>`;
                }
            } else {
                html += '<p class="text-gray-500">No session log available</p>';
            }

            html += `
                        </div>
                    </div>
                </div>
            `;

            content.innerHTML = html;
        } else {
            content.innerHTML = '<p class="text-red-500">Failed to load run details</p>';
        }
    } catch (error) {
        console.error('Error loading run details:', error);
        content.innerHTML = '<p class="text-red-500">Error loading run details</p>';
    }
}

function closeRunDetailsModal() {
    const modal = document.getElementById('run-details-modal');
    modal.classList.add('hidden');
}
