"""
Test - użyj xlCanTransmit zamiast xlCanTransmitEx
Może xlCanTransmitEx wymaga czegoś innego?
"""
import ctypes
from ctypes import Structure, Union, c_uint, c_uint64, c_ubyte, c_ulong, c_ushort, c_int, c_void_p, byref, sizeof, POINTER

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

# Classic CAN structures
class s_xl_can_msg(Structure):
    _fields_ = [
        ("id", c_ulong),
        ("flags", c_ushort),
        ("dlc", c_ushort),
        ("res1", c_uint64),
        ("data", c_ubyte * 8),
        ("res2", c_uint64),
    ]

class s_xl_tag_data(Union):
    _fields_ = [
        ("msg", s_xl_can_msg),
    ]

class XLevent(Structure):
    _fields_ = [
        ("tag", c_ubyte),
        ("chanIndex", c_ubyte),
        ("transId", c_ushort),
        ("portHandle", c_ushort),
        ("flags", c_ubyte),
        ("reserved", c_ubyte),
        ("timeStamp", c_uint64),
        ("tagData", s_xl_tag_data),
    ]

# FD config
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

XL_TRANSMIT_MSG = 10

print("Test: xlCanTransmit with FD configured port")
print("=" * 50)

status = dll.xlOpenDriver()
print(f"xlOpenDriver: {status}")

dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)

channel_mask = c_uint64(1 << idx)
port_handle = c_int(0)
permission_mask = c_uint64(channel_mask.value)

# Open with V3 (for xlCanTransmit)
status = dll.xlOpenPort(
    byref(port_handle),
    b"ClassicTX",
    channel_mask,
    byref(permission_mask),
    256,
    3,  # V3
    1   # CAN
)
print(f"xlOpenPort (V3): status={status}, handle={port_handle.value}")

if status == 0 and permission_mask.value != 0:
    # Configure FD anyway
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
    
    # Activate
    status = dll.xlActivateChannel(port_handle, channel_mask, 1, 8)
    print(f"xlActivateChannel: {status}")
    
    if status == 0:
        # Send classic CAN through xlCanTransmit
        event = XLevent()
        event.tag = XL_TRANSMIT_MSG
        event.tagData.msg.id = 0x123
        event.tagData.msg.dlc = 8
        for i in range(8):
            event.tagData.msg.data[i] = i + 1
        
        msg_count = c_uint(1)
        status = dll.xlCanTransmit(port_handle, channel_mask, byref(msg_count), byref(event))
        print(f"\nxlCanTransmit (classic): {status}")
        
        if status == 0:
            print("*** Classic CAN TX works on FD configured port! ***")
    
    dll.xlDeactivateChannel(port_handle, channel_mask)
    dll.xlClosePort(port_handle)

print("\n" + "=" * 50)
print("Teraz test tylko V4 z xlCanTransmitEx na świeżym porcie")
print("=" * 50)

# Nowy test - pełna struktura TX event
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

port_handle = c_int(0)
permission_mask = c_uint64(channel_mask.value)

status = dll.xlOpenPort(
    byref(port_handle),
    b"FDOnlyTX",
    channel_mask,
    byref(permission_mask),
    256,
    4,  # V4
    1   # CAN
)
print(f"xlOpenPort (V4): status={status}, handle={port_handle.value}")

if status == 0 and permission_mask.value != 0:
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
    
    status = dll.xlActivateChannel(port_handle, channel_mask, 1, 8)
    print(f"xlActivateChannel: {status}")
    
    if status == 0:
        tx = XL_CAN_TX_MSG()
        tx.canId = 0x456
        tx.msgFlags = 0  # Try classic first through V4
        tx.dlc = 4
        for i in range(4):
            tx.data[i] = 0xCC
        
        msg_count = c_uint(1)
        
        # Ręcznie ustaw argumenty
        dll.xlCanTransmitEx.argtypes = [c_int, c_uint64, POINTER(c_uint), POINTER(XL_CAN_TX_MSG)]
        dll.xlCanTransmitEx.restype = c_int
        
        status = dll.xlCanTransmitEx(port_handle.value, channel_mask.value, byref(msg_count), byref(tx))
        print(f"\nxlCanTransmitEx (classic via V4): {status}")
        
        # FD frame
        tx.canId = 0x789
        tx.msgFlags = 0x0001  # EDL only
        tx.dlc = 12  # 12 bytes
        msg_count.value = 1
        status = dll.xlCanTransmitEx(port_handle.value, channel_mask.value, byref(msg_count), byref(tx))
        print(f"xlCanTransmitEx (FD EDL only): {status}")
        
        # FD + BRS
        tx.canId = 0xABC
        tx.msgFlags = 0x0003  # EDL + BRS
        tx.dlc = 8
        msg_count.value = 1
        status = dll.xlCanTransmitEx(port_handle.value, channel_mask.value, byref(msg_count), byref(tx))
        print(f"xlCanTransmitEx (FD EDL+BRS): {status}")
    
    dll.xlDeactivateChannel(port_handle, channel_mask)
    dll.xlClosePort(port_handle)

dll.xlCloseDriver()
print("\nDone")
