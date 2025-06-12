# **iCUE LINK Telemetry Utility & Protocol Specification**

This repository provides a Python utility and a reverse-engineered USB HID protocol specification for the Corsair iCUE LINK System Hub (VID: 0x1B1C, PID: 0x0C3F). The tool reads live telemetry (temperature, fan/pump RPMs) directly from the hardware, while the spec documents the commands and data structures required to do so.  
This work is based on research from the [FanControl.CorsairLink](https://github.com/evanmulawski/FanControl.CorsairLink) project, with corrections from live hardware testing.

## **Key Features**

* **Live Telemetry Utility:** A command-line tool to monitor and log hardware performance.  
* **Prometheus Exporter:** A service that exposes telemetry data as Prometheus metrics.
* **Detailed Protocol Specification:** An unofficial but validated spec for developers.  
* **Standalone Oper3ation:** Communicates directly with the hub via USB HID, no iCUE software required.  
* **Flexible Output:** View live data in the console, log it to a CSV file, or scrape via Prometheus.

## **The Utility: icue\_link\_telemetry.py**

### **Requirements**

* Python 3.6+ and the hidapi library  
* A Corsair iCUE LINK System Hub connected via USB.  
* Administrative/root privileges for direct HID device access.

### **Installation & Usage**

1. **Clone the repository and install dependencies:**  
   git clone https://github.com/cwawak/iCUE-LINK-Telemetry-Reader.git  
   cd iCUE-LINK-Telemetry-Reader  
   pip install hidapi

2. **Run the script:**  
   \# Print to console every 2 seconds  
   python icue\_link\_telemetry.py

   \# Log to a CSV file every 5 seconds  
   python icue\_link\_telemetry.py \-o telemetry.csv \-i 5

   *Note: May require sudo or Administrator privileges.* Press Ctrl+C to stop. For all options, run with \--help.

## **Prometheus Exporter: icue\_link\_prometheus\_exporter.py**

The Prometheus exporter provides a way to monitor your iCUE LINK System Hub in a production environment by exposing metrics in a format that Prometheus can scrape.

### **Requirements**

* Python 3.6+
* hidapi library
* prometheus-client library
* A Corsair iCUE LINK System Hub connected via USB
* Administrative/root privileges for direct HID device access

### **Installation & Usage**

1. **Install dependencies:**  
   pip install -r requirements.txt

2. **Run the exporter:**  
   \# Start with default settings (port 8000, 5-second updates)  
   python icue\_link\_prometheus\_exporter.py

   \# Custom port and update interval  
   python icue\_link\_prometheus\_exporter.py --port 9090 --update-interval 2.0

   \# Enable debug logging  
   python icue\_link\_prometheus\_exporter.py --log-level DEBUG

### **Available Metrics**

The exporter provides the following metrics:

* `icue_link_pump_rpm`: Pump speed in RPM
* `icue_link_water_temp`: Water temperature in Celsius
* `icue_link_fan_rpm`: Fan speed in RPM (with `fan_id` label to distinguish between fans)

### **Configuration Options**

* `--port`: HTTP port to expose metrics on (default: 8000)
* `--update-interval`: How often to update metrics in seconds (default: 5.0)
* `--log-level`: Set logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## **Reverse-Engineered Protocol Details**

This section details the unofficial USB HID protocol. A key finding is that the protocol uses inconsistent data structures for different sensor types.

* **Communication Flow:** The standard sequence is to Close, Open, Read, and then Close the target sensor endpoint.  
* **Device Info:** iCUE Link System Hub (0x1B1C:0x0C3F), Output Report: 513 bytes, Input Report: 512 bytes.  
* **Speed Data (Endpoint 0x17):** The response uses a structured format: a sensor count byte followed by 3-byte data blocks for each sensor.  
* **Temperature Data (Endpoint 0x21):** The response uses a fixed-position format. The temperature is a 16-bit little-endian value at **bytes 11-12**, which must be divided by 10.0. **This does not follow the block format used by speed sensors.**

## **License**

This project is licensed under the MIT License. See the LICENSE file for details.

## **Acknowledgements**

This work is heavily based on the excellent reverse-engineering by **Evan Mulawski** for the [**FanControl.CorsairLink**](https://github.com/evanmulawski/FanControl.CorsairLink) project.