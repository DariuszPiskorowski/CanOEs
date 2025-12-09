"""
Test xlCanTransmitEx - V4 interface i różne parametry
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_ubyte, c_int, c_ushort, byref, sizeof

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

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

# XL_CAN_TX_MSG from vxlapi.h
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

print(f"XL_CAN_TX_MSG size: {sizeof(XL_CAN_TX_MSG)} bytes")

status = dll.xlOpenDriver()
print(f"xlOpenDriver: {status}")

dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)
channel_mask = c_uint64(1 << idx)

print(f"\nTesting with V4 interface...")

port_handle = c_int(0)
permission_mask = c_uint64(channel_mask.value)

# Try V4 interface
status = dll.xlOpenPort(
    byref(port_handle),
    b"FDTransmit",
    channel_mask,
    byref(permission_mask),
    256,
    4,  # V4 interface!
    1   # CAN
)
print(f"xlOpenPort (V4): {status}, handle={port_handle.value}, perm=0x{permission_mask.value:X}")

if status == 0 and permission_mask.value != 0:
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
    
    # Activate
    status = dll.xlActivateChannel(port_handle, channel_mask, 1, 8)
    print(f"xlActivateChannel: {status}")
    
    if status == 0:
        # Test 1: XL_CAN_TX_MSG directly
        print("\n--- Test 1: XL_CAN_TX_MSG directly ---")
        tx = XL_CAN_TX_MSG()
        tx.canId = 0x123
        tx.msgFlags = 0x0003  # EDL | BRS
        tx.dlc = 8
        for i in range(8):
            tx.data[i] = i + 1
        
        msg_count = c_uint(1)
        status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx))
        print(f"xlCanTransmitEx: {status} (msg_count={msg_count.value})")
        
        # Test 2: Try with msgFlags = 0 (classic CAN frame through FD interface)
        print("\n--- Test 2: Classic CAN through FD interface ---")
        tx2 = XL_CAN_TX_MSG()
        tx2.canId = 0x456
        tx2.msgFlags = 0  # No FD flags - classic CAN
        tx2.dlc = 4
        for i in range(4):
            tx2.data[i] = 0xAA
        
        msg_count.value = 1
        status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx2))
        print(f"xlCanTransmitEx: {status}")
        
        # Test 3: Try with only EDL flag (no BRS)
        print("\n--- Test 3: FD without BRS ---")
        tx3 = XL_CAN_TX_MSG()
        tx3.canId = 0x789
        tx3.msgFlags = 0x0001  # Only EDL
        tx3.dlc = 8
        for i in range(8):
            tx3.data[i] = 0xBB
        
        msg_count.value = 1
        status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx3))
        print(f"xlCanTransmitEx: {status}")
        
    dll.xlDeactivateChannel(port_handle, channel_mask)
    dll.xlClosePort(port_handle)

dll.xlCloseDriver()
print("\nDone")
