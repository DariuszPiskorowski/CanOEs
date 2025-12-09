"""
Test comparing different XLcanFdConf structures
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_ubyte, c_int, c_ushort, byref, sizeof

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

# Structure 1 - all c_uint (jak w test_final.py - WORKS)
class XLcanFdConf_AllUint(Structure):
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

# Structure 2 - mixed types (jak w vn1640a_can.py)
class XLcanFdConf_Mixed(Structure):
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

print("Structure sizes:")
print(f"  XLcanFdConf_AllUint: {sizeof(XLcanFdConf_AllUint)} bytes")
print(f"  XLcanFdConf_Mixed:   {sizeof(XLcanFdConf_Mixed)} bytes")

# Open driver
status = dll.xlOpenDriver()
print(f"\nxlOpenDriver: {status}")

# Get channel
dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)

channel_mask = c_uint64(1 << idx)
print(f"Channel mask: 0x{channel_mask.value:016X}")

def test_struct(name, conf_class):
    print(f"\n{'='*50}")
    print(f"Testing {name}")
    print(f"{'='*50}")
    
    port_handle = c_int(0)
    permission_mask = c_uint64(channel_mask.value)
    
    status = dll.xlOpenPort(
        byref(port_handle),
        b"FDTest",
        channel_mask,
        byref(permission_mask),
        256,
        3,
        1
    )
    print(f"xlOpenPort: status={status}, handle={port_handle.value}, perm=0x{permission_mask.value:X}")
    
    if status == 0 and permission_mask.value != 0:
        conf = conf_class()
        conf.arbitrationBitRate = 500000
        conf.dataBitRate = 2000000
        
        # Set timing for both structures
        if hasattr(conf, 'sjwAbr'):
            conf.sjwAbr = 2
            conf.tseg1Abr = 6
            conf.tseg2Abr = 3
            conf.sjwDbr = 2
            conf.tseg1Dbr = 6
            conf.tseg2Dbr = 3
        
        status = dll.xlCanFdSetConfiguration(port_handle, channel_mask, byref(conf))
        print(f"xlCanFdSetConfiguration: {status}")
        
        if status == 0:
            print("*** SUCCESS ***")
        elif status == 101:
            print("NO_LICENSE")
        else:
            print(f"Error: {status}")
        
        dll.xlClosePort(port_handle)
        return status
    else:
        if port_handle.value > 0:
            dll.xlClosePort(port_handle)
        return -1

# Test both structures
result1 = test_struct("XLcanFdConf_AllUint", XLcanFdConf_AllUint)
result2 = test_struct("XLcanFdConf_Mixed", XLcanFdConf_Mixed)

dll.xlCloseDriver()

print(f"\n{'='*50}")
print("Results:")
print(f"  AllUint: {result1} {'(SUCCESS)' if result1 == 0 else '(FAIL)'}")
print(f"  Mixed:   {result2} {'(SUCCESS)' if result2 == 0 else '(FAIL)'}")
