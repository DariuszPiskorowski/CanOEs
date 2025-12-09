"""Test CAN - V3 vs V4 interface"""
from ctypes import *

dll = WinDLL('vxlapi64.dll')

XL_SUCCESS = 0
XL_HWTYPE_VN1640 = 59
XL_BUS_TYPE_CAN = 0x00000001
XL_INTERFACE_VERSION = 3  # V3 - stare API
XL_INTERFACE_VERSION_V4 = 4  # V4 - nowe API dla FD
XL_ACTIVATE_RESET_CLOCK = 8
XL_TRANSMIT_MSG = 0x0A

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

# ============================================
# TEST 1: Interface V3 (stare API)
# ============================================
print("\n" + "="*50)
print("TEST 1: Interface V3 + xlCanTransmit")
print("="*50)

channel_mask = c_uint64(mask)
permission_mask = c_uint64(mask)
port_handle = c_int(-1)

status = dll.xlOpenPort(
    byref(port_handle),
    b"TestV3",
    channel_mask,
    byref(permission_mask),
    c_uint(256),
    c_uint(XL_INTERFACE_VERSION),  # V3
    c_uint(XL_BUS_TYPE_CAN)
)
print(f"xlOpenPort (V3): {status}")

# Ustaw baudrate
status = dll.xlCanSetChannelBitrate(port_handle, channel_mask, c_uint(500000))
print(f"xlCanSetChannelBitrate: {status}")

status = dll.xlActivateChannel(port_handle, channel_mask, c_uint(XL_BUS_TYPE_CAN), c_uint(XL_ACTIVATE_RESET_CLOCK))
print(f"xlActivateChannel: {status}")

event = XLevent()
event.tag = XL_TRANSMIT_MSG
event.tagData.msg.id = 0x100
event.tagData.msg.dlc = 4
event.tagData.msg.data[0] = 0x11
event.tagData.msg.data[1] = 0x22
event.tagData.msg.data[2] = 0x33
event.tagData.msg.data[3] = 0x44

msg_count = c_uint(1)
status = dll.xlCanTransmit(port_handle, channel_mask, byref(msg_count), byref(event))
print(f"xlCanTransmit: {status}")

if status == 0:
    print("[OK] CAN klasyczny działa z V3!")

dll.xlDeactivateChannel(port_handle, channel_mask)
dll.xlClosePort(port_handle)

# ============================================
# TEST 2: Interface V4 + xlCanTransmitEx
# ============================================
print("\n" + "="*50)
print("TEST 2: Interface V4 + xlCanTransmitEx")
print("="*50)

channel_mask = c_uint64(mask)
permission_mask = c_uint64(mask)
port_handle = c_int(-1)

status = dll.xlOpenPort(
    byref(port_handle),
    b"TestV4",
    channel_mask,
    byref(permission_mask),
    c_uint(256),
    c_uint(XL_INTERFACE_VERSION_V4),  # V4
    c_uint(XL_BUS_TYPE_CAN)
)
print(f"xlOpenPort (V4): {status}")

# Dla V4 trzeba użyć xlCanFdSetConfiguration
class XLcanFdConf(Structure):
    _pack_ = 1
    _fields_ = [
        ("arbitrationBitRate", c_uint),
        ("sjwAbr", c_ubyte),
        ("tseg1Abr", c_ubyte),
        ("tseg2Abr", c_ubyte),
        ("reserved1", c_ubyte),
        ("dataBitRate", c_uint),
        ("sjwDbr", c_ubyte),
        ("tseg1Dbr", c_ubyte),
        ("tseg2Dbr", c_ubyte),
        ("reserved2", c_ubyte),
        ("reserved3", c_ubyte * 2),
        ("options", c_ushort),
        ("reserved4", c_ubyte * 8),
    ]

fd_conf = XLcanFdConf()
fd_conf.arbitrationBitRate = 500000
fd_conf.dataBitRate = 2000000
status = dll.xlCanFdSetConfiguration(port_handle, channel_mask, byref(fd_conf))
print(f"xlCanFdSetConfiguration: {status} (101=NO_LICENSE)")

status = dll.xlActivateChannel(port_handle, channel_mask, c_uint(XL_BUS_TYPE_CAN), c_uint(XL_ACTIVATE_RESET_CLOCK))
print(f"xlActivateChannel: {status}")

tx = XLcanTxEvent()
tx.tag = 0x0400  # może to jest tag RX nie TX?
tx.canId = 0x100
tx.msgFlags = 0
tx.dlc = 4
tx.data[0] = 0x11

msg_count = c_uint(1)
status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx))
print(f"xlCanTransmitEx (tag=0x0400): {status}")

tx.tag = 0x0401
status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx))
print(f"xlCanTransmitEx (tag=0x0401): {status}")

tx.tag = 0x0440  # XL_CAN_EV_TAG_TX_REQUEST?
status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx))
print(f"xlCanTransmitEx (tag=0x0440): {status}")

tx.tag = 0  # bez taga
status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx))
print(f"xlCanTransmitEx (tag=0): {status}")

dll.xlDeactivateChannel(port_handle, channel_mask)
dll.xlClosePort(port_handle)

dll.xlCloseDriver()
print("\n[KONIEC]")
