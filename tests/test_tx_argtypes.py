"""
Test z pełnymi argtypes dla wszystkich funkcji
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_ubyte, c_int, c_ushort, c_void_p, byref, sizeof, POINTER

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

# Typy
XLportHandle = c_int
XLaccess = c_uint64
XLstatus = c_int

# Struktury
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

# Ustaw argtypes
dll.xlOpenDriver.restype = XLstatus

dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int

dll.xlOpenPort.argtypes = [
    POINTER(XLportHandle),  # pPortHandle
    ctypes.c_char_p,        # userName
    XLaccess,               # accessMask
    POINTER(XLaccess),      # permissionMask
    c_uint,                 # rxQueueSize
    c_uint,                 # xlInterfaceVersion
    c_uint                  # busType
]
dll.xlOpenPort.restype = XLstatus

dll.xlCanFdSetConfiguration.argtypes = [XLportHandle, XLaccess, POINTER(XLcanFdConf)]
dll.xlCanFdSetConfiguration.restype = XLstatus

dll.xlActivateChannel.argtypes = [XLportHandle, XLaccess, c_uint, c_uint]
dll.xlActivateChannel.restype = XLstatus

dll.xlCanTransmitEx.argtypes = [XLportHandle, XLaccess, POINTER(c_uint), c_void_p]
dll.xlCanTransmitEx.restype = XLstatus

dll.xlDeactivateChannel.argtypes = [XLportHandle, XLaccess]
dll.xlClosePort.argtypes = [XLportHandle]
dll.xlCloseDriver.restype = XLstatus

print("Starting test with proper argtypes...")

status = dll.xlOpenDriver()
print(f"xlOpenDriver: {status}")

idx = dll.xlGetChannelIndex(59, 0, 0)
print(f"xlGetChannelIndex: {idx}")

channel_mask = XLaccess(1 << idx)
port_handle = XLportHandle(0)
permission_mask = XLaccess(channel_mask.value)

status = dll.xlOpenPort(
    byref(port_handle),
    b"FDTest",
    channel_mask,
    byref(permission_mask),
    256,
    4,  # XL_INTERFACE_VERSION_V4
    1   # XL_BUS_TYPE_CAN
)
print(f"xlOpenPort: status={status}, handle={port_handle.value}, perm=0x{permission_mask.value:X}")

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
        # Spróbuj wysłać
        tx = XL_CAN_TX_MSG()
        tx.canId = 0x123
        tx.msgFlags = 0x0003  # EDL | BRS
        tx.dlc = 8
        for i in range(8):
            tx.data[i] = i + 1
        
        msg_count = c_uint(1)
        
        print(f"\nXL_CAN_TX_MSG size: {sizeof(tx)}")
        print(f"canId: 0x{tx.canId:08X}")
        print(f"msgFlags: 0x{tx.msgFlags:08X}")
        print(f"dlc: {tx.dlc}")
        
        status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx))
        print(f"\nxlCanTransmitEx: {status}")
        
        if status == 132:
            # Może problem w channel_mask - powinna być wartość, nie obiekt?
            print("\nTrying with channel_mask.value...")
            msg_count.value = 1
            status = dll.xlCanTransmitEx(port_handle, channel_mask.value, byref(msg_count), byref(tx))
            print(f"xlCanTransmitEx: {status}")
        
    dll.xlDeactivateChannel(port_handle, channel_mask)
    dll.xlClosePort(port_handle)

dll.xlCloseDriver()
print("\nDone")
