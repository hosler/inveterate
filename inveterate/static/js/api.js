/**
 * Inveterate API Client
 * Handles all REST API interactions with CSRF protection
 */

class InveterateAPI {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
        this.csrfToken = this.getCSRFToken();
    }

    /**
     * Get CSRF token from cookie
     */
    getCSRFToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    /**
     * Make API request
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP ${response.status}: ${response.statusText}`);
            }

            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // Service operations
    async getServices() {
        return this.request('/services/');
    }

    async getService(id) {
        return this.request(`/services/${id}/`);
    }

    async startService(id) {
        return this.request(`/services/${id}/start/`, { method: 'POST' });
    }

    async stopService(id) {
        return this.request(`/services/${id}/stop/`, { method: 'POST' });
    }

    async shutdownService(id) {
        return this.request(`/services/${id}/shutdown/`, { method: 'POST' });
    }

    async rebootService(id) {
        return this.request(`/services/${id}/reboot/`, { method: 'POST' });
    }

    async resetService(id) {
        return this.request(`/services/${id}/reset/`, { method: 'POST' });
    }

    async getServiceStatus(id) {
        return this.request(`/services/${id}/status/`, { method: 'POST' });
    }

    async getServiceIPs(id) {
        return this.request(`/services/${id}/ips/`);
    }

    async getConsoleAccess(id) {
        return this.request(`/services/${id}/console/`);
    }

    // Node operations
    async getNodes() {
        return this.request('/nodes/');
    }

    async getNode(id) {
        return this.request(`/nodes/${id}/`);
    }

    async getNodeStatus(id) {
        return this.request(`/nodes/${id}/status/`);
    }

    async getNodeVMs(id) {
        return this.request(`/nodes/${id}/vms/`);
    }

    // Cluster operations
    async getClusters() {
        return this.request('/clusters/');
    }

    async getCluster(id) {
        return this.request(`/clusters/${id}/`);
    }

    async getClusterStatus(id) {
        return this.request(`/clusters/${id}/status/`);
    }

    async testConnection(host, user, key) {
        return this.request('/clusters/test_connection/', {
            method: 'POST',
            body: JSON.stringify({ host, user, key })
        });
    }

    // Dashboard
    async getDashboardSummary() {
        return this.request('/dashboard/summary/');
    }

    async getDashboardStats() {
        return this.request('/clusters/stats/');
    }

    // Plans and Templates
    async getPlans() {
        return this.request('/plans/');
    }

    async getTemplates() {
        return this.request('/templates/');
    }

    // IP Pools
    async getIPPools() {
        return this.request('/ippools/');
    }

    async getIPs() {
        return this.request('/ips/');
    }
}

// Global API instance
window.api = new InveterateAPI();
