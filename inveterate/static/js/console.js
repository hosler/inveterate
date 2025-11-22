/**
 * Proxmox Console Integration using xterm.js
 * Handles authentication and WebSocket connection to Proxmox
 */

class ProxmoxConsole {
    constructor(serviceId, containerId = 'terminal') {
        this.serviceId = serviceId;
        this.containerId = containerId;
        this.term = null;
        this.socket = null;
        this.authData = null;
    }

    /**
     * Initialize console
     */
    async init() {
        try {
            // Get authentication data
            await this.authenticate();

            // Initialize xterm.js
            this.initTerminal();

            // Connect to Proxmox WebSocket
            await this.connect();

        } catch (error) {
            console.error('Console initialization failed:', error);
            this.showError(error.message);
        }
    }

    /**
     * Authenticate with Proxmox via backend proxy
     */
    async authenticate() {
        const response = await fetch(`/services/${this.serviceId}/console/auth/`);
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Authentication failed');
        }

        this.authData = data;
        console.log('Authenticated with Proxmox');
    }

    /**
     * Initialize xterm.js terminal
     */
    initTerminal() {
        const container = document.getElementById(this.containerId);

        this.term = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#1e1e1e',
                foreground: '#d4d4d4',
                cursor: '#ffffff',
                black: '#000000',
                red: '#cd3131',
                green: '#0dbc79',
                yellow: '#e5e510',
                blue: '#2472c8',
                magenta: '#bc3fbc',
                cyan: '#11a8cd',
                white: '#e5e5e5',
                brightBlack: '#666666',
                brightRed: '#f14c4c',
                brightGreen: '#23d18b',
                brightYellow: '#f5f543',
                brightBlue: '#3b8eea',
                brightMagenta: '#d670d6',
                brightCyan: '#29b8db',
                brightWhite: '#e5e5e5'
            },
            rows: 30,
            cols: 120
        });

        // Add fit addon to resize terminal
        const fitAddon = new FitAddon.FitAddon();
        this.term.loadAddon(fitAddon);

        // Open terminal in container
        this.term.open(container);
        fitAddon.fit();

        // Handle window resize
        window.addEventListener('resize', () => {
            fitAddon.fit();
        });

        this.term.writeln('Connecting to Proxmox console...');
    }

    /**
     * Connect to Proxmox WebSocket for console
     */
    async connect() {
        const { host, node, vmid, vmtype, ticket, CSRFPreventionToken } = this.authData;

        // For LXC containers, use terminal WebSocket
        // For QEMU/KVM, use VNC WebSocket

        if (vmtype === 'lxc') {
            try {
                // Get terminal proxy ticket from Proxmox
                // Note: This requires CORS to be configured on Proxmox or we need a backend proxy
                const proxyUrl = `https://${host}:8006/api2/json/nodes/${node}/lxc/${vmid}/termproxy`;

                const proxyResponse = await fetch(proxyUrl, {
                    method: 'POST',
                    headers: {
                        'CSRFPreventionToken': CSRFPreventionToken
                    },
                    credentials: 'include',  // Send cookies
                    // Set cookie manually for cross-origin
                    headers: {
                        'CSRFPreventionToken': CSRFPreventionToken,
                        'Authorization': `PVEAuthCookie=${ticket}`
                    }
                }).catch(error => {
                    // CORS issue - fall back to opening Proxmox directly
                    throw new Error('CORS_ERROR');
                });

                const proxyData = await proxyResponse.json();

                if (proxyData.data) {
                    const port = proxyData.data.port;
                    const vncticket = proxyData.data.ticket;

                    // Connect WebSocket with proper auth
                    const wsUrl = `wss://${host}:8006/api2/json/nodes/${node}/lxc/${vmid}/vncwebsocket?port=${port}&vncticket=${encodeURIComponent(vncticket)}`;

                    const ws = new WebSocket(wsUrl);
                    this.setupWebSocket(ws);
                } else {
                    throw new Error('Failed to get terminal proxy ticket');
                }
            } catch (error) {
                // If CORS blocks us, open in Proxmox
                this.term.writeln('\r\n\x1b[33mDirect console connection blocked by browser security.\x1b[0m');
                this.term.writeln('Opening Proxmox web console in new window...\r\n');

                const proxmoxUrl = `https://${host}:8006/#v1:0:18:4::5:${vmtype}%2F${vmid}:4::${node}:::`;
                setTimeout(() => {
                    window.open(proxmoxUrl, '_blank');
                }, 1000);
            }
        } else {
            // For KVM, show message and open Proxmox
            this.term.writeln('\r\n\x1b[33mKVM VMs use graphical console (VNC).\x1b[0m');
            this.term.writeln('Opening Proxmox web interface for full VNC access...\r\n');

            const proxmoxUrl = `https://${host}:8006/#v1:0:18:4::5:${vmtype}%2F${vmid}:4::${node}:::`;
            setTimeout(() => {
                window.open(proxmoxUrl, '_blank');
            }, 1000);
        }
    }

    /**
     * Setup WebSocket handlers
     */
    setupWebSocket(ws) {
        this.socket = ws;

        ws.onopen = () => {
            console.log('WebSocket connected');
            this.term.clear();
            this.term.writeln('Connected to console. Press Enter to activate...\r\n');

            // Send data from terminal to websocket
            this.term.onData(data => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(data);
                }
            });
        };

        ws.onmessage = (event) => {
            // Write data from websocket to terminal
            this.term.write(event.data);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.term.writeln('\r\n\x1b[31mConnection error occurred\x1b[0m');
        };

        ws.onclose = () => {
            console.log('WebSocket closed');
            this.term.writeln('\r\n\x1b[33mConnection closed\x1b[0m');
            this.term.writeln('Refresh page to reconnect');
        };
    }

    /**
     * Show error in terminal
     */
    showError(message) {
        if (this.term) {
            this.term.writeln(`\r\n\x1b[31mError: ${message}\x1b[0m`);
        } else {
            alert('Console error: ' + message);
        }
    }

    /**
     * Disconnect and cleanup
     */
    disconnect() {
        if (this.socket) {
            this.socket.close();
        }
        if (this.term) {
            this.term.dispose();
        }
    }
}

// Make available globally
window.ProxmoxConsole = ProxmoxConsole;
