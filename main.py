
import network
import asyncio
from saioftp import FtpServer


class WiFiManager:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wlan = None
        self._monitoring = False
        self._monitor_task = None
        
    def init_interface(self):
        """Initialize WiFi interface"""
        self.wlan = network.WLAN(network.STA_IF)
        if not self.wlan.active():
            self.wlan.active(True)
        return self.wlan
        
    async def connect(self, start_monitoring=True):
        """Connect to WiFi with retries"""
        if self.wlan is None:
            self.init_interface()
            
        # Try to connect if not connected
        if not self.wlan.isconnected():
            print('Connecting to WiFi...')
            try:
                self.wlan.connect(self.ssid, self.password)
                # Wait up to 10 seconds for connection
                for _ in range(10):
                    if self.wlan.isconnected():
                        break
                    await asyncio.sleep(1)
            except:
                print('Failed to connect')
                
        if self.wlan.isconnected():
            print('Network config:', self.wlan.ifconfig())
            if start_monitoring and not self._monitoring:
                self.start_monitoring()
            return True
        return False
        
    def start_monitoring(self):
        """Start WiFi monitoring in background"""
        if not self._monitoring:
            self._monitoring = True
            self._monitor_task = asyncio.create_task(self._monitor())
            
    async def _monitor(self):
        """Monitor WiFi connection and reconnect if needed"""
        while self._monitoring:
            if self.wlan is None or not self.wlan.isconnected():
                print('WiFi disconnected, reconnecting...')
                if await self.connect(start_monitoring=False):
                    print('WiFi reconnected')
                else:
                    print('WiFi reconnection failed')
            await asyncio.sleep(5)  # Check every 5 seconds
            
    def stop(self):
        """Stop WiFi monitoring"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None


class FtpService:
    def __init__(self, wifi_manager):
        self.wifi = wifi_manager
        self.server = None
        
    async def start(self, host='0.0.0.0', port=21):
        """Start FTP server on specified host and port"""
        if self.server is None:
            # Ensure WiFi is connected
            if not await self.wifi.connect():
                raise RuntimeError('WiFi connection required')
                
            # Start FTP server
            self.server = FtpServer()
            await self.server.start(host=host, port=port)
            print(f'FTP server started on port {port}')
        return self.server
        
    def stop(self):
        """Stop FTP server if running"""
        if self.server:
            self.server.close()
            self.server = None
            print('FTP server stopped')


async def main():
    # WiFi credentials
    SSID = 'YourWiFiName'
    PASSWORD = 'YourWiFiPassword'
    
    try:
        # Create managers
        wifi = WiFiManager(SSID, PASSWORD)
        service = FtpService(wifi)
        
        # Start FTP service
        await service.start()
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print('Stopped by user')
    except Exception as e:
        print('Error:', e)
    finally:
        if 'service' in locals():
            service.stop()
        if 'wifi' in locals():
            wifi.stop()


# Can be imported as module or run directly
if __name__ == '__main__':
    # Run as standalone FTP server
    asyncio.run(main())
