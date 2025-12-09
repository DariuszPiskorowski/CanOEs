"""
Test xlCanTransmitEx z różnymi strukturami XLcanTxEvent
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_ubyte, c_int, c_ushort, byref, sizeof

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

# Struktura 1 - obecna w vn1640a_can.py
class XLcanTxEvent_Current(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

# Struktura 2 - z dokumentacji Vector (XL_CAN_TX_MSG)
class XLcanTxEvent_V2(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("txAttemptConf", c_ubyte),
        ("reserved", c_ushort),
        ("data", c_ubyte * 64),
    ]

# Struktura 3 - pełna struktura XLcanTxEvent
class XL_CAN_TX_MSG(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("txAttemptConf", c_ubyte),
        ("reserved", c_ushort),
        ("data", c_ubyte * 64),
    ]

class XLcanTxEvent_Full(Structure):
    _pack_ = 1
    _fields_ = [
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("channelIndex", c_ubyte),
        ("reserved", c_ubyte * 3),
        ("tagData", XL_CAN_TX_MSG),
    ]

print("Structure sizes:")
print(f"  XLcanTxEvent_Current: {sizeof(XLcanTxEvent_Current)} bytes")
print(f"  XLcanTxEvent_V2:      {sizeof(XLcanTxEvent_V2)} bytes")
print(f"  XLcanTxEvent_Full:    {sizeof(XLcanTxEvent_Full)} bytes")

# CAN FD config structure
class XLcanFdConf(Structure):
    _pack_ = 1
    _fields_ = [
        ("arbitrationBitRate", c_uint),
        ("sjwAbr", c_uint),
        ("tseg1Abr", c_uint),
        ("tseg2Abr", c_uint),
        ("dataBitRate", c_uint),
        ("sjwDbr", c_uint),
        ("tseg1Dbr", c_uint),
        ("tseg2Dbr", c_uint),
        ("reserved", c_uint * 2),
    ]

# Open driver
status = dll.xlOpenDriver()
print(f"\nxlOpenDriver: {status}")

# Get channel
dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)

channel_mask = c_uint64(1 << idx)
print(f"Channel index: {idx}, mask: 0x{channel_mask.value:X}")

def test_transmit(name, tx_event_class, use_full=False):
    print(f"\n{'='*50}")
    print(f"Testing {name}")
    print(f"{'='*50}")
    
    port_handle = c_int(0)
    permission_mask = c_uint64(channel_mask.value)
    
    # Open port with V3 interface first to configure, then we'll use V4 for FD
    status = dll.xlOpenPort(
        byref(port_handle),
        b"TxTest",
        channel_mask,
        byref(permission_mask),
        256,
        3,  # V3
        1   # CAN
    )
    print(f"xlOpenPort: {status}, handle={port_handle.value}, perm=0x{permission_mask.value:X}")
    
    if status != 0 or permission_mask.value == 0:
        print("Failed to get permission")
        if port_handle.value > 0:
            dll.xlClosePort(port_handle)
        return -1
    
    # Configure FD
    fd_conf = XLcanFdConf()
    fd_conf.arbitrationBitRate = 500000
    fd_conf.sjwAbr = 2
    fd_conf.tseg1Abr = 6
    fd_conf.tseg2Abr = 3
    fd_conf.dataBitRate = 2000000
    fd_conf.sjwDbr = 2
    fd_conf.tseg1Dbr = 6
    fd_conf.tseg2Dbr = 3
    
    status = dll.xlCanFdSetConfiguration(port_handle, channel_mask, byref(fd_conf))
    print(f"xlCanFdSetConfiguration: {status}")
    
    if status != 0:
        dll.xlClosePort(port_handle)
        return status
    
    # Activate
    status = dll.xlActivateChannel(port_handle, channel_mask, 1, 8)
    print(f"xlActivateChannel: {status}")
    
    if status != 0:
        dll.xlClosePort(port_handle)
        return status
    
    # Create TX event
    if use_full:
        tx = tx_event_class()
        tx.tag = 0x0440  # XL_CAN_EV_TAG_TX_MSG
        tx.transId = 0
        tx.channelIndex = 0
        tx.tagData.canId = 0x123
        tx.tagData.msgFlags = 0x0001 | 0x0002  # EDL | BRS
        tx.tagData.dlc = 8
        for i in range(8):
            tx.tagData.data[i] = i + 1
    else:
        tx = tx_event_class()
        tx.canId = 0x123
        tx.msgFlags = 0x0001 | 0x0002  # EDL | BRS
        tx.dlc = 8
        for i in range(8):
            tx.data[i] = i + 1
    
    msg_count = c_uint(1)
    status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx))
    print(f"xlCanTransmitEx: {status}")
    
    if status == 0:
        print("*** TX SUCCESS! ***")
    elif status == 132:
        print("WRONG_PARAMETER")
    elif status == 14:
        print("NO_LICENSE")
    
    dll.xlDeactivateChannel(port_handle, channel_mask)
    dll.xlClosePort(port_handle)
    
    return status

# Test all structures
result1 = test_transmit("XLcanTxEvent_Current", XLcanTxEvent_Current)
result2 = test_transmit("XLcanTxEvent_V2", XLcanTxEvent_V2)
result3 = test_transmit("XLcanTxEvent_Full", XLcanTxEvent_Full, use_full=True)

dll.xlCloseDriver()

print(f"\n{'='*50}")
print("Results:")
print(f"  Current:  {result1}")
print(f"  V2:       {result2}")
print(f"  Full:     {result3}")
