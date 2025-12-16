"""
Production Server for VariousInternalServices Web Interface

Uses Waitress WSGI server for production deployment.
"""

import socket
from waitress import serve
from app import app, initialize_scheduler
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Create a socket to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return '127.0.0.1'


if __name__ == '__main__':
    # Initialize scheduler before starting server
    initialize_scheduler()

    # Get local IP
    local_ip = get_local_ip()
    port = 5001

    # Print startup information
    print("\n" + "=" * 70)
    print("Various Internal Services - Production Server")
    print("=" * 70)
    print(f"\n🚀 Server starting on port {port}...")
    print(f"\n📍 Access URLs:")
    print(f"   Local:   http://localhost:{port}")
    print(f"   Network: http://{local_ip}:{port}")
    print(f"\n⏰ APScheduler is running in the background")
    print(f"\n🔐 Login with credentials from .env file")
    print("\n" + "=" * 70 + "\n")

    # Start Waitress server
    serve(
        app,
        host='0.0.0.0',
        port=port,
        threads=6,
        url_scheme='http'
    )
