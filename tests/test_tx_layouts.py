"""
Test XLcanTxEvent - sprawdzenie różnych rozmiarów/layoutów struktury
Może XLcanTxEvent też wymaga innego layoutu jak XLcanFdConf?
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_ubyte, c_ushort, c_int, byref, sizeof, POINTER

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

# Wariant 1: Oryginalny (80 bajtów)
class XLcanTxEvent_v1(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

# Wariant 2: Z tagiem na początku (jak XLcanRxEvent)
class XLcanTxEvent_v2(Structure):
    _pack_ = 1
    _fields_ = [
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("channelIndex", c_ubyte),
        ("reserved0", c_ubyte * 3),
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

# Wariant 3: Pełna struktura z size na początku
class XLcanTxEvent_v3(Structure):
    _pack_ = 1
    _fields_ = [
        ("size", c_uint),
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("channelIndex", c_ubyte),
        ("reserved0", c_ubyte * 3),
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

# Wariant 4: Bez _pack_
class XLcanTxEvent_v4(Structure):
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

# FD Config (działająca wersja)
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

print("Rozmiary struktur XLcanTxEvent:")
print(f"  v1 (oryginalna):     {sizeof(XLcanTxEvent_v1)} bajtów")
print(f"  v2 (z tagiem):       {sizeof(XLcanTxEvent_v2)} bajtów")
print(f"  v3 (z size+tag):     {sizeof(XLcanTxEvent_v3)} bajtów")
print(f"  v4 (bez _pack_):     {sizeof(XLcanTxEvent_v4)} bajtów")

status = dll.xlOpenDriver()
print(f"\nxlOpenDriver: {status}")

dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)
access = c_uint64(1 << idx)

def test_tx_struct(name, tx_class, setup_func=None):
    print(f"\n{'='*50}")
    print(f"Test: {name} ({sizeof(tx_class)} bajtów)")
    print(f"{'='*50}")
    
    port = c_int(0)
    perm = c_uint64(access.value)
    
    status = dll.xlOpenPort(byref(port), b"Test", access, byref(perm), 256, 3, 1)
    if status != 0 or perm.value == 0:
        print(f"xlOpenPort failed: {status}")
        return
    
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
        tx = tx_class()
        
        # Setup
        if setup_func:
            setup_func(tx)
        else:
            tx.canId = 0x123
            tx.msgFlags = 0x0001  # EDL
            tx.dlc = 8
            for i in range(8):
                tx.data[i] = 0x11 + i
        
        msgCnt = c_uint(0)
        status = dll.xlCanTransmitEx(port, access, 1, byref(msgCnt), byref(tx))
        print(f"xlCanTransmitEx: {status} (sent={msgCnt.value})")
        
        if status == 0:
            print("*** SUKCES! ***")
    
    dll.xlDeactivateChannel(port, access)
    dll.xlClosePort(port)

def setup_v2(tx):
    tx.tag = 0x0440  # XL_CAN_EV_TAG_TX_MSG
    tx.transId = 0
    tx.channelIndex = 0
    tx.canId = 0x123
    tx.msgFlags = 0x0001
    tx.dlc = 8
    for i in range(8):
        tx.data[i] = 0x11 + i

def setup_v3(tx):
    tx.size = sizeof(type(tx))
    tx.tag = 0x0440
    tx.transId = 0
    tx.channelIndex = 0
    tx.canId = 0x123
    tx.msgFlags = 0x0001
    tx.dlc = 8
    for i in range(8):
        tx.data[i] = 0x11 + i

test_tx_struct("v1 - oryginalna", XLcanTxEvent_v1)
test_tx_struct("v2 - z tagiem", XLcanTxEvent_v2, setup_v2)
test_tx_struct("v3 - z size+tag", XLcanTxEvent_v3, setup_v3)
test_tx_struct("v4 - bez _pack_", XLcanTxEvent_v4)

dll.xlCloseDriver()
print("\nDone")
