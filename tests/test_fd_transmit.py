"""
Test xlCanTransmitEx - sprawdzenie dokładnej sygnatury
Według dokumentacji Vector:
XLstatus xlCanTransmitEx(XLportHandle portHandle, XLaccess accessMask, 
                          unsigned int msgCnt, unsigned int* pMsgCntSent, 
                          XLcanTxEvent* pXlCanTxEvt)
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_ubyte, c_int, byref, sizeof, POINTER

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

XLportHandle = c_int
XLaccess = c_uint64

# XLcanTxEvent - z dokumentacji Vector XL Driver Library
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

print(f"sizeof(XLcanTxEvent) = {sizeof(XLcanTxEvent)}")

status = dll.xlOpenDriver()
print(f"xlOpenDriver: {status}")

dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)

access = XLaccess(1 << idx)
print(f"Access mask: 0x{access.value:X}")

# Explicit function signatures
dll.xlOpenPort.argtypes = [POINTER(XLportHandle), ctypes.c_char_p, XLaccess, POINTER(XLaccess), c_uint, c_uint, c_uint]
dll.xlOpenPort.restype = c_int

dll.xlCanFdSetConfiguration.argtypes = [XLportHandle, XLaccess, POINTER(XLcanFdConf)]
dll.xlCanFdSetConfiguration.restype = c_int

dll.xlActivateChannel.argtypes = [XLportHandle, XLaccess, c_uint, c_uint]
dll.xlActivateChannel.restype = c_int

# WAŻNE: Sprawdźmy różne sygnatury xlCanTransmitEx
# Wersja 1: msgCnt jako wartość, pMsgCntSent jako pointer
dll.xlCanTransmitEx.argtypes = [XLportHandle, XLaccess, c_uint, POINTER(c_uint), POINTER(XLcanTxEvent)]
dll.xlCanTransmitEx.restype = c_int

port = XLportHandle(0)
perm = XLaccess(access.value)

status = dll.xlOpenPort(byref(port), b"FDTest", access, byref(perm), 256, 3, 1)
print(f"\nxlOpenPort: status={status}, port={port.value}, perm=0x{perm.value:X}")

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
        tx.msgFlags = 0x0001 | 0x0002  # EDL + BRS
        tx.dlc = 8  # 8 bytes
        for i in range(8):
            tx.data[i] = 0x11 + i
        
        print("\n--- Test różnych wywołań xlCanTransmitEx ---")
        
        # Test 1: msgCnt=1, pMsgCntSent
        msgCntSent = c_uint(0)
        status = dll.xlCanTransmitEx(port, access, 1, byref(msgCntSent), byref(tx))
        print(f"Test 1 (msgCnt=1, &sent): status={status}, sent={msgCntSent.value}")
        
        # Test 2: Bez BRS
        tx.msgFlags = 0x0001  # Tylko EDL
        msgCntSent = c_uint(0)
        status = dll.xlCanTransmitEx(port, access, 1, byref(msgCntSent), byref(tx))
        print(f"Test 2 (EDL only): status={status}")
        
        # Test 3: DLC=15 (64 bajty)
        tx.dlc = 15
        for i in range(64):
            tx.data[i] = i
        msgCntSent = c_uint(0)
        status = dll.xlCanTransmitEx(port, access, 1, byref(msgCntSent), byref(tx))
        print(f"Test 3 (64 bytes): status={status}")
        
        # Test 4: Sprawdźmy czy problem jest w access mask
        print("\n--- Test z różnymi access mask ---")
        
        # Bezpośrednio wartość 1
        msgCntSent = c_uint(0)
        tx.dlc = 8
        tx.msgFlags = 0x0001
        
        # Użyj c_uint64(1) bezpośrednio
        status = dll.xlCanTransmitEx(port, c_uint64(1), 1, byref(msgCntSent), byref(tx))
        print(f"Test 4a (c_uint64(1)): status={status}")
        
        # Użyj access.value
        status = dll.xlCanTransmitEx(port, access.value, 1, byref(msgCntSent), byref(tx))
        print(f"Test 4b (access.value): status={status}")
        
    dll.xlDeactivateChannel(port, access)
    dll.xlClosePort(port)

dll.xlCloseDriver()
print("\nDone")
