"""
Mercedes DSM Protocol Handler
UDS protocol implementation for Mercedes Door Control Module
"""

import time
import struct

class DSMProtocol:
    """UDS protocol implementation for Mercedes DSM"""
    
    def __init__(self, connector):
        self.connector = connector
        self.tx_id = 0x7E0  # Diagnostic request
        self.rx_id = 0x7E8  # Diagnostic response
        
    def start_session(self):
        """Start diagnostic session (0x10 0x03)"""
        return self._send_uds([0x10, 0x03])
    
    def read_data_by_identifier(self, data_id):
        """
        Read Data By Identifier (0x22)
        data_id: 2-byte identifier (e.g., 0xF100 for EEPROM segment)
        """
        data = [0x22, (data_id >> 8) & 0xFF, data_id & 0xFF]
        response = self._send_uds(data)
        
        if response and len(response) > 2:
            # Check if response is positive (0x62)
            if response[0] == 0x62:
                # Verify data identifier matches
                if response[1] == (data_id >> 8) and response[2] == (data_id & 0xFF):
                    return response[3:]  # Return actual data
        
        return None
    
    def security_access(self, level=1, key=None):
        """
        Security Access (0x27)
        level: Access level (1 for request seed, 2 for send key)
        key: Key for level 2 (if None, only seed is requested)
        """
        if level == 1:
            # Request seed
            response = self._send_uds([0x27, 0x01])
            if response and len(response) > 2:
                if response[0] == 0x67 and response[1] == 0x01:
                    seed = response[2:]  # Seed bytes
                    return seed
        elif level == 2 and key:
            # Send key
            data = [0x27, 0x02] + list(key)
            response = self._send_uds(data)
            return response is not None
        
        return None
    
    def read_memory_by_address(self, address, length):
        """
        Read Memory By Address (0x23)
        address: Memory address to read from
        length: Number of bytes to read
        """
        # Format: [0x23, address_format, length_format, address_bytes..., length_bytes...]
        # Assuming 4-byte address, 2-byte length
        data = [0x23, 0x44, 0x22]  # 4-byte address, 2-byte length format
        
        # Add address bytes (big-endian)
        data.extend([(address >> 24) & 0xFF, (address >> 16) & 0xFF, 
                    (address >> 8) & 0xFF, address & 0xFF])
        
        # Add length bytes (big-endian)
        data.extend([(length >> 8) & 0xFF, length & 0xFF])
        
        response = self._send_uds(data)
        if response and response[0] == 0x63:
            return response[1:]  # Skip service ID
        
        return None
    
    def scan_eeprom_segments(self, start_id=0xF100, end_id=0xF1FF, step=0x10):
        """Scan for available EEPROM segments"""
        segments = []
        
        for seg_id in range(start_id, end_id + 1, step):
            data = self.read_data_by_identifier(seg_id)
            if data and len(data) > 0:
                segments.append((seg_id, data))
                print(f"Found segment 0x{seg_id:04X}: {len(data)} bytes")
            
            time.sleep(0.02)  # Avoid flooding the bus
        
        return segments
    
    def _send_uds(self, data):
        """Send UDS request and wait for response"""
        if not self.connector.send_can_frame(self.tx_id, bytes(data)):
            return None
        
        # Wait for response
        timeout = 2.0
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = self.connector.receive_can_frame(0.1)
            if response:
                resp_id, resp_data = response
                if resp_id == self.rx_id:
                    return resp_data
        
        return None
