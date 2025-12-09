"""Test CAN FD - próba z różnymi nazwami aplikacji"""
from ctypes import *

dll = WinDLL('vxlapi64.dll')

XL_HWTYPE_VN1640 = 59
XL_BUS_TYPE_CAN = 0x00000001
XL_INTERFACE_VERSION_V4 = 4
XL_ACTIVATE_RESET_CLOCK = 8

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

dll.xlOpenDriver()
dll.xlGetChannelMask.restype = c_uint64
mask = dll.xlGetChannelMask(c_int(XL_HWTYPE_VN1640), c_int(0), c_int(0))

# Różne nazwy aplikacji do przetestowania
app_names = [
    b"CANoe",
    b"CANalyzer",
    b"Vector",
    b"VectorCANFD",
    b"xlCANFD",
    b"Kostia",
    b"KostiaCommander",
    b"CANFD",
    b"PythonCAN",
]

for app_name in app_names:
    channel_mask = c_uint64(mask)
    permission_mask = c_uint64(mask)
    port_handle = c_int(-1)
    
    status = dll.xlOpenPort(
        byref(port_handle),
        app_name,
        channel_mask,
        byref(permission_mask),
        c_uint(256),
        c_uint(XL_INTERFACE_VERSION_V4),
        c_uint(XL_BUS_TYPE_CAN)
    )
    
    if status == 0:
        fd_conf = XLcanFdConf()
        fd_conf.arbitrationBitRate = 500000
        fd_conf.dataBitRate = 2000000
        
        fd_status = dll.xlCanFdSetConfiguration(port_handle, channel_mask, byref(fd_conf))
        print(f"App: {app_name.decode():20} -> xlCanFdSetConfiguration: {fd_status}")
        
        dll.xlClosePort(port_handle)
    else:
        print(f"App: {app_name.decode():20} -> xlOpenPort failed: {status}")

dll.xlCloseDriver()
