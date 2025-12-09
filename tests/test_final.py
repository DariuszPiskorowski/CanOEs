"""
Final test - using correct types for xlOpenPort
XLportHandle is typedef int in vxlapi.h
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_ubyte, c_int, byref, POINTER

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

# Define proper types
XLportHandle = c_int  # Confirmed: typedef int XLportHandle
XLaccess = c_uint64   # Confirmed: typedef unsigned __int64 XLaccess

print("=" * 60)
print("Correct Types Test")
print("=" * 60)

status = dll.xlOpenDriver()
print(f"xlOpenDriver: {status}")

# Setup
dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)
print(f"Channel index: {idx}")

channel_mask = XLaccess(1 << idx)
print(f"Channel mask: 0x{channel_mask.value:016X}")

# Define xlOpenPort properly
dll.xlOpenPort.argtypes = [
    POINTER(XLportHandle),  # pPortHandle
    ctypes.c_char_p,        # userName
    XLaccess,               # accessMask
    POINTER(XLaccess),      # permissionMask
    c_uint,                 # rxQueueSize
    c_uint,                 # xlInterfaceVersion
    c_uint                  # busType
]
dll.xlOpenPort.restype = c_int

# Open port
port_handle = XLportHandle(0)
permission_mask = XLaccess(channel_mask.value)
port_name = b"CanOEs"

print(f"\nBefore xlOpenPort:")
print(f"  port_handle: {port_handle.value}")
print(f"  permission_mask: 0x{permission_mask.value:016X}")

status = dll.xlOpenPort(
    byref(port_handle),
    port_name,
    channel_mask,
    byref(permission_mask),
    256,
    3,  # XL_INTERFACE_VERSION
    1   # XL_BUS_TYPE_CAN
)

print(f"\nAfter xlOpenPort:")
print(f"  status: {status}")
print(f"  port_handle: {port_handle.value}")
print(f"  permission_mask: 0x{permission_mask.value:016X}")

if status == 0 and permission_mask.value != 0:
    print("\n** Got init access! **")
    
    # Define FD config
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
    
    fd_conf = XLcanFdConf()
    fd_conf.arbitrationBitRate = 500000
    fd_conf.sjwAbr = 2
    fd_conf.tseg1Abr = 6
    fd_conf.tseg2Abr = 3
    fd_conf.dataBitRate = 2000000
    fd_conf.sjwDbr = 2
    fd_conf.tseg1Dbr = 6
    fd_conf.tseg2Dbr = 3
    
    # Try FD config
    dll.xlCanFdSetConfiguration.argtypes = [XLportHandle, XLaccess, ctypes.POINTER(XLcanFdConf)]
    dll.xlCanFdSetConfiguration.restype = c_int
    
    status = dll.xlCanFdSetConfiguration(port_handle, channel_mask, byref(fd_conf))
    print(f"\nxlCanFdSetConfiguration: {status}")
    
    if status == 0:
        print("*** CAN FD CONFIGURATION SUCCESS! ***")
    elif status == 101:
        print("-> XL_ERR_NO_LICENSE")
        
        # Let's check if there's a different function for checking FD license
        print("\nChecking for other FD-related functions...")
        
        # Try activating as CAN FD
        dll.xlActivateChannel.argtypes = [XLportHandle, XLaccess, c_uint, c_uint]
        dll.xlActivateChannel.restype = c_int
        
        XL_BUS_TYPE_CAN = 1
        XL_ACTIVATE_NONE = 0
        
        status = dll.xlActivateChannel(port_handle, channel_mask, XL_BUS_TYPE_CAN, XL_ACTIVATE_NONE)
        print(f"xlActivateChannel (CAN classic): {status}")
        
        if status == 0:
            print("CAN Classic works - only FD license is missing")
    else:
        print(f"-> Unknown error: {status}")
    
    dll.xlClosePort(port_handle)
    print("\nPort closed")
else:
    print(f"\n** Failed to get init access **")
    print(f"status={status}")
    if port_handle.value > 0:
        dll.xlClosePort(port_handle)

dll.xlCloseDriver()
print("\nDone")
