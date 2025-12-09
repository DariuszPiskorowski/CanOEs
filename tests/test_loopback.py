"""Test CAN FD z loopback - jeden kanał wysyła i odbiera"""
import time
import ctypes
from ctypes import c_uint, c_int, c_uint64, byref

# Załaduj DLL
dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

# Stałe
XL_HWTYPE_VN1640 = 59
XL_BUS_TYPE_CAN = 0x00000001
XL_INTERFACE_VERSION_V4 = 4
XL_ACTIVATE_RESET_CLOCK = 8
XL_CAN_EV_TAG_TX_MSG = 0x0440
XL_CAN_TXMSG_FLAG_EDL = 0x0001
XL_CAN_TXMSG_FLAG_BRS = 0x0002

# Struktury
class s_xl_can_tx_msg(ctypes.Structure):
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", ctypes.c_ubyte),
        ("reserved", ctypes.c_ubyte * 7),
        ("data", ctypes.c_ubyte * 64),
    ]

class s_txTagData(ctypes.Union):
    _fields_ = [("canMsg", s_xl_can_tx_msg)]

class XLcanTxEvent(ctypes.Structure):
    _fields_ = [
        ("tag", ctypes.c_ushort),
        ("transId", ctypes.c_ushort),
        ("chanIndex", ctypes.c_ubyte),
        ("reserved", ctypes.c_ubyte * 3),
        ("tagData", s_txTagData),
    ]

class XLcanRxEvent(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("size", c_uint),
        ("tag", ctypes.c_ushort),
        ("channelIndex", ctypes.c_ushort),
        ("userHandle", c_uint),
        ("flagsChip", ctypes.c_ushort),
        ("reserved0", ctypes.c_ushort),
        ("reserved1", c_uint64),
        ("timeStamp", c_uint64),
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("crc", c_uint),
        ("reserved", ctypes.c_ubyte * 12),
        ("totalBitCnt", ctypes.c_ushort),
        ("dlc", ctypes.c_ubyte),
        ("reserved2", ctypes.c_ubyte * 5),
        ("data", ctypes.c_ubyte * 64),
    ]

class XLcanFdConf(ctypes.Structure):
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

print("="*60)
print("Test CAN FD LOOPBACK - jeden kanał TX i RX")
print("="*60)

# Otwórz driver
dll.xlOpenDriver()

# Pobierz maskę kanału
dll.xlGetChannelMask.restype = c_uint64
mask = dll.xlGetChannelMask(c_int(XL_HWTYPE_VN1640), c_int(0), c_int(0))
print(f"Maska kanału 1: 0x{mask:X}")

# Otwórz port
port = c_int(-1)
perm = c_uint64(mask)
status = dll.xlOpenPort(
    byref(port), b"LoopbackTest", c_uint64(mask), byref(perm),
    c_uint(256), c_uint(XL_INTERFACE_VERSION_V4), c_uint(XL_BUS_TYPE_CAN)
)
print(f"xlOpenPort: {status}, port={port.value}, perm=0x{perm.value:X}")

# Konfiguruj FD
fd_conf = XLcanFdConf()
fd_conf.arbitrationBitRate = 500000
fd_conf.dataBitRate = 2000000
fd_conf.sjwAbr = 2
fd_conf.tseg1Abr = 6
fd_conf.tseg2Abr = 3
fd_conf.sjwDbr = 2
fd_conf.tseg1Dbr = 6
fd_conf.tseg2Dbr = 3

status = dll.xlCanFdSetConfiguration(port, c_uint64(mask), byref(fd_conf))
print(f"xlCanFdSetConfiguration: {status}")

# *** WŁĄCZ TX LOOPBACK ***
# XL_CAN_TXMSG_FLAG_TX_LOOPBACK = 0x00000100 lub użyj xlSetChannelTransceiver
# Alternatywnie: xlCanSetChannelParams z loopback

# Sprawdźmy czy jest funkcja do loopback
try:
    # Spróbuj włączyć loopback przez output mode
    # XL_OUTPUT_MODE_SILENT_LOOPBACK = 1
    status = dll.xlCanSetChannelOutput(port, c_uint64(mask), c_uint(1))  # 1 = loopback?
    print(f"xlCanSetChannelOutput (loopback?): {status}")
except:
    print("Brak xlCanSetChannelOutput")

# Aktywuj kanał
status = dll.xlActivateChannel(port, c_uint64(mask), c_uint(XL_BUS_TYPE_CAN), c_uint(XL_ACTIVATE_RESET_CLOCK))
print(f"xlActivateChannel: {status}")

# Ustaw argtypes
dll.xlCanTransmitEx.argtypes = [c_int, c_uint64, c_uint, ctypes.POINTER(c_uint), ctypes.POINTER(XLcanTxEvent)]

# Wyślij wiadomość
tx = XLcanTxEvent()
tx.tag = XL_CAN_EV_TAG_TX_MSG
tx.transId = 0xFFFF
tx.chanIndex = 0
tx.tagData.canMsg.canId = 0x123
tx.tagData.canMsg.msgFlags = XL_CAN_TXMSG_FLAG_EDL | XL_CAN_TXMSG_FLAG_BRS
tx.tagData.canMsg.dlc = 8
for i in range(8):
    tx.tagData.canMsg.data[i] = 0x11 + i

msg_sent = c_uint(0)
status = dll.xlCanTransmitEx(port, c_uint64(mask), c_uint(1), byref(msg_sent), byref(tx))
print(f"\nxlCanTransmitEx: {status}, sent={msg_sent.value}")

# Próbuj odebrać (loopback)
print("\nPróbuję odebrać (loopback)...")
rx = XLcanRxEvent()
for i in range(20):
    status = dll.xlCanReceive(port, byref(rx))
    if status == 0:
        print(f"  ODEBRANO! tag=0x{rx.tag:04X}, ID=0x{rx.canId:X}, dlc={rx.dlc}")
        data = ' '.join(f'{rx.data[j]:02X}' for j in range(min(rx.dlc, 8)))
        print(f"  Data: [{data}]")
        break
    time.sleep(0.05)
else:
    print("  Brak wiadomości w loopback")

# Zamknij
dll.xlDeactivateChannel(port, c_uint64(mask))
dll.xlClosePort(port)
dll.xlCloseDriver()
print("\nGotowe!")
