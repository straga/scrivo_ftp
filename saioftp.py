
import os
import gc
import network
import asyncio


def info(msg):
    print("FTP: %s" % msg)


class FtpServer:
    """
    MicroPython FTP Server implementation
    Memory efficient FTP server with minimal buffer usage
    """
    # Timing constants
    PAUSE = 0.005  # Small pause between operations
    CLOSE_WAIT = 0.2  # Wait time before closing connections
    PASV_WAIT = 0.05  # Wait time for PASV connection check
    PASV_RETRIES = 10  # Number of retries for PASV connection

    # Buffer sizes
    CHUNK_SIZE = 256  # Smaller chunk size to reduce memory usage

    def __init__(self):
        self.pasv_server = None
        self.pasv_writer = None
        self.pasv_reader = None
        self.chunk = bytearray(self.CHUNK_SIZE)  # Smaller reusable buffer
        self.current_dir = '/'  # Current working directory for FTP session
        self.rename_from = None  # Store filename for rename operation

    def close(self):
        """Close PASV connection if open and collect garbage"""
        if self.pasv_writer:
            info("Closing PASV writer")
            try:
                self.pasv_writer.close()
                asyncio.sleep(self.CLOSE_WAIT)  # Give time to close
            except:
                pass
            self.pasv_writer = None
            self.pasv_reader = None

        if self.pasv_server:
            info("Closing PASV server")
            try:
                self.pasv_server.close()
            except:
                pass
            self.pasv_server = None

        gc.collect()

    async def cmd_pasv(self, writer):
        """Handle PASV command - start passive mode server"""
        # Close any existing PASV connection first
        self.close()

        port = 1024 + (os.urandom(1)[0] % 64510)
        info(f"Starting PASV server on port {port}")

        # Store the server callback to handle the connection
        async def handle_pasv_connection(reader, writer):
            info("New PASV data connection")
            self.pasv_reader = reader
            self.pasv_writer = writer
            info("PASV reader and writer set")

        self.pasv_server = await asyncio.start_server(handle_pasv_connection, host='0.0.0.0', port=port)

        addr = network.WLAN(network.STA_IF).ifconfig()[0].split('.')
        response = f'227 Entering Passive Mode ({addr[0]},{addr[1]},{addr[2]},{addr[3]},{port>>8},{port&0xFF})\r\n'
        info(f"PASV response: {response.strip()}")
        await writer.awrite(response.encode())

    async def cmd_list(self, writer):
        """Handle LIST command - send directory listing"""
        if not self.pasv_server:
            info("LIST failed: No PASV server")
            await writer.awrite(b'425 Use PASV first.\r\n')
            return

        # Wait a bit for PASV connection to establish
        for _ in range(self.PASV_RETRIES):  # Try for 0.5 seconds
            if self.pasv_writer:
                break
            await asyncio.sleep(self.PASV_WAIT)

        if not self.pasv_writer:
            info("LIST failed: No PASV writer after waiting")
            await writer.awrite(b'425 Data connection failed.\r\n')
            return

        info(f"LIST starting in directory: {self.current_dir}")
        await writer.awrite(b'150 Here comes the directory listing.\r\n')
        await asyncio.sleep(self.PAUSE)

        try:
            files = os.listdir(self.current_dir)
            info(f"Found {len(files)} files/directories")

            # Send all files
            for name in files:
                try:
                    full_path = self.get_full_path(name)
                    stat = os.stat(full_path)
                    size = stat[6]
                    is_dir = (stat[0] & 0o170000) == 0o040000
                    ftype = 'd' if is_dir else '-'
                    line = f'{ftype}rw-r--r-- 1 owner group {size:8d} Jan 1 2000 {name}\r\n'.encode()
                    await self.pasv_writer.awrite(line)
                    info(f"Listed: {name}")
                    await asyncio.sleep(self.PAUSE)
                    del line
                except Exception as e:
                    info(f"Error listing {name}: {str(e)}")
                    continue
                gc.collect()

            # Complete data transfer
            await asyncio.sleep(self.CLOSE_WAIT)  # Increased delay

            # Close data connection
            if self.pasv_writer:
                info("Closing data connection")
                await self.pasv_writer.aclose()
                self.pasv_writer = None
                self.pasv_reader = None

            # Close PASV server
            if self.pasv_server:
                info("Closing PASV server after transfer")
                self.pasv_server.close()
                self.pasv_server = None

            # Send confirmation
            await writer.awrite(b'226 Directory send OK.\r\n')
            info("LIST completed successfully")

        except Exception as e:
            info(f"LIST failed with error: {str(e)}")
            await writer.awrite(b'550 Failed.\r\n')
            self.close()

    async def cmd_retr(self, writer, filename):
        """Handle RETR command - send file contents"""
        if not self.pasv_server:
            info("RETR failed: No PASV server")
            await writer.awrite(b'425 Use PASV first.\r\n')
            return

        # Wait a bit for PASV connection to establish
        for _ in range(self.PASV_RETRIES):  # Try for 0.5 seconds
            if self.pasv_writer:
                break
            await asyncio.sleep(self.PASV_WAIT)

        if not self.pasv_writer:
            info("RETR failed: No PASV writer after waiting")
            await writer.awrite(b'425 Data connection failed.\r\n')
            return

        f = None
        try:
            full_path = self.get_full_path(filename)
            info(f"RETR starting for file: {full_path}")
            f = open(full_path, 'rb')
            await writer.awrite(b'150 Opening data connection.\r\n')
            await asyncio.sleep(self.PAUSE)

            while True:
                n = f.readinto(self.chunk)
                if not n:
                    break
                await self.pasv_writer.awrite(memoryview(self.chunk)[:n])
                await asyncio.sleep(self.PAUSE)
                gc.collect()

            f.close()
            f = None

            # Complete data transfer
            await asyncio.sleep(self.CLOSE_WAIT)  # Increased delay

            # Close data connection
            if self.pasv_writer:
                info("Closing data connection")
                await self.pasv_writer.aclose()
                self.pasv_writer = None
                self.pasv_reader = None

            # Close PASV server
            if self.pasv_server:
                info("Closing PASV server after transfer")
                self.pasv_server.close()
                self.pasv_server = None

            # Send confirmation
            await writer.awrite(b'226 Transfer complete.\r\n')
            info("RETR completed successfully")

        except Exception as e:
            info(f"RETR failed with error: {str(e)}")
            await writer.awrite(b'550 Failed.\r\n')
            if f:
                f.close()
            self.close()

    async def cmd_stor(self, writer, filename):
        """Handle STOR command - receive file contents"""
        if not self.pasv_server:
            info("STOR failed: No PASV server")
            await writer.awrite(b'425 Use PASV first.\r\n')
            return

        # Wait a bit for PASV connection to establish
        for _ in range(self.PASV_RETRIES):  # Try for 0.5 seconds
            if self.pasv_writer:
                break
            await asyncio.sleep(self.PASV_WAIT)

        if not self.pasv_writer:
            info("STOR failed: No PASV writer after waiting")
            await writer.awrite(b'425 Data connection failed.\r\n')
            return

        f = None
        tmp_name = filename + '.tmp'
        try:
            full_path = self.get_full_path(tmp_name)
            info(f"STOR starting for file: {full_path}")
            f = open(full_path, 'wb')
            await writer.awrite(b'150 Ok to send data.\r\n')
            await asyncio.sleep(self.PAUSE)

            while True:
                data = await self.pasv_reader.read(self.CHUNK_SIZE)
                if not data:
                    break
                f.write(data)
                await asyncio.sleep(self.PAUSE)
                del data
                gc.collect()

            f.close()
            f = None

            # If upload is successful, replace original file
            try:
                final_path = self.get_full_path(filename)
                info(f"Renaming {tmp_name} to {filename}")
                try:
                    os.remove(final_path)
                except:
                    pass
                os.rename(full_path, final_path)
            except Exception as e:
                info(f"Error renaming file: {str(e)}")
                raise

            # Complete data transfer
            await asyncio.sleep(self.CLOSE_WAIT)

            # Close data connection
            if self.pasv_writer:
                info("Closing data connection")
                await self.pasv_writer.aclose()
                self.pasv_writer = None
                self.pasv_reader = None

            # Close PASV server
            if self.pasv_server:
                info("Closing PASV server after transfer")
                self.pasv_server.close()
                self.pasv_server = None

            # Send confirmation
            await writer.awrite(b'226 Transfer complete.\r\n')
            info("STOR completed successfully")

        except Exception as e:
            info(f"STOR failed with error: {str(e)}")
            # Clean up temporary file on error
            try:
                os.remove(full_path)
            except:
                pass
            await writer.awrite(b'550 Failed.\r\n')
            if f:
                f.close()
            self.close()

    async def cmd_dele(self, writer, filename):
        """Handle DELE command - delete file"""
        try:
            full_path = self.get_full_path(filename)
            info(f"Deleting file: {full_path}")
            os.remove(full_path)
            await asyncio.sleep(self.PAUSE)
            await writer.awrite(b'250 File deleted.\r\n')
            info("DELE completed successfully")
        except Exception as e:
            info(f"DELE failed with error: {str(e)}")
            await writer.awrite(b'550 Failed.\r\n')

    async def cmd_rnfr(self, writer, filename):
        """Handle RNFR command - rename from"""
        try:
            full_path = self.get_full_path(filename)
            info(f"Rename from: {full_path}")
            os.stat(full_path)  # Check file existence
            self.rename_from = full_path
            await writer.awrite(b'350 Ready for destination name.\r\n')
            info("RNFR completed successfully")
        except Exception as e:
            info(f"RNFR failed with error: {str(e)}")
            await writer.awrite(b'550 File not found.\r\n')

    async def cmd_rnto(self, writer, filename):
        """Handle RNTO command - rename to"""
        if not self.rename_from:
            info("RNTO failed: No RNFR command first")
            await writer.awrite(b'503 Bad sequence of commands.\r\n')
            return

        try:
            full_path = self.get_full_path(filename)
            info(f"Rename to: {full_path}")
            os.rename(self.rename_from, full_path)
            await writer.awrite(b'250 File renamed.\r\n')
            info("RNTO completed successfully")
        except Exception as e:
            info(f"RNTO failed with error: {str(e)}")
            await writer.awrite(b'550 Rename failed.\r\n')
        finally:
            self.rename_from = None

    async def cmd_cwd(self, writer, path):
        """Handle CWD command - change working directory"""
        new_dir = path or '/'
        if new_dir.startswith('/'):
            # If path is absolute, use as is
            check_dir = new_dir
        else:
            # If path is relative, add current directory
            check_dir = self.current_dir + '/' + new_dir if self.current_dir != '/' else '/' + new_dir
        
        # Remove double slashes and normalize path
        check_dir = check_dir.replace('//', '/').rstrip('/')
        info(f"Changing directory to: {check_dir}")
        try:
            os.stat(check_dir)  # Check directory existence
            self.current_dir = check_dir
            await writer.awrite(b'250 OK.\r\n')
            info("CWD completed successfully")
        except Exception as e:
            info(f"CWD failed with error: {str(e)}")
            await writer.awrite(b'550 Failed.\r\n')

    async def server(self, reader, writer):
        """Main FTP server coroutine that handles client connection"""
        addr = writer.get_extra_info('peername')
        info(f"Client from {addr}")
        await writer.awrite(b'220 Welcome.\r\n')

        while True:
            data = await reader.readline()
            if not data:
                break

            parts = data.decode().split(' ', 1)
            cmd = parts[0].strip()
            arg = parts[1].strip() if len(parts) > 1 else None

            info(f"FTP: {cmd} {arg}")

            if cmd == 'USER':
                await writer.awrite(b'230 Logged in.\r\n')
            elif cmd == 'PASS':
                await writer.awrite(b'230 Logged in.\r\n')
            elif cmd == 'SYST':
                await writer.awrite(b'215 UNIX Type: L8\r\n')
            elif cmd == 'FEAT':
                await writer.awrite(b'211-Features:\r\n211 End\r\n')
            elif cmd == 'TYPE':
                await writer.awrite(b'200 OK.\r\n')
            elif cmd == 'PWD':
                await writer.awrite(f'257 "{self.current_dir}"\r\n'.encode())
            elif cmd == 'CWD':
                await self.cmd_cwd(writer, arg)
            elif cmd == 'PASV':
                await self.cmd_pasv(writer)
            elif cmd == 'LIST':
                await self.cmd_list(writer)
            elif cmd == 'RETR':
                await self.cmd_retr(writer, arg)
            elif cmd == 'STOR':
                await self.cmd_stor(writer, arg)
            elif cmd == 'DELE':
                await self.cmd_dele(writer, arg)
            elif cmd == 'RNFR':
                await self.cmd_rnfr(writer, arg)
            elif cmd == 'RNTO':
                await self.cmd_rnto(writer, arg)
            elif cmd == 'QUIT':
                await writer.awrite(b'221 Goodbye.\r\n')
                break
            else:
                await writer.awrite(b'502 Command not implemented.\r\n')

        writer.close()
        await writer.wait_closed()

    async def start(self, host='0.0.0.0', port=21):
        """Start FTP server on specified host and port"""
        self.server = await asyncio.start_server(self.server, host, port)

    def get_full_path(self, filename):
        """Get absolute path from current directory and filename"""
        if filename.startswith('/'):
            # If path is absolute, use as is
            path = filename
        else:
            # If path is relative, add current directory
            path = self.current_dir + '/' + filename if self.current_dir != '/' else '/' + filename
        
        # Remove double slashes and normalize path
        return path.replace('//', '/').rstrip('/')
