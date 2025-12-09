"""
Test xlCanTransmitEx z V4 interface + struktura jak python-can
"""
import ctypes
from ctypes import Structure, Union, c_uint, c_uint64, c_ubyte, c_ushort, c_int, byref, sizeof

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

XL_CAN_MAX_DATA_LEN = 64

class s_xl_can_tx_msg(Structure):
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * XL_CAN_MAX_DATA_LEN),
    ]

class s_txTagData(Union):
    _fields_ = [("canMsg", s_xl_can_tx_msg)]

class XLcanTxEvent(Structure):
    _fields_ = [
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("chanIndex", c_ubyte),
        ("reserved", c_ubyte * 3),
        ("tagData", s_txTagData),
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

XL_CAN_EV_TAG_TX_MSG = 0x0440
XL_CAN_TXMSG_FLAG_EDL = 0x0001
XL_CAN_TXMSG_FLAG_BRS = 0x0002

print("=" * 60)
print("Test z V4 interface")
print("=" * 60)

status = dll.xlOpenDriver()
print(f"xlOpenDriver: {status}")

dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)
access = c_uint64(1 << idx)

# Open port z V4!
port = c_int(0)
perm = c_uint64(access.value)

print(f"\nOtwieranie portu z interfaceVersion=4 (V4)...")
status = dll.xlOpenPort(byref(port), b"CANFD_V4", access, byref(perm), 256, 4, 1)  # <-- V4!
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
        tx.tag = XL_CAN_EV_TAG_TX_MSG
        tx.transId = 0xFFFF
        tx.chanIndex = 0
        tx.tagData.canMsg.canId = 0x123
        tx.tagData.canMsg.msgFlags = XL_CAN_TXMSG_FLAG_EDL | XL_CAN_TXMSG_FLAG_BRS
        tx.tagData.canMsg.dlc = 8
        for i in range(8):
            tx.tagData.canMsg.data[i] = 0x11 + i
        
        msgCntSent = c_uint(0)
        status = dll.xlCanTransmitEx(port, access, 1, byref(msgCntSent), byref(tx))
        print(f"\nxlCanTransmitEx: status={status}, sent={msgCntSent.value}")
        
        if status == 0:
            print("\n*** SUKCES! CAN FD WYSŁANE! ***")
        else:
            # Sprawdź co znaczy ten kod błędu
            error_codes = {
                0: "SUCCESS",
                10: "QUEUE_IS_EMPTY",
                11: "QUEUE_IS_FULL", 
                14: "NO_LICENSE",
                118: "NOT_SUPPORTED/WRONG_CHIP_TYPE",
                132: "WRONG_PARAMETER",
            }
            print(f"Błąd: {error_codes.get(status, 'UNKNOWN')}")
    
    dll.xlDeactivateChannel(port, access)
    dll.xlClosePort(port)
elif status == 0:
    print("Brak uprawnień do kanału!")
    dll.xlClosePort(port)

dll.xlCloseDriver()
print("\nDone")
