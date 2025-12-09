"""Test CAN FD - sprawdzenie permission_mask vs channel_mask"""
from ctypes import *

dll = WinDLL('vxlapi64.dll')

XL_SUCCESS = 0
XL_HWTYPE_VN1640 = 59
XL_BUS_TYPE_CAN = 0x00000001
XL_INTERFACE_VERSION_V4 = 4
XL_ACTIVATE_RESET_CLOCK = 8

class XLcanTxEvent(Structure):
    _pack_ = 1
    _fields_ = [
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("channelIndex", c_ubyte),
        ("reserved1", c_ubyte * 3),
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved2", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

dll.xlOpenDriver()
dll.xlGetChannelMask.restype = c_uint64
mask = dll.xlGetChannelMask(c_int(XL_HWTYPE_VN1640), c_int(0), c_int(0))
print(f"Channel mask: 0x{mask:X}")

channel_mask = c_uint64(mask)
permission_mask = c_uint64(mask)
port_handle = c_int(-1)

status = dll.xlOpenPort(
    byref(port_handle),
    b"TestPerm",
    channel_mask,
    byref(permission_mask),
    c_uint(256),
    c_uint(XL_INTERFACE_VERSION_V4),
    c_uint(XL_BUS_TYPE_CAN)
)
print(f"xlOpenPort: {status}")
print(f"  channel_mask: 0x{channel_mask.value:X}")
print(f"  permission_mask (po xlOpenPort): 0x{permission_mask.value:X}")

status = dll.xlActivateChannel(port_handle, channel_mask, c_uint(XL_BUS_TYPE_CAN), c_uint(XL_ACTIVATE_RESET_CLOCK))
print(f"xlActivateChannel: {status}")

tx = XLcanTxEvent()
tx.tag = 0x0401
tx.canId = 0x100
tx.msgFlags = 0  # klasyczny CAN
tx.dlc = 4
tx.data[0] = 0x11
tx.data[1] = 0x22
tx.data[2] = 0x33
tx.data[3] = 0x44

msg_count = c_uint(1)

# Test 1: z channel_mask
print("\n--- Test z channel_mask ---")
status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx))
print(f"xlCanTransmitEx (channel_mask): {status}")

# Test 2: z permission_mask
print("\n--- Test z permission_mask ---")
msg_count.value = 1
status = dll.xlCanTransmitEx(port_handle, permission_mask, byref(msg_count), byref(tx))
print(f"xlCanTransmitEx (permission_mask): {status}")

# Test 3: użyj starego API xlCanTransmit (które działa)
print("\n--- Test xlCanTransmit (stare API) ---")

class XLcanMsg(Structure):
    _fields_ = [
        ('id', c_uint),
        ('flags', c_ushort),
        ('dlc', c_ushort),
        ('res1', c_uint64),
        ('data', c_ubyte * 8),
        ('res2', c_uint64),
    ]

class XLcanMsgTagData(Union):
    _fields_ = [
        ('msg', XLcanMsg),
    ]

class XLevent(Structure):
    _fields_ = [
        ('tag', c_ubyte),
        ('chanIndex', c_ubyte),
        ('transId', c_ushort),
        ('portHandle', c_ushort),
        ('flags', c_ubyte),
        ('reserved', c_ubyte),
        ('timeStamp', c_uint64),
        ('tagData', XLcanMsgTagData),
    ]

event = XLevent()
event.tag = 0x0A  # XL_TRANSMIT_MSG
event.tagData.msg.id = 0x100
event.tagData.msg.dlc = 4
event.tagData.msg.data[0] = 0x11
event.tagData.msg.data[1] = 0x22
event.tagData.msg.data[2] = 0x33
event.tagData.msg.data[3] = 0x44

msg_count.value = 1
status = dll.xlCanTransmit(port_handle, channel_mask, byref(msg_count), byref(event))
print(f"xlCanTransmit (stare API): {status}")

dll.xlDeactivateChannel(port_handle, channel_mask)
dll.xlClosePort(port_handle)
dll.xlCloseDriver()
print("\n[OK] Zamknięto")
