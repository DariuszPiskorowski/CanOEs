"""
Test xlCanTransmitEx z różnymi sposobami przekazywania argumentów
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_ubyte, c_ushort, c_int, byref, sizeof, POINTER

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

# Typy
XLportHandle = c_int
XLaccess = c_uint64

# TX Event - najprostsza wersja
class XLcanTxEvent(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

# FD Config
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

print(f"sizeof(XLcanTxEvent) = {sizeof(XLcanTxEvent)}")

# Open driver
status = dll.xlOpenDriver()
print(f"xlOpenDriver: {status}")

# Get channel
dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)
print(f"Channel index: {idx}")

access_mask = XLaccess(1 << idx)
print(f"Access mask: 0x{access_mask.value:X}")

# Define function signatures explicitly
dll.xlOpenPort.argtypes = [POINTER(XLportHandle), ctypes.c_char_p, XLaccess, POINTER(XLaccess), c_uint, c_uint, c_uint]
dll.xlOpenPort.restype = c_int

dll.xlCanFdSetConfiguration.argtypes = [XLportHandle, XLaccess, POINTER(XLcanFdConf)]
dll.xlCanFdSetConfiguration.restype = c_int

dll.xlActivateChannel.argtypes = [XLportHandle, XLaccess, c_uint, c_uint]
dll.xlActivateChannel.restype = c_int

dll.xlCanTransmitEx.argtypes = [XLportHandle, XLaccess, c_uint, POINTER(c_uint), POINTER(XLcanTxEvent)]
dll.xlCanTransmitEx.restype = c_int

dll.xlDeactivateChannel.argtypes = [XLportHandle, XLaccess]
dll.xlClosePort.argtypes = [XLportHandle]

# Open port
port = XLportHandle(0)
perm = XLaccess(access_mask.value)

status = dll.xlOpenPort(byref(port), b"FDTest", access_mask, byref(perm), 256, 3, 1)
print(f"\nxlOpenPort: status={status}, port={port.value}, perm=0x{perm.value:X}")

if status == 0 and perm.value != 0:
    # FD config
    fd_conf = XLcanFdConf()
    fd_conf.arbitrationBitRate = 500000
    fd_conf.sjwAbr = 2
    fd_conf.tseg1Abr = 6
    fd_conf.tseg2Abr = 3
    fd_conf.dataBitRate = 2000000
    fd_conf.sjwDbr = 2
    fd_conf.tseg1Dbr = 6
    fd_conf.tseg2Dbr = 3
    
    status = dll.xlCanFdSetConfiguration(port, access_mask, byref(fd_conf))
    print(f"xlCanFdSetConfiguration: {status}")
    
    # Activate
    status = dll.xlActivateChannel(port, access_mask, 1, 8)
    print(f"xlActivateChannel: {status}")
    
    if status == 0:
        # Prepare TX event
        tx = XLcanTxEvent()
        tx.canId = 0x123
        tx.msgFlags = 0x0001  # XL_CAN_TXMSG_FLAG_EDL (FD frame)
        tx.dlc = 8
        for i in range(8):
            tx.data[i] = 0x11 + i
        
        # Try different msgCtr values
        for msgCtr_val in [0, 1]:
            msgCtr = c_uint(msgCtr_val)
            status = dll.xlCanTransmitEx(port, access_mask, msgCtr_val, byref(msgCtr), byref(tx))
            print(f"xlCanTransmitEx (msgCtr={msgCtr_val}): status={status}")
            
            if status == 0:
                print("*** SUKCES! ***")
                break
        
        # Spróbuj bez flagi FD (klasyczna ramka przez FD port)
        print("\nPróba z klasyczną ramką (msgFlags=0):")
        tx.msgFlags = 0
        msgCtr = c_uint(1)
        status = dll.xlCanTransmitEx(port, access_mask, 1, byref(msgCtr), byref(tx))
        print(f"xlCanTransmitEx (classic): status={status}")
    
    dll.xlDeactivateChannel(port, access_mask)
    dll.xlClosePort(port)

dll.xlCloseDriver()
print("\nDone")
