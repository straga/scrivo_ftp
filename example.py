"""
Example of using FTP Server in MicroPython

Usage:
1. Import and create FTP server instance
2. Start server on specified host and port
3. Server will handle FTP clients in background
"""

import asyncio
from saioftp import FtpServer

async def main():
    # Create FTP server instance
    server = FtpServer()
    
    # Start server on default FTP port
    await server.start(host='0.0.0.0', port=21)
    
    # Keep running to handle FTP clients
    while True:
        await asyncio.sleep(1)

# Run the example
if __name__ == '__main__':
    asyncio.run(main())
