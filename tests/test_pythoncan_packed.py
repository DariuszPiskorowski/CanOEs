"""
Test xlCanTransmitEx ze strukturą jak w python-can + _pack_=1
"""
import ctypes
from ctypes import Structure, Union, c_uint, c_uint64, c_ubyte, c_ushort, c_int, byref, sizeof

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

XL_CAN_MAX_DATA_LEN = 64

# s_xl_can_tx_msg - dane wiadomości
class s_xl_can_tx_msg(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * XL_CAN_MAX_DATA_LEN),
    ]

# s_txTagData - union (tylko canMsg)
class s_txTagData(Union):
    _pack_ = 1
    _fields_ = [("canMsg", s_xl_can_tx_msg)]

# XLcanTxEvent - główna struktura (z tagiem!)
class XLcanTxEvent(Structure):
    _pack_ = 1
    _fields_ = [
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("chanIndex", c_ubyte),
        ("reserved", c_ubyte * 3),
        ("tagData", s_txTagData),
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

# Stałe
XL_CAN_EV_TAG_TX_MSG = 0x0440  # 1088
XL_CAN_TXMSG_FLAG_EDL = 0x0001
XL_CAN_TXMSG_FLAG_BRS = 0x0002

print("=" * 60)
print("Test ze strukturą jak w python-can + _pack_=1")
print("=" * 60)
print(f"sizeof(XLcanTxEvent) = {sizeof(XLcanTxEvent)}")
print(f"sizeof(s_xl_can_tx_msg) = {sizeof(s_xl_can_tx_msg)}")

status = dll.xlOpenDriver()
print(f"\nxlOpenDriver: {status}")

dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)
access = c_uint64(1 << idx)
print(f"Channel index: {idx}, access: 0x{access.value:X}")

# Open port
port = c_int(0)
perm = c_uint64(access.value)

status = dll.xlOpenPort(byref(port), b"PythonCanFD", access, byref(perm), 256, 3, 1)
print(f"xlOpenPort: status={status}, perm=0x{perm.value:X}")

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
    
    status = dll.xlCanFdSetConfiguration(port, access, byref(fd_conf))
    print(f"xlCanFdSetConfiguration: {status}")
    
    # Activate
    status = dll.xlActivateChannel(port, access, 1, 8)
    print(f"xlActivateChannel: {status}")
    
    if status == 0:
        # Build TX event jak python-can
        tx = XLcanTxEvent()
        tx.tag = XL_CAN_EV_TAG_TX_MSG  # 0x0440
        tx.transId = 0xFFFF
        tx.chanIndex = 0
        tx.tagData.canMsg.canId = 0x123
        tx.tagData.canMsg.msgFlags = XL_CAN_TXMSG_FLAG_EDL | XL_CAN_TXMSG_FLAG_BRS
        tx.tagData.canMsg.dlc = 8
        for i in range(8):
            tx.tagData.canMsg.data[i] = 0x11 + i
        
        print(f"\nTX Event:")
        print(f"  tag: 0x{tx.tag:04X}")
        print(f"  transId: 0x{tx.transId:04X}")
        print(f"  canId: 0x{tx.tagData.canMsg.canId:08X}")
        print(f"  msgFlags: 0x{tx.tagData.canMsg.msgFlags:08X}")
        print(f"  dlc: {tx.tagData.canMsg.dlc}")
        
        msgCntSent = c_uint(0)
        status = dll.xlCanTransmitEx(port, access, 1, byref(msgCntSent), byref(tx))
        print(f"\nxlCanTransmitEx: status={status}, sent={msgCntSent.value}")
        
        if status == 0:
            print("\n*** SUKCES! CAN FD WIADOMOŚĆ WYSŁANA! ***")
        elif status == 132:
            print("WRONG_PARAMETER")
        elif status == 118:
            print("XL_ERR_NOT_SUPPORTED or similar")
    
    dll.xlDeactivateChannel(port, access)
    dll.xlClosePort(port)

dll.xlCloseDriver()
print("\nDone")
