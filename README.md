# CanOEs - CAN Interface for Vector VN1640A

Python GUI application for CAN/CAN FD communication using Vector VN1640A hardware.

## Features

- **CAN Classic** - 11-bit and 29-bit (Extended) IDs, up to 8 bytes
- **CAN FD** - Up to 64 bytes with BRS support (requires Vector license)
- **GUI Interface** - Send/receive messages, filters, periodic transmission
- **4 Channel Support** - Switch between channels 1-4

## Requirements

- Windows OS
- Vector VN1640A hardware
- Vector XL Driver Library (vxlapi64.dll)
- Python 3.9+

## Files

- `vn1640a_can.py` - Core CAN interface library
- `can_gui.py` - Tkinter GUI application
- `detect_vector_usb.py` - USB device detection utility

## Usage

### GUI Application
```powershell
py can_gui.py
```

### Programmatic Usage
```python
from vn1640a_can import VN1640A

# CAN Classic
vn = VN1640A()
vn.open()
vn.start(channel=1)
vn.send(0x100, [0x01, 0x02, 0x03, 0x04])
msg = vn.receive(timeout_ms=1000)
vn.stop()
vn.close()

# CAN FD (requires license)
vn = VN1640A()
vn.open()
vn.start_fd(channel=1)
vn.send_fd(0x100, [0x01]*32, brs=True)
vn.stop()
vn.close()
```

## Configuration

- **Baudrate**: 125k, 250k, 500k, 1M
- **Channel**: 1-4 (Vector numbering)
- **Extended ID**: 29-bit addressing support

## License

MIT
