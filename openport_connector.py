"""
OpenPort 2.0 Connector
Module for communication with OpenPort 2.0 via serial port
"""

import serial
import time
import struct
from threading import Lock

class OpenPortConnector:
    """Connection manager for OpenPort 2.0"""
    
    def __init__(self, port='COM3', baudrate=500000):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.is_connected = False
        self.lock = Lock()
        
    def connect(self):
        """Establish connection to OpenPort"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=115200,  # OpenPort fixed baudrate
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=1,
                write_timeout=1
            )
            
            # Initialize CAN interface
            self._send_command('C')  # Close if open
            time.sleep(0.1)
            self._send_command('O')  # Open CAN
            time.sleep(0.1)
            self._send_command(f'S{self.baudrate}')  # Set CAN speed
            time.sleep(0.1)
            self._send_command('M1')  # Monitoring mode
            
            self.is_connected = True
            return True
            
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        """Close connection"""
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.is_connected = False
    
    def send_can_frame(self, can_id, data):
        """Send CAN frame through OpenPort"""
        if not self.is_connected:
            return False
        
        with self.lock:
            try:
                # OpenPort format: tIIIdd...
                cmd = f't{can_id:03X}{data.hex()}\r'
                self.serial.write(cmd.encode())
                return True
            except Exception as e:
                print(f"Send error: {e}")
                return False
    
    def receive_can_frame(self, timeout=1.0):
        """Receive CAN frame from OpenPort"""
        if not self.is_connected:
            return None
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.serial.in_waiting:
                try:
                    line = self.serial.readline().decode().strip()
                    if line.startswith('t'):
                        # Parse OpenPort response format
                        can_id = int(line[1:4], 16)
                        data_hex = line[4:]
                        # Clean non-hex characters
                        data_hex = ''.join(c for c in data_hex if c in '0123456789ABCDEFabcdef')
                        data = bytes.fromhex(data_hex)
                        return can_id, data
                except Exception as e:
                    print(f"Receive error: {e}")
        
        return None
    
    def _send_command(self, cmd):
        """Send low-level command to OpenPort"""
        if self.serial:
            self.serial.write(f'{cmd}\r'.encode())
            time.sleep(0.05)
            return self.serial.read(100).decode().strip()
        return ""
    
    def test_connection(self):
        """Test if OpenPort is responsive"""
        try:
            response = self._send_command('V')  # Version command
            return 'OpenPort' in response
        except:
            return False
