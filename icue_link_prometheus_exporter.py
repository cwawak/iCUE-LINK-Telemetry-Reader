#!/usr/bin/env python3
"""
iCUE LINK Prometheus Exporter

A Python service that exposes Corsair iCUE LINK System Hub telemetry data
as Prometheus metrics via an HTTP endpoint.

This exporter builds on top of the iCUE-LINK-Telemetry-Reader project to provide
continuous monitoring of pump speeds, fan RPMs, and water temperature.
"""

import argparse
import logging
import time
from typing import Dict, Optional, Tuple

from prometheus_client import start_http_server, Gauge, CollectorRegistry
from icue_link_telemetry import CorsairLinkDevice, CorsairLinkError

# Create a custom registry to hold our metrics. This is a more robust
# way to disable default metrics across different library versions.
custom_registry = CollectorRegistry()

# Prometheus metric definitions registered with our custom registry
PUMP_RPM = Gauge('icue_link_pump_rpm', 'Pump speed in RPM', registry=custom_registry)
WATER_TEMP = Gauge('icue_link_water_temp', 'Water temperature in Celsius', registry=custom_registry)
FAN_RPM = Gauge('icue_link_fan_rpm', 'Fan speed in RPM', ['fan_id'], registry=custom_registry)

class ICueLinkExporter:
    """Prometheus exporter for iCUE LINK System Hub telemetry."""
    
    def __init__(self, port: int = 8000, update_interval: float = 5.0):
        """
        Initialize the exporter.
        
        Args:
            port: HTTP port to expose metrics on
            update_interval: How often to update metrics (in seconds)
        """
        self.port = port
        self.update_interval = update_interval
        self.device: Optional[CorsairLinkDevice] = None
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def _update_metrics(self) -> None:
        """Read telemetry data and update Prometheus metrics."""
        try:
            if not self.device:
                self.device = CorsairLinkDevice()
                self.device.connect()
                self.device.enter_software_mode()
            
            # Read temperature
            temp = self.device.read_temperature()
            if temp is not None:
                WATER_TEMP.set(temp)
            
            # Read speeds
            pump_rpm, fan_rpms = self.device.read_speeds()
            if pump_rpm is not None:
                PUMP_RPM.set(pump_rpm)
            
            # Update fan metrics
            for i, rpm in enumerate(fan_rpms, 1):
                if rpm is not None:
                    FAN_RPM.labels(fan_id=str(i)).set(rpm)
            
        except CorsairLinkError as e:
            self.logger.error(f"Error reading telemetry: {e}")
            # Reset metrics to indicate no data
            WATER_TEMP.set(0)
            PUMP_RPM.set(0)
            for i in range(1, 4):  # Reset all fan metrics
                FAN_RPM.labels(fan_id=str(i)).set(0)
            
            # Try to recover connection
            if self.device:
                try:
                    self.device.disconnect()
                except:
                    pass
                self.device = None
    
    def run(self) -> None:
        """Run the exporter service."""
        self.logger.info(f"Starting iCUE LINK Prometheus exporter on port {self.port}")
        self.logger.info(f"Updating metrics every {self.update_interval} seconds")
        
        # Start HTTP server with our custom registry to avoid default metrics
        start_http_server(self.port, registry=custom_registry)
        
        while True:
            self._update_metrics()
            time.sleep(self.update_interval)

def create_argument_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="iCUE LINK Prometheus Exporter",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port to expose metrics on'
    )
    parser.add_argument(
        '--update-interval',
        type=float,
        default=5.0,
        help='How often to update metrics (in seconds)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set the logging level'
    )
    return parser

def main() -> None:
    """Main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Set logging level
    logging.basicConfig(level=getattr(logging, args.log_level))
    
    exporter = ICueLinkExporter(
        port=args.port,
        update_interval=args.update_interval
    )
    
    try:
        exporter.run()
    except KeyboardInterrupt:
        logging.info("Exiting...")
    finally:
        if exporter.device:
            exporter.device.disconnect()

if __name__ == '__main__':
    main()
