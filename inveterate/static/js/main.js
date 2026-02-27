/**
 * Utility functions and global app logic
 */

// Show loading spinner
function showLoading(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        el.innerHTML = '<div class="flex justify-center"><div class="spinner"></div></div>';
    }
}

// Show error message
function showError(message, elementId = null) {
    const errorHTML = `
        <div class="rounded-md bg-red-50 border-red-200 border p-4">
            <p class="text-red-800">${escapeHTML(message)}</p>
        </div>
    `;

    if (elementId) {
        document.getElementById(elementId).innerHTML = errorHTML;
    } else {
        // Show as toast notification
        showToast(message, 'error');
    }
}

// Show success message
function showSuccess(message, elementId = null) {
    const successHTML = `
        <div class="rounded-md bg-green-50 border-green-200 border p-4">
            <p class="text-green-800">${escapeHTML(message)}</p>
        </div>
    `;

    if (elementId) {
        document.getElementById(elementId).innerHTML = successHTML;
    } else {
        showToast(message, 'success');
    }
}

// Toast notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 p-4 rounded-md shadow-lg z-50 ${
        type === 'error' ? 'bg-red-500' :
        type === 'success' ? 'bg-green-500' :
        'bg-blue-500'
    } text-white`;
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Escape HTML to prevent XSS
function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Format bytes to human readable
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];

    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Format percentage
function formatPercent(value, total) {
    if (!total || total === 0) return '0%';
    return ((value / total) * 100).toFixed(1) + '%';
}

// Get status badge HTML
function getStatusBadge(status) {
    const statusClass = `status-${status.toLowerCase()}`;
    return `<span class="status-badge ${statusClass}">${escapeHTML(status)}</span>`;
}

// Poll for task completion
async function pollTask(taskId, callback, maxAttempts = 60) {
    let attempts = 0;

    const poll = async () => {
        try {
            // You would need a task status endpoint
            // For now, just call the callback after a delay
            if (attempts >= maxAttempts) {
                throw new Error('Task polling timed out');
            }

            attempts++;
            setTimeout(async () => {
                await callback();
            }, 2000);

        } catch (error) {
            console.error('Task polling error:', error);
            showError('Task failed: ' + error.message);
        }
    };

    poll();
}

// Confirm action
function confirmAction(message) {
    return confirm(message);
}

// Format uptime
function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h ${minutes}m`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
}

// Copy to clipboard
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard', 'success');
    } catch (err) {
        showToast('Failed to copy', 'error');
    }
}

// Initialize tooltips and other UI enhancements
document.addEventListener('DOMContentLoaded', () => {
    console.log('Inveterate app loaded');

    // Add click handlers for copy buttons
    document.querySelectorAll('[data-copy]').forEach(btn => {
        btn.addEventListener('click', () => {
            copyToClipboard(btn.dataset.copy);
        });
    });
});
