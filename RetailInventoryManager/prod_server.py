"""
Production server runner using Waitress WSGI server.

This script runs the Flask application using Waitress, making it accessible
from any device on the same network.

To run: python prod_server.py
To access from other devices: http://<your-computer-ip>:5000
"""

from waitress import serve
from app import app
import socket
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "Unable to determine IP"

if __name__ == '__main__':
    host = '0.0.0.0'  # Listen on all network interfaces
    port = 5000

    local_ip = get_local_ip()

    logger.info("=" * 70)
    logger.info("Starting Retail Inventory Manager in PRODUCTION MODE")
    logger.info("=" * 70)
    logger.info(f"Server running on: http://{local_ip}:{port}")
    logger.info(f"Access from this computer: http://localhost:{port}")
    logger.info(f"Access from other devices on network: http://{local_ip}:{port}")
    logger.info("=" * 70)
    logger.info("Press Ctrl+C to stop the server")
    logger.info("=" * 70)

    # Run the production server
    serve(app, host=host, port=port, threads=6)
