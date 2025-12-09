"""
Test - może struktura XL_CAN_TX_MSG ma inne pola?
Sprawdzam różne kombinacje
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_ubyte, c_ushort, c_int, byref, sizeof

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

# Różne warianty - może reserved ma inny rozmiar?
# Dokumentacja mówi: data[XL_CAN_MAX_DATA_LEN] gdzie XL_CAN_MAX_DATA_LEN=64

# Wariant A: reserved[7] (current)
class TxEvent_A(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),         # 4
        ("msgFlags", c_uint),      # 4
        ("dlc", c_ubyte),          # 1
        ("reserved", c_ubyte * 7), # 7
        ("data", c_ubyte * 64),    # 64 = TOTAL 80
    ]

# Wariant B: reserved jako c_uint + padding
class TxEvent_B(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),         # 4
        ("msgFlags", c_uint),      # 4
        ("dlc", c_ubyte),          # 1
        ("reserved1", c_ubyte),    # 1
        ("reserved2", c_ushort),   # 2
        ("reserved3", c_uint),     # 4
        ("data", c_ubyte * 64),    # 64 = TOTAL 80
    ]

# Wariant C: txTagData w union
class XL_CAN_TX_MSG(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

class TxEvent_C(Structure):
    _pack_ = 1
    _fields_ = [
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("channelIndex", c_ubyte),
        ("reserved", c_ubyte * 3),
        ("txMsg", XL_CAN_TX_MSG),
    ]

# Wariant D: txMsgFlags jako ushort
class TxEvent_D(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_ushort),    # ushort zamiast uint!
        ("reserved0", c_ushort),
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

print("Rozmiary:")
print(f"  TxEvent_A: {sizeof(TxEvent_A)}")
print(f"  TxEvent_B: {sizeof(TxEvent_B)}")
print(f"  TxEvent_C: {sizeof(TxEvent_C)}")
print(f"  TxEvent_D: {sizeof(TxEvent_D)}")

status = dll.xlOpenDriver()
dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)
access = c_uint64(1 << idx)

def test(name, tx_class, setup=None):
    print(f"\n--- {name} ---")
    port = c_int(0)
    perm = c_uint64(access.value)
    
    status = dll.xlOpenPort(byref(port), b"Test", access, byref(perm), 256, 3, 1)
    if status != 0 or perm.value == 0:
        print(f"OpenPort failed")
        return
    
    fd = XLcanFdConf()
    fd.arbitrationBitRate = 500000
    fd.sjwAbr = 2
    fd.tseg1Abr = 6
    fd.tseg2Abr = 3
    fd.dataBitRate = 2000000
    fd.sjwDbr = 2
    fd.tseg1Dbr = 6
    fd.tseg2Dbr = 3
    
    dll.xlCanFdSetConfiguration(port, access, byref(fd))
    dll.xlActivateChannel(port, access, 1, 8)
    
    tx = tx_class()
    if setup:
        setup(tx)
    else:
        tx.canId = 0x123
        tx.msgFlags = 0x0001
        tx.dlc = 8
        for i in range(8):
            tx.data[i] = i
    
    cnt = c_uint(0)
    status = dll.xlCanTransmitEx(port, access, 1, byref(cnt), byref(tx))
    print(f"xlCanTransmitEx: {status}")
    
    dll.xlDeactivateChannel(port, access)
    dll.xlClosePort(port)

def setup_C(tx):
    tx.tag = 0x0440
    tx.transId = 0
    tx.channelIndex = 0
    tx.txMsg.canId = 0x123
    tx.txMsg.msgFlags = 0x0001
    tx.txMsg.dlc = 8
    for i in range(8):
        tx.txMsg.data[i] = i

test("TxEvent_A (original)", TxEvent_A)
test("TxEvent_B (different reserved)", TxEvent_B)
test("TxEvent_C (with tag wrapper)", TxEvent_C, setup_C)
test("TxEvent_D (msgFlags as ushort)", TxEvent_D)

dll.xlCloseDriver()
