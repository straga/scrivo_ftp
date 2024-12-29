# MicroPython FTP Server for Scrivo

A lightweight, memory-efficient FTP server implementation for MicroPython, designed specifically for ESP32 and similar microcontrollers.

## Features

- Asynchronous operation using `asyncio`
- Memory-efficient file transfers using reusable buffers
- Support for basic FTP commands:
  - USER: Authentication (simple)
  - SYST: System information
  - FEAT: Server features
  - TYPE: Transfer type
  - PWD: Print working directory
  - CWD: Change directory
  - PASV: Passive mode
  - LIST: Directory listing
  - RETR: Download file
  - STOR: Upload file (with temporary file safety)
  - DELE: Delete file
  - QUIT: Close connection

## Installation

1. Copy `saioftp.py` to your MicroPython device
2. Optional: Copy `main.py` or `example.py` for reference


## Usage

Basic usage:

```python
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

# Run the server
asyncio.run(main())
```

See `main.py` for a complete example.

## Memory Usage

The server is designed to be memory-efficient:
- Uses a single 512-byte reusable buffer for file transfers
- Implements small pauses between operations to prevent memory fragmentation
- Avoids string concatenation and temporary object creation
- Uses direct file operations without loading entire files into memory

## Security

Basic security features:
- Simple authentication (can be extended)
- Safe file uploads using temporary files
- No system directory changes (uses internal path tracking)


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - feel free to use in your own projects.

## Credits

Developed for MicroPython by the Viktor Vorobjov.
