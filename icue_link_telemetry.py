#!/usr/bin/env python3
"""
iCUE LINK Telemetry Utility

A Python script for reading live telemetry data from Corsair iCUE LINK System Hubs.
Supports temperature monitoring, pump/fan RPM tracking, and data logging to CSV.

This implementation follows the Corsair iCUE Link Hub USB HID Protocol Specification v2.1
and is based on research from the FanControl.CorsairLink project.

Requirements:
    - hidapi library (pip install hidapi)
    - Corsair iCUE LINK System Hub connected via USB
    - Device must be accessible (may require running as administrator on some systems)

Author: Based on FanControl.CorsairLink research
License: MIT
"""

import argparse
import csv
import logging
import struct
import sys
import time
from datetime import datetime
from typing import List, Optional, Tuple

try:
    import hid
except ImportError:
    print("Error: hidapi library not found. Install with: pip install hidapi")
    sys.exit(1)


# Device Configuration
VENDOR_ID = 0x1B1C  # Corsair
PRODUCT_ID = 0x0C3F  # iCUE LINK System Hub

# HID Report Sizes (per USB HID Protocol Specification v2.1)
OUTPUT_REPORT_SIZE = 513  # Including 1-byte Report ID
INPUT_REPORT_SIZE = 512

# Protocol Constants
CMD_HEADER = bytes([0x00, 0x00, 0x01])

# Device Mode Commands
CMD_ENTER_SOFTWARE_MODE = bytes([0x01, 0x03, 0x00, 0x02])
CMD_EXIT_SOFTWARE_MODE = bytes([0x01, 0x03, 0x00, 0x01])

# Endpoint Management Commands
CMD_OPEN_ENDPOINT = bytes([0x0D, 0x01])
CMD_CLOSE_ENDPOINT = bytes([0x05, 0x01, 0x01])
CMD_READ = bytes([0x08, 0x01])

# Endpoint Identifiers
ENDPOINT_SPEEDS = bytes([0x17])
ENDPOINT_TEMPS = bytes([0x21])

# Data Type Identifiers
DATA_TYPE_SPEEDS = bytes([0x25, 0x00])
DATA_TYPE_TEMPS = bytes([0x10, 0x00])

# Response Parsing Constants
STATUS_CODE_INDEX = 1
DATA_TYPE_START_INDEX = 4
PAYLOAD_START_INDEX = 6

# Temperature Data Constants
TEMP_SCALING_FACTOR = 10.0
TEMP_VALUE_INDEX_LOW = 11
TEMP_VALUE_INDEX_HIGH = 12

# Speed Sensor Constants
SENSOR_BLOCK_SIZE = 3
PUMP_SENSOR_INDEX = 1
FAN_SENSORS_START_INDEX = 13
MAX_FANS = 3

# Communication Timing
COMMAND_DELAY_SECONDS = 0.05
RESPONSE_TIMEOUT_SECONDS = 1.0

# Status Codes
STATUS_SUCCESS = 0x00


class CorsairLinkError(Exception):
    """Custom exception for Corsair LINK communication errors."""
    pass


class CorsairLinkDevice:
    """
    Handles communication with a Corsair iCUE LINK System Hub.
    
    This class manages the HID connection, protocol communication, and data parsing
    for reading telemetry from Corsair cooling devices.
    """
    
    def __init__(self, debug: bool = False):
        """
        Initialize the device handler.
        
        Args:
            debug: Enable debug logging for protocol communication
        """
        self.device: Optional[hid.device] = None
        self.device_path: Optional[str] = None
        self.debug = debug
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure logging for debug output."""
        if self.debug:
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(levelname)s - %(message)s'
            )
        self.logger = logging.getLogger(__name__)
    
    def connect(self) -> None:
        """
        Discover and connect to the iCUE LINK System Hub.
        
        Raises:
            CorsairLinkError: If device is not found or connection fails
        """
        self.logger.info(f"Searching for device VID=0x{VENDOR_ID:04X}, PID=0x{PRODUCT_ID:04X}")
        
        device_list = hid.enumerate(VENDOR_ID, PRODUCT_ID)
        if not device_list:
            raise CorsairLinkError(
                "iCUE LINK System Hub not found. Please ensure the device is connected "
                "and you have appropriate permissions (may require administrator access)."
            )
        
        device_info = device_list[0]
        self.device_path = device_info['path'].decode('utf-8')
        self.logger.info(f"Device found at path: {self.device_path}")
        
        try:
            self.device = hid.device()
            self.device.open_path(device_info['path'])
            self.device.set_nonblocking(1)  # Enable non-blocking reads for timeouts
            self.logger.info("Successfully connected to device")
        except Exception as e:
            raise CorsairLinkError(f"Failed to connect to device: {e}")
    
    def disconnect(self) -> None:
        """Safely disconnect from the device."""
        if self.device:
            try:
                self.logger.info("Returning device to hardware mode")
                self._send_command(CMD_EXIT_SOFTWARE_MODE)
                self.device.close()
                self.logger.info("Device disconnected successfully")
            except Exception as e:
                self.logger.warning(f"Error during disconnect: {e}")
            finally:
                self.device = None
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def _create_command_packet(self, command: bytes, data: bytes = b'') -> bytes:
        """
        Create a properly formatted command packet.
        
        Args:
            command: The command bytes to send
            data: Optional data payload
            
        Returns:
            Formatted packet ready for transmission
        """
        packet = bytearray(OUTPUT_REPORT_SIZE)
        packet[0] = 0x00  # Report ID
        
        full_command = CMD_HEADER + command + data
        packet[1:1 + len(full_command)] = full_command
        
        return bytes(packet)
    
    def _send_command(self, command: bytes, data: bytes = b'') -> None:
        """
        Send a command to the device.
        
        Args:
            command: Command bytes to send
            data: Optional data payload
            
        Raises:
            CorsairLinkError: If device is not connected or write fails
        """
        if not self.device:
            raise CorsairLinkError("Device not connected")
        
        packet = self._create_command_packet(command, data)
        
        if self.debug:
            self.logger.debug(f"Sending command: {command.hex()}, data: {data.hex()}")
        
        try:
            self.device.write(packet)
            time.sleep(COMMAND_DELAY_SECONDS)  # Critical timing delay
        except Exception as e:
            raise CorsairLinkError(f"Failed to send command: {e}")
    
    def _read_response(self, expected_data_type: bytes) -> bytes:
        """
        Read a response packet with the expected data type.
        
        Args:
            expected_data_type: The 2-byte data type identifier to wait for
            
        Returns:
            The response packet data
            
        Raises:
            CorsairLinkError: If timeout occurs or invalid response received
        """
        if not self.device:
            raise CorsairLinkError("Device not connected")
        
        start_time = time.monotonic()
        
        while time.monotonic() - start_time < RESPONSE_TIMEOUT_SECONDS:
            try:
                response = self.device.read(INPUT_REPORT_SIZE)
                
                if not response:
                    continue
                
                if self.debug:
                    hex_data = ' '.join(f'{b:02X}' for b in response[:32])
                    self.logger.debug(f"Received: {hex_data}...")
                
                # Validate response structure
                if len(response) < DATA_TYPE_START_INDEX + 2:
                    continue
                
                # Check status code
                status_code = response[STATUS_CODE_INDEX]
                if status_code != STATUS_SUCCESS:
                    raise CorsairLinkError(f"Device returned error status: 0x{status_code:02X}")
                
                # Check data type
                received_type = bytes(response[DATA_TYPE_START_INDEX:DATA_TYPE_START_INDEX + 2])
                if received_type == expected_data_type:
                    return bytes(response)
                    
            except Exception as e:
                if "Device returned error status" in str(e):
                    raise
                # Continue on read errors (device may not be ready)
                continue
        
        raise CorsairLinkError(f"Timeout waiting for response type {expected_data_type.hex()}")
    
    def enter_software_mode(self) -> None:
        """
        Switch the device to software mode for telemetry access.
        
        Raises:
            CorsairLinkError: If mode switch fails
        """
        self.logger.info("Entering software mode")
        self._send_command(CMD_ENTER_SOFTWARE_MODE)
    
    def _read_endpoint_data(self, endpoint: bytes, data_type: bytes) -> bytes:
        """
        Read data from a specific endpoint using the standard protocol sequence.
        
        Args:
            endpoint: Endpoint identifier
            data_type: Expected data type identifier
            
        Returns:
            Raw response packet data
        """
        # Standard endpoint communication sequence
        self._send_command(CMD_CLOSE_ENDPOINT, endpoint)
        self._send_command(CMD_OPEN_ENDPOINT, endpoint)
        self._send_command(CMD_READ)
        response = self._read_response(data_type)
        self._send_command(CMD_CLOSE_ENDPOINT, endpoint)
        
        return response
    
    def read_temperature(self) -> Optional[float]:
        """
        Read the liquid temperature from the device.
        
        Returns:
            Temperature in Celsius, or None if unavailable
            
        Raises:
            CorsairLinkError: If communication fails
        """
        try:
            response = self._read_endpoint_data(ENDPOINT_TEMPS, DATA_TYPE_TEMPS)
            
            # Temperature data is at fixed positions (bytes 11-12)
            if len(response) >= TEMP_VALUE_INDEX_HIGH + 1:
                raw_temp = struct.unpack(
                    '<h', 
                    bytes([response[TEMP_VALUE_INDEX_LOW], response[TEMP_VALUE_INDEX_HIGH]])
                )[0]
                return raw_temp / TEMP_SCALING_FACTOR
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to read temperature: {e}")
            return None
    
    def read_speeds(self) -> Tuple[Optional[int], List[Optional[int]]]:
        """
        Read pump and fan speeds from the device.
        
        Returns:
            Tuple of (pump_rpm, [fan1_rpm, fan2_rpm, fan3_rpm])
            None values indicate unavailable sensors
            
        Raises:
            CorsairLinkError: If communication fails
        """
        try:
            response = self._read_endpoint_data(ENDPOINT_SPEEDS, DATA_TYPE_SPEEDS)
            speeds = self._parse_speed_sensors(response)
            
            # Extract pump RPM
            pump_rpm = None
            if len(speeds) > PUMP_SENSOR_INDEX and speeds[PUMP_SENSOR_INDEX] is not None:
                pump_rpm = speeds[PUMP_SENSOR_INDEX]
            
            # Extract fan RPMs
            fan_rpms = []
            for i in range(MAX_FANS):
                fan_index = FAN_SENSORS_START_INDEX + i
                if len(speeds) > fan_index and speeds[fan_index] is not None:
                    fan_rpms.append(speeds[fan_index])
                else:
                    fan_rpms.append(None)
            
            return pump_rpm, fan_rpms
            
        except Exception as e:
            self.logger.warning(f"Failed to read speeds: {e}")
            return None, [None] * MAX_FANS
    
    def _parse_speed_sensors(self, packet: bytes) -> List[Optional[int]]:
        """
        Parse speed sensor data from a response packet.
        
        Args:
            packet: Raw response packet
            
        Returns:
            List of RPM values (None for unavailable sensors)
        """
        if len(packet) <= PAYLOAD_START_INDEX:
            return []
        
        payload = packet[PAYLOAD_START_INDEX:]
        if len(payload) < 1:
            return []
        
        sensors = []
        sensor_count = payload[0]
        sensor_data_start = 1
        
        for i in range(sensor_count):
            offset = sensor_data_start + (i * SENSOR_BLOCK_SIZE)
            if offset + 2 >= len(payload):
                break
            
            status = payload[offset]
            if status == 0x00:  # Sensor available
                rpm_value = struct.unpack('<h', payload[offset + 1:offset + 3])[0]
                sensors.append(rpm_value)
            else:
                sensors.append(None)
        
        return sensors


class TelemetryLogger:
    """Handles CSV logging of telemetry data."""
    
    def __init__(self, filename: str, device_path: str):
        """
        Initialize the CSV logger.
        
        Args:
            filename: Output CSV filename
            device_path: Device path for identification
        """
        self.filename = filename
        self.device_path = device_path
        self.file = None
        self.writer = None
    
    def __enter__(self):
        """Context manager entry."""
        self.file = open(self.filename, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file)
        
        # Write CSV header
        header = ['timestamp', 'device_path', 'liquid_temp_c', 'pump_rpm', 
                 'fan1_rpm', 'fan2_rpm', 'fan3_rpm']
        self.writer.writerow(header)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.file:
            self.file.close()
    
    def log_data(self, timestamp: str, liquid_temp: Optional[float], 
                 pump_rpm: Optional[int], fan_rpms: List[Optional[int]]) -> None:
        """
        Log a data point to the CSV file.
        
        Args:
            timestamp: ISO format timestamp
            liquid_temp: Liquid temperature in Celsius
            pump_rpm: Pump RPM
            fan_rpms: List of fan RPM values
        """
        row = [timestamp, self.device_path, liquid_temp, pump_rpm] + fan_rpms
        self.writer.writerow(row)


def format_telemetry_output(timestamp: str, liquid_temp: Optional[float],
                          pump_rpm: Optional[int], fan_rpms: List[Optional[int]]) -> str:
    """
    Format telemetry data for console output.
    
    Args:
        timestamp: ISO format timestamp
        liquid_temp: Liquid temperature in Celsius
        pump_rpm: Pump RPM
        fan_rpms: List of fan RPM values
        
    Returns:
        Formatted string for display
    """
    temp_str = f"{liquid_temp:.1f}°C" if liquid_temp is not None else "N/A"
    pump_str = str(pump_rpm) if pump_rpm is not None else "N/A"
    fan_strs = [str(rpm) if rpm is not None else "N/A" for rpm in fan_rpms]
    
    return (f"{timestamp} | Liquid: {temp_str} | Pump: {pump_str} RPM | "
            f"Fans: {', '.join(fan_strs)} RPM")


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Read and log telemetry data from a Corsair iCUE LINK System Hub.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Print to console every 2 seconds
  %(prog)s -i 5                     # Print to console every 5 seconds  
  %(prog)s -o telemetry.csv         # Log to CSV file
  %(prog)s -o data.csv -i 1 -d      # Log to CSV every 1 second with debug output

Notes:
  - Requires Corsair iCUE LINK System Hub connected via USB
  - May require administrator/root privileges for device access
  - Press Ctrl+C to stop data collection
        """)
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        help="Output CSV file path. If not specified, prints to console."
    )
    
    parser.add_argument(
        '-i', '--interval',
        type=float,
        default=2.0,
        help="Polling interval in seconds (default: 2.0)"
    )
    
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help="Enable debug output showing raw protocol communication"
    )
    
    return parser


def main() -> None:
    """Main application entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Validate arguments
    if args.interval <= 0:
        print("Error: Interval must be positive")
        sys.exit(1)
    
    try:
        # Connect to device
        with CorsairLinkDevice(debug=args.debug) as device:
            device.enter_software_mode()
            
            print("--- Starting Telemetry Capture (Press Ctrl+C to exit) ---")
            
            # Setup logging if requested
            logger_context = None
            if args.output:
                print(f"Logging telemetry data to: {args.output}")
                logger_context = TelemetryLogger(args.output, device.device_path)
            
            with logger_context if logger_context else suppress_context():
                while True:
                    timestamp = datetime.now().isoformat()
                    
                    # Read telemetry data
                    liquid_temp = device.read_temperature()
                    pump_rpm, fan_rpms = device.read_speeds()
                    
                    # Output data
                    if logger_context:
                        logger_context.log_data(timestamp, liquid_temp, pump_rpm, fan_rpms)
                    else:
                        output = format_telemetry_output(timestamp, liquid_temp, pump_rpm, fan_rpms)
                        print(output)
                    
                    time.sleep(args.interval)
    
    except KeyboardInterrupt:
        print("\nStopping telemetry capture...")
    except CorsairLinkError as e:
        print(f"Device Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


class suppress_context:
    """Null context manager when no logging is needed."""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


if __name__ == "__main__":
    main()
