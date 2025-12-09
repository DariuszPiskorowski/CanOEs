"""Test różnych wariantów struktury XLcanTxEvent"""
from ctypes import *
import time

dll = WinDLL('vxlapi64.dll')

XL_SUCCESS = 0
XL_HWTYPE_VN1640 = 59
XL_BUS_TYPE_CAN = 0x00000001
XL_INTERFACE_VERSION_V4 = 4
XL_ACTIVATE_RESET_CLOCK = 8
XL_CAN_TXMSG_FLAG_EDL = 0x0001

# Wariant 1: Oryginalna struktura
class XLcanTxEvent_v1(Structure):
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

# Wariant 2: Z XL_CAN_TX_MSG wewnątrz
class XL_CAN_TX_MSG(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

class XLcanTxEvent_v2(Structure):
    _pack_ = 1
    _fields_ = [
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("channelIndex", c_ubyte),
        ("reserved", c_ubyte * 3),
        ("tagData", XL_CAN_TX_MSG),
    ]

# Wariant 3: Bez _pack_
class XLcanTxEvent_v3(Structure):
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

print(f"Rozmiar v1 (pack=1): {sizeof(XLcanTxEvent_v1)}")
print(f"Rozmiar v2 (nested): {sizeof(XLcanTxEvent_v2)}")
print(f"Rozmiar v3 (no pack): {sizeof(XLcanTxEvent_v3)}")

# Według dokumentacji Vector: sizeof powinien być 88 bajtów
# tag(2) + transId(2) + channelIndex(1) + reserved(3) + canId(4) + msgFlags(4) + dlc(1) + reserved(7) + data(64) = 88

dll.xlOpenDriver()
dll.xlGetChannelMask.restype = c_uint64
mask = dll.xlGetChannelMask(c_int(XL_HWTYPE_VN1640), c_int(0), c_int(0))

channel_mask = c_uint64(mask)
permission_mask = c_uint64(mask)
port_handle = c_int(-1)

status = dll.xlOpenPort(
    byref(port_handle),
    b"TestFD2",
    channel_mask,
    byref(permission_mask),
    c_uint(256),
    c_uint(XL_INTERFACE_VERSION_V4),
    c_uint(XL_BUS_TYPE_CAN)
)
print(f"\nxlOpenPort: {status}")

status = dll.xlActivateChannel(port_handle, channel_mask, c_uint(XL_BUS_TYPE_CAN), c_uint(XL_ACTIVATE_RESET_CLOCK))
print(f"xlActivateChannel: {status}")

# Test każdego wariantu
for name, cls in [("v1", XLcanTxEvent_v1), ("v2", XLcanTxEvent_v2), ("v3", XLcanTxEvent_v3)]:
    print(f"\n--- Test {name} ---")
    tx = cls()
    tx.tag = 0x0401  # XL_CAN_EV_TAG_TX_OK
    
    if name == "v2":
        tx.tagData.canId = 0x100
        tx.tagData.msgFlags = 0  # klasyczny CAN
        tx.tagData.dlc = 4
        tx.tagData.data[0] = 0x11
        tx.tagData.data[1] = 0x22
    else:
        tx.canId = 0x100
        tx.msgFlags = 0  # klasyczny CAN
        tx.dlc = 4
        tx.data[0] = 0x11
        tx.data[1] = 0x22
    
    msg_count = c_uint(1)
    status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx))
    print(f"xlCanTransmitEx status: {status}")

dll.xlDeactivateChannel(port_handle, channel_mask)
dll.xlClosePort(port_handle)
dll.xlCloseDriver()
print("\n[OK] Zamknięto")
