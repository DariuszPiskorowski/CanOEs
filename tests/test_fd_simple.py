"""Test CAN FD - próba bez xlCanFdSetConfiguration"""
from ctypes import *
import time

dll = WinDLL('vxlapi64.dll')

XL_SUCCESS = 0
XL_HWTYPE_VN1640 = 59
XL_BUS_TYPE_CAN = 0x00000001
XL_INTERFACE_VERSION_V4 = 4
XL_ACTIVATE_RESET_CLOCK = 8

XL_CAN_EV_TAG_TX_OK = 0x0401
XL_CAN_EV_TAG_RX_OK = 0x0400
XL_CAN_TXMSG_FLAG_EDL = 0x0001
XL_CAN_TXMSG_FLAG_BRS = 0x0002

class XLcanTxEvent(Structure):
    _pack_ = 1
    _fields_ = [
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("channelIndex", c_ubyte),
        ("reserved1", c_ubyte * 3),
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved2", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

# Otwórz sterownik
dll.xlOpenDriver()
print("[OK] Sterownik otwarty")

# Pobierz maskę kanału
dll.xlGetChannelMask.restype = c_uint64
mask = dll.xlGetChannelMask(c_int(XL_HWTYPE_VN1640), c_int(0), c_int(0))
print(f"[INFO] Maska kanału: 0x{mask:X}")

channel_mask = c_uint64(mask)
permission_mask = c_uint64(mask)
port_handle = c_int(-1)

# Otwórz port V4 (dla CAN FD)
status = dll.xlOpenPort(
    byref(port_handle),
    b"TestFD",
    channel_mask,
    byref(permission_mask),
    c_uint(256),
    c_uint(XL_INTERFACE_VERSION_V4),
    c_uint(XL_BUS_TYPE_CAN)
)
print(f"[INFO] xlOpenPort status: {status}, handle: {port_handle.value}")
print(f"[INFO] permission_mask: 0x{permission_mask.value:X}")

if permission_mask.value == 0:
    print("[WARN] Brak uprawnień do kanału - może być używany przez inną aplikację!")

# NIE konfigurujemy FD - używamy ustawień z Vector Hardware Config
print("[INFO] Pomijam xlCanFdSetConfiguration - używam domyślnych ustawień")

# Aktywuj kanał
status = dll.xlActivateChannel(
    port_handle,
    channel_mask,
    c_uint(XL_BUS_TYPE_CAN),
    c_uint(XL_ACTIVATE_RESET_CLOCK)
)
print(f"[INFO] xlActivateChannel status: {status}")

if status == 0:
    print("[OK] Kanał aktywny - ON BUS")
    
    # Wyślij wiadomość FD
    tx_event = XLcanTxEvent()
    tx_event.tag = XL_CAN_EV_TAG_TX_OK
    tx_event.canId = 0x100
    tx_event.msgFlags = XL_CAN_TXMSG_FLAG_EDL  # FD bez BRS
    tx_event.dlc = 8
    for i in range(8):
        tx_event.data[i] = i + 1
    
    msg_count = c_uint(1)
    status = dll.xlCanTransmitEx(
        port_handle,
        channel_mask,
        byref(msg_count),
        byref(tx_event)
    )
    print(f"[INFO] xlCanTransmitEx (FD) status: {status}")
    
    if status == 0:
        print("[OK] Wiadomość FD wysłana!")
    else:
        print(f"[BŁĄD] Nie udało się wysłać: {status}")
        
        # Spróbuj bez flagi FD
        print("\n[INFO] Próba bez flagi FD...")
        tx_event.msgFlags = 0
        status = dll.xlCanTransmitEx(
            port_handle,
            channel_mask,
            byref(msg_count),
            byref(tx_event)
        )
        print(f"[INFO] xlCanTransmitEx (klasyczny) status: {status}")
    
    # Deaktywuj
    dll.xlDeactivateChannel(port_handle, channel_mask)
    print("[OK] Kanał deaktywowany")

dll.xlClosePort(port_handle)
dll.xlCloseDriver()
print("[OK] Sterownik zamknięty")
