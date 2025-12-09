"""
Test xlCanTransmitEx z interfaceVersion=4
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_ubyte, c_int, byref, sizeof

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

class XLcanTxEvent(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

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

print("Test z interfaceVersion=4 (XL_INTERFACE_VERSION_V4)")
print("=" * 60)

status = dll.xlOpenDriver()
print(f"xlOpenDriver: {status}")

dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)
access = c_uint64(1 << idx)
print(f"Channel index: {idx}, access: 0x{access.value:X}")

# Test z V3
print("\n--- Test z interfaceVersion=3 ---")
port = c_int(0)
perm = c_uint64(access.value)

status = dll.xlOpenPort(byref(port), b"V3Test", access, byref(perm), 256, 3, 1)
print(f"xlOpenPort(V3): status={status}, port={port.value}, perm=0x{perm.value:X}")

if status == 0 and perm.value != 0:
    fd_conf = XLcanFdConf()
    fd_conf.arbitrationBitRate = 500000
    fd_conf.sjwAbr = 2
    fd_conf.tseg1Abr = 6
    fd_conf.tseg2Abr = 3
    fd_conf.dataBitRate = 2000000
    fd_conf.sjwDbr = 2
    fd_conf.tseg1Dbr = 6
    fd_conf.tseg2Dbr = 3
    
    status = dll.xlCanFdSetConfiguration(port, access, byref(fd_conf))
    print(f"xlCanFdSetConfiguration: {status}")
    
    status = dll.xlActivateChannel(port, access, 1, 8)
    print(f"xlActivateChannel: {status}")
    
    if status == 0:
        tx = XLcanTxEvent()
        tx.canId = 0x123
        tx.msgFlags = 0x0001  # EDL
        tx.dlc = 8
        for i in range(8):
            tx.data[i] = 0x11 + i
        
        msgCnt = c_uint(0)
        status = dll.xlCanTransmitEx(port, access, 1, byref(msgCnt), byref(tx))
        print(f"xlCanTransmitEx: {status}")
    
    dll.xlDeactivateChannel(port, access)
    dll.xlClosePort(port)

# Test z V4
print("\n--- Test z interfaceVersion=4 ---")
port = c_int(0)
perm = c_uint64(access.value)

status = dll.xlOpenPort(byref(port), b"V4Test", access, byref(perm), 256, 4, 1)
print(f"xlOpenPort(V4): status={status}, port={port.value}, perm=0x{perm.value:X}")

if status == 0 and perm.value != 0:
    fd_conf = XLcanFdConf()
    fd_conf.arbitrationBitRate = 500000
    fd_conf.sjwAbr = 2
    fd_conf.tseg1Abr = 6
    fd_conf.tseg2Abr = 3
    fd_conf.dataBitRate = 2000000
    fd_conf.sjwDbr = 2
    fd_conf.tseg1Dbr = 6
    fd_conf.tseg2Dbr = 3
    
    status = dll.xlCanFdSetConfiguration(port, access, byref(fd_conf))
    print(f"xlCanFdSetConfiguration: {status}")
    
    status = dll.xlActivateChannel(port, access, 1, 8)
    print(f"xlActivateChannel: {status}")
    
    if status == 0:
        tx = XLcanTxEvent()
        tx.canId = 0x123
        tx.msgFlags = 0x0001  # EDL
        tx.dlc = 8
        for i in range(8):
            tx.data[i] = 0x11 + i
        
        msgCnt = c_uint(0)
        status = dll.xlCanTransmitEx(port, access, 1, byref(msgCnt), byref(tx))
        print(f"xlCanTransmitEx: {status}")
        
        if status == 0:
            print("*** SUKCES! ***")
    
    dll.xlDeactivateChannel(port, access)
    dll.xlClosePort(port)
elif status == 0:
    print("Port opened but no permission!")
    dll.xlClosePort(port)

dll.xlCloseDriver()
print("\nDone")
