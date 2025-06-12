# Corsair iCUE Link Hub USB HID Protocol Specification

**Version:** 2.1  
**Date:** June 11, 2025  
**Status:** Verified Implementation with Corrections  
**Reference:** Based on [FanControl.CorsairLink](https://github.com/EvanMulawski/FanControl.CorsairLink) and live testing

## Device Information

- **USB Vendor ID:** 0x1B1C (Corsair)
- **USB Product ID:** 0x0C3F (iCUE Link System Hub)
- **Interface:** USB HID (Human Interface Device)
- **Usage Page:** 0xFF42 (Corsair vendor-specific)

## HID Communication Parameters

- **Output Report Size:** 513 bytes (including 1-byte Report ID)
- **Input Report Size:** 512 bytes
- **Communication Method:** HID Output/Input reports via interrupt transfers

## Packet Structure

### Command Packet Format (Host → Hub)

```
Byte 0:     Report ID (0x00)
Byte 1-3:   [0x00, 0x00, 0x01]  # Fixed header
Byte 4+:    Command bytes
Byte N+:    Data bytes (if any)
Remaining:  Zero padding to 513 bytes
```

### Response Packet Format (Hub → Host)

```
Byte 0:     Report ID (usually 0x00)
Byte 1:     Status Code (0x00 = success)
Byte 2-3:   Reserved
Byte 4-5:   Data Type Identifier (2 bytes)
Byte 6+:    Payload data (format varies by endpoint)
```

## Protocol Commands

### Device Mode Control

- **Enter Software Mode:** `[0x01, 0x03, 0x00, 0x02]`
- **Enter Hardware Mode:** `[0x01, 0x03, 0x00, 0x01]`

### Endpoint Management

- **Open Endpoint:** `[0x0d, 0x01]` + endpoint_id
- **Close Endpoint:** `[0x05, 0x01, 0x01]` + endpoint_id
- **Read Data:** `[0x08, 0x01]`

### Endpoint Identifiers

- **Speed Sensors:** `[0x17]`
- **Temperature Sensors:** `[0x21]`
- **Sub-devices:** `[0x36]`

### Data Type Identifiers

- **Speed Data:** `[0x25, 0x00]`
- **Temperature Data:** `[0x10, 0x00]`
- **Sub-device Data:** `[0x21, 0x00]`

## Data Parsing

### Speed Sensor Data

Response structure after successful read:

```
Byte 6:     Sensor count (N)
Byte 7+:    N × 3-byte sensor blocks
```

Each 3-byte sensor block:
```
Byte 0:     Status (0x00 = available, other = unavailable)
Byte 1-2:   RPM value (16-bit little-endian signed integer)
```

### Temperature Sensor Data **[CORRECTED]**

**⚠️ IMPORTANT:** Temperature data does NOT use the standard sensor block format.

Temperature response structure after successful read:

```
Byte 0:     Report ID
Byte 1:     Status Code
Byte 2-3:   Reserved
Byte 4-5:   Data Type [0x10, 0x00]
Byte 6-10:  Unknown/Reserved
Byte 11-12: Temperature value (16-bit little-endian, units: 0.1°C)
Byte 13+:   Additional data (format unknown)
```

**Temperature Conversion:** `temperature_celsius = raw_value / 10.0`

**Note:** Unlike speed sensors, temperature data appears at fixed byte positions rather than following the sensor block format. This inconsistency suggests the temperature endpoint may be an older or different implementation.

## Communication Flow

### Reading Sensor Data

1. Send Close Endpoint command for target endpoint
2. Send Open Endpoint command for target endpoint
3. Send Read command
4. Poll for response with matching data type identifier
5. Send Close Endpoint command
6. Parse response payload (using appropriate format for endpoint type)

## Error Handling

- **Status Code 0x00:** Success
- **Status Code 0x03:** Incorrect mode (device needs mode switch)
- **Other codes:** Various errors (device unavailable, invalid command, etc.)

## Implementation Requirements

### Critical Requirements

- Device must be in Software Mode before sensor queries
- Endpoints must be properly opened/closed for each transaction
- Response polling should include data type verification
- All multi-byte values use little-endian byte order
- **Temperature parsing uses fixed byte positions, not sensor blocks**

### Timing Considerations

- Include 50ms delays between commands to ensure device processing
- Use 1-second timeout for response polling
- Recommended polling interval: 1-2 seconds for continuous monitoring

## Device Sensor Mapping

Typical sensor array layout for **Speed Sensors**:

- **Index 1:** Pump RPM
- **Index 13-15:** Fan RPMs (Fan 1, Fan 2, Fan 3)

**Temperature Sensors:** Fixed position at bytes 11-12 of response packet

## Implementation Notes

### Endpoint Format Differences

The protocol appears to use different data formats for different endpoint types:

- **Speed Endpoint (0x17):** Uses structured sensor blocks with count + status + value format
- **Temperature Endpoint (0x21):** Uses fixed-position format with temperature at bytes 11-12

This inconsistency suggests the protocol evolved over time or different endpoints were implemented by different teams/versions.

### Compatibility Considerations

When implementing this protocol:
1. Always validate the data type identifier in responses
2. Use endpoint-specific parsing logic rather than assuming uniform format
3. Include robust error handling for malformed responses
4. Test with actual hardware to verify parsing assumptions

## Changelog

### Version 2.1 (June 11, 2025)
- **BREAKING:** Corrected temperature data parsing format
- Added Report ID to command packet structure
- Clarified endpoint-specific data formats
- Added implementation notes about format inconsistencies
- Updated packet size requirements

### Version 2.0 (Previous)
- Initial specification based on FanControl.CorsairLink analysis

## Notes

This protocol specification is derived from the [FanControl.CorsairLink](https://github.com/EvanMulawski/FanControl.CorsairLink) project by Evan Mulawski, with corrections based on live testing and implementation validation.

The temperature data format inconsistency discovered in v2.1 highlights the importance of testing protocol implementations against actual hardware rather than relying solely on reverse-engineered documentation.