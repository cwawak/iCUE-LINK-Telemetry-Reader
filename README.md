# **iCUE LINK Telemetry Utility & Protocol Specification**

This repository provides a Python utility and a reverse-engineered USB HID protocol specification for the Corsair iCUE LINK System Hub (VID: 0x1B1C, PID: 0x0C3F). The tool reads live telemetry (temperature, fan/pump RPMs) directly from the hardware, while the spec documents the commands and data structures required to do so.  
This work is based on research from the [FanControl.CorsairLink](https://github.com/evanmulawski/FanControl.CorsairLink) project, with corrections from live hardware testing.

## **Key Features**

* **Live Telemetry Utility:** A command-line tool to monitor and log hardware performance.  
* **Detailed Protocol Specification:** An unofficial but validated spec for developers.  
* **Standalone Operation:** Communicates directly with the hub via USB HID, no iCUE software required.  
* **Flexible Output:** View live data in the console or log it to a CSV file.

## **The Utility: icue\_link\_telemetry.py**

### **Requirements**

* Python 3.6+ and the hidapi library  
* A Corsair iCUE LINK System Hub connected via USB.  
* Administrative/root privileges for direct HID device access.

### **Installation & Usage**

1. **Clone the repository and install dependencies:**  
   git clone https://github.com/your-username/iCUE-LINK-Telemetry-Reader.git  
   cd iCUE-LINK-Telemetry-Reader  
   pip install hidapi

2. **Run the script:**  
   \# Print to console every 2 seconds  
   python icue\_link\_telemetry.py

   \# Log to a CSV file every 5 seconds  
   python icue\_link\_telemetry.py \-o telemetry.csv \-i 5

   *Note: May require sudo or Administrator privileges.* Press Ctrl+C to stop. For all options, run with \--help.

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