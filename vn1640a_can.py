"""
Vector VN1640A - Interfejs CAN / CAN FD
Wysyłanie i odbieranie wiadomości CAN i CAN FD

Funkcje:
- CAN klasyczny (11-bit ID, do 8 bajtów)
- CAN FD (11-bit lub 29-bit ID, do 64 bajtów)
- Extended ID (29-bit)
- BRS (Bit Rate Switch) dla CAN FD

Konfiguracja:
- Kanał 1: fizycznie podłączony
- Baudrate: 500 kbit/s (arbitration), 2 Mbit/s (data dla FD)
- Numeracja kanałów: 1-4 (zgodnie z Vector)

Autor: GitHub Copilot
"""

import ctypes
from ctypes import (
    c_uint, c_int, c_char, c_ubyte, c_ushort, c_ulong, c_ulonglong,
    c_uint64, c_uint32, c_void_p, Structure, Union, POINTER, byref, sizeof
)
from typing import Optional, List, Callable, Union as TypingUnion
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
import time
import threading


# ============================================================================
# STAŁE VXLAPI
# ============================================================================

XL_SUCCESS = 0
XL_ERR_QUEUE_IS_EMPTY = 10
XL_ERR_QUEUE_IS_FULL = 11
XL_ERR_INVALID_ACCESS = 13
XL_ERR_NO_LICENSE = 14

XL_BUS_TYPE_CAN = 0x00000001
XL_INTERFACE_VERSION = 3
XL_INTERFACE_VERSION_V4 = 4  # Dla CAN FD

XL_ACTIVATE_RESET_CLOCK = 8

# Event tags
XL_RECEIVE_MSG = 1
XL_CHIP_STATE = 4
XL_TRANSMIT_MSG = 10
XL_CAN_EV_TAG_RX_OK = 0x0400
XL_CAN_EV_TAG_TX_OK = 0x0401
XL_CAN_EV_TAG_TX_MSG = 0x0440  # Tag dla wysyłania CAN FD

# Flagi wiadomości CAN
XL_CAN_EXT_MSG_ID = 0x80000000  # Extended ID (29-bit)
XL_CAN_MSG_FLAG_ERROR_FRAME = 0x01
XL_CAN_MSG_FLAG_REMOTE_FRAME = 0x10
XL_CAN_MSG_FLAG_TX_COMPLETED = 0x40

# Flagi CAN FD
XL_CAN_RXMSG_FLAG_EDL = 0x0001  # Extended Data Length (FD frame)
XL_CAN_RXMSG_FLAG_BRS = 0x0002  # Bit Rate Switch
XL_CAN_RXMSG_FLAG_ESI = 0x0004  # Error State Indicator
XL_CAN_RXMSG_FLAG_EF = 0x0200   # Error Frame

XL_CAN_TXMSG_FLAG_EDL = 0x0001  # FD frame
XL_CAN_TXMSG_FLAG_BRS = 0x0002  # Bit Rate Switch
XL_CAN_TXMSG_FLAG_RTR = 0x0010  # Remote frame

# Hardware types
XL_HWTYPE_VN1610 = 55
XL_HWTYPE_VN1630 = 57
XL_HWTYPE_VN1640 = 59  # VN1640A

# CAN FD DLC mapping (DLC -> liczba bajtów)
CAN_FD_DLC_MAP = {
    0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
    9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64
}


class Baudrate(IntEnum):
    """Prędkości CAN (arbitration phase)."""
    BAUD_1M = 1000000
    BAUD_500K = 500000
    BAUD_250K = 250000
    BAUD_125K = 125000
    BAUD_100K = 100000


class BaudrateFD(IntEnum):
    """Prędkości CAN FD (data phase)."""
    BAUD_8M = 8000000
    BAUD_5M = 5000000
    BAUD_4M = 4000000
    BAUD_2M = 2000000
    BAUD_1M = 1000000


# ============================================================================
# STRUKTURY VXLAPI - CAN KLASYCZNY
# ============================================================================

class s_xl_can_msg(Structure):
    """Wiadomość CAN klasyczna."""
    _fields_ = [
        ("id", c_ulong),
        ("flags", c_ushort),
        ("dlc", c_ushort),
        ("res1", c_uint64),
        ("data", c_ubyte * 8),
        ("res2", c_uint64),
    ]


class s_xl_chip_state(Structure):
    _fields_ = [
        ("busStatus", c_ubyte),
        ("txErrorCounter", c_ubyte),
        ("rxErrorCounter", c_ubyte),
        ("chipState", c_ubyte),
        ("flags", c_uint),
    ]


class s_xl_tag_data(Union):
    _fields_ = [
        ("msg", s_xl_can_msg),
        ("chipState", s_xl_chip_state),
    ]


class XLevent(Structure):
    """Event CAN klasyczny."""
    _fields_ = [
        ("tag", c_ubyte),
        ("chanIndex", c_ubyte),
        ("transId", c_ushort),
        ("portHandle", c_ushort),
        ("flags", c_ubyte),
        ("reserved", c_ubyte),
        ("timeStamp", c_uint64),
        ("tagData", s_xl_tag_data),
    ]


# ============================================================================
# STRUKTURY VXLAPI - CAN FD
# ============================================================================

class XLcanRxEvent(Structure):
    """Struktura odbieranej wiadomości CAN FD."""
    _pack_ = 1
    _fields_ = [
        ("size", c_uint),
        ("tag", c_ushort),
        ("channelIndex", c_ushort),
        ("userHandle", c_uint),
        ("flagsChip", c_ushort),
        ("reserved0", c_ushort),
        ("reserved1", c_uint64),
        ("timeStamp", c_uint64),
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("crc", c_uint),
        ("reserved", c_ubyte * 12),
        ("totalBitCnt", c_ushort),
        ("dlc", c_ubyte),
        ("reserved2", c_ubyte * 5),
        ("data", c_ubyte * 64),
    ]


# Struktura wiadomości CAN FD do wysyłania (wewnętrzna)
class s_xl_can_tx_msg(Structure):
    """Wewnętrzna struktura wiadomości CAN FD do wysyłania."""
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

# Union dla tagData w XLcanTxEvent
class s_txTagData(Union):
    _fields_ = [
        ("canMsg", s_xl_can_tx_msg),
    ]

class XLcanTxEvent(Structure):
    """Struktura wysyłanej wiadomości CAN FD - zgodna z python-can i V4 API."""
    _fields_ = [
        ("tag", c_ushort),         # 0x0440 = XL_CAN_EV_TAG_TX_MSG
        ("transId", c_ushort),     # 0xFFFF
        ("chanIndex", c_ubyte),    # indeks kanału
        ("reserved", c_ubyte * 3), # wyrównanie
        ("tagData", s_txTagData),  # wiadomość CAN
    ]


class XLcanFdConf(Structure):
    """Konfiguracja CAN FD - UWAGA: wszystkie pola muszą być c_uint!"""
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


# ============================================================================
# KLASA WIADOMOŚCI CAN/CAN FD
# ============================================================================

@dataclass
class CANMsg:
    """
    Wiadomość CAN lub CAN FD.
    
    Attributes:
        id: ID wiadomości (11-bit lub 29-bit)
        data: Dane (do 8 bajtów dla CAN, do 64 dla CAN FD)
        dlc: Data Length Code
        channel: Numer kanału (1-4)
        timestamp: Znacznik czasu
        is_extended: True dla extended ID (29-bit)
        is_fd: True dla ramki CAN FD
        is_brs: True jeśli BRS (szybsza faza danych)
        is_remote: True dla ramki RTR
        is_error: True dla ramki błędu
    """
    id: int
    data: bytes = field(default_factory=bytes)
    dlc: int = None
    channel: int = 1
    timestamp: float = 0.0
    is_extended: bool = False
    is_fd: bool = False
    is_brs: bool = False
    is_remote: bool = False
    is_error: bool = False
    
    def __post_init__(self):
        if isinstance(self.data, list):
            self.data = bytes(self.data)
        
        if self.dlc is None:
            self.dlc = self._bytes_to_dlc(len(self.data))
        
        max_len = 64 if self.is_fd else 8
        if len(self.data) > max_len:
            self.data = self.data[:max_len]
    
    def _bytes_to_dlc(self, num_bytes: int) -> int:
        """Konwertuje liczbę bajtów na DLC."""
        if num_bytes <= 8:
            return num_bytes
        for dlc, length in sorted(CAN_FD_DLC_MAP.items()):
            if length >= num_bytes:
                return dlc
        return 15
    
    @property
    def data_length(self) -> int:
        """Rzeczywista długość danych w bajtach."""
        return CAN_FD_DLC_MAP.get(self.dlc, self.dlc if self.dlc <= 8 else 8)
    
    def __repr__(self):
        hex_data = ' '.join(f'{b:02X}' for b in self.data)
        
        if self.is_extended:
            id_str = f"0x{self.id:08X}"
        else:
            id_str = f"0x{self.id:03X}"
        
        flags = []
        if self.is_fd:
            flags.append("FD")
        if self.is_brs:
            flags.append("BRS")
        if self.is_extended:
            flags.append("EXT")
        if self.is_remote:
            flags.append("RTR")
        if self.is_error:
            flags.append("ERR")
        
        flags_str = f" [{','.join(flags)}]" if flags else ""
        
        return f"[CH{self.channel}] ID={id_str} DLC={self.dlc}{flags_str} [{hex_data}]"


# ============================================================================
# GŁÓWNA KLASA VN1640A
# ============================================================================

class VN1640A:
    """
    Interfejs CAN/CAN FD dla Vector VN1640A.
    
    Obsługuje:
    - CAN klasyczny (11-bit ID, 8 bajtów)
    - CAN z Extended ID (29-bit)
    - CAN FD (do 64 bajtów)
    - CAN FD z BRS (Bit Rate Switch)
    
    Numeracja kanałów: 1, 2, 3, 4 (zgodnie z Vector)
    
    Przykład CAN klasyczny:
        vn = VN1640A()
        vn.open()
        vn.start(channel=1)
        vn.send(0x123, [0x11, 0x22, 0x33])
        vn.close()
    
    Przykład CAN FD:
        vn = VN1640A()
        vn.open()
        vn.start_fd(channel=1)
        vn.send_fd(0x123, [0x11]*32, brs=True)
        vn.close()
    
    Przykład Extended ID (29-bit):
        vn.send(0x12345678, [0x11, 0x22], extended=True)
    """
    
    def __init__(self, 
                 baudrate: int = Baudrate.BAUD_500K,
                 baudrate_fd: int = BaudrateFD.BAUD_2M):
        """
        Args:
            baudrate: Prędkość CAN / arbitration phase (domyślnie 500 kbit/s)
            baudrate_fd: Prędkość data phase dla CAN FD (domyślnie 2 Mbit/s)
        """
        self.baudrate = baudrate
        self.baudrate_fd = baudrate_fd
        self.dll = None
        
        # Stan
        self.port_handle = c_int(-1)
        self.channel_mask = c_uint64(0)
        self.permission_mask = c_uint64(0)
        self.active_channel: Optional[int] = None
        
        self.is_open = False
        self.is_on_bus = False
        self.is_fd_mode = False
        
        # RX callback
        self._rx_callback: Optional[Callable] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._rx_running = False
    
    # ========================================================================
    # OTWIERANIE / ZAMYKANIE
    # ========================================================================
    
    def open(self) -> bool:
        """Otwiera sterownik Vector."""
        try:
            self.dll = ctypes.windll.LoadLibrary("vxlapi64.dll")
        except OSError as e:
            print(f"[BŁĄD] Nie można załadować vxlapi64.dll: {e}")
            return False
        
        # Ustaw argtypes dla xlCanTransmitEx (kluczowe dla CAN FD!)
        self.dll.xlCanTransmitEx.argtypes = [
            c_int,                      # portHandle (XLportHandle = c_long/c_int)
            c_uint64,                   # accessMask (XLaccess = c_uint64)
            c_uint,                     # msgCnt
            POINTER(c_uint),            # pMsgCntSent
            POINTER(XLcanTxEvent)       # pXlCanTxEvt
        ]
        self.dll.xlCanTransmitEx.restype = c_int
        
        status = self.dll.xlOpenDriver()
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlOpenDriver: {status}")
            return False
        
        self.is_open = True
        print("[OK] Sterownik Vector otwarty")
        return True
    
    def close(self):
        """Zamyka sterownik."""
        if self.is_on_bus:
            self.stop()
        
        if self.port_handle.value >= 0 and self.dll:
            self.dll.xlClosePort(self.port_handle)
            self.port_handle = c_int(-1)
        
        if self.dll:
            self.dll.xlCloseDriver()
        
        self.is_open = False
        self.is_fd_mode = False
        self.active_channel = None
        print("[OK] Sterownik zamknięty")
    
    # ========================================================================
    # START CAN KLASYCZNY
    # ========================================================================
    
    def start(self, channel: int = 1) -> bool:
        """
        Uruchamia kanał w trybie CAN klasycznym.
        
        Args:
            channel: Numer kanału (1, 2, 3 lub 4)
        """
        if not self.is_open:
            print("[BŁĄD] Najpierw użyj open()")
            return False
        
        if channel < 1 or channel > 4:
            print(f"[BŁĄD] Nieprawidłowy kanał: {channel}. Użyj 1-4")
            return False
        
        # Pobierz maskę kanału
        # Wewnętrznie Vector używa indeksów 0-3, ale my przyjmujemy 1-4
        hw_channel = channel - 1
        
        self.dll.xlGetChannelMask.restype = c_uint64
        mask = self.dll.xlGetChannelMask(
            c_int(XL_HWTYPE_VN1640),
            c_int(0),
            c_int(hw_channel)
        )
        
        if mask == 0:
            print(f"[BŁĄD] Nie znaleziono kanału {channel}")
            return False
        
        self.channel_mask = c_uint64(mask)
        self.permission_mask = c_uint64(mask)
        
        print(f"[INFO] Kanał {channel}: maska = 0x{mask:X}")
        
        # Otwórz port
        status = self.dll.xlOpenPort(
            byref(self.port_handle),
            b"PythonCAN",
            self.channel_mask,
            byref(self.permission_mask),
            c_uint(256),
            c_uint(XL_INTERFACE_VERSION),
            c_uint(XL_BUS_TYPE_CAN)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlOpenPort: {status}")
            return False
        
        # Ustaw baudrate
        status = self.dll.xlCanSetChannelBitrate(
            self.port_handle,
            self.channel_mask,
            c_uint(self.baudrate)
        )
        
        if status != XL_SUCCESS:
            print(f"[WARN] Nie można ustawić baudrate: {status}")
        else:
            print(f"[OK] Baudrate: {self.baudrate // 1000} kbit/s")
        
        # Wyczyść kolejkę odbiorczą
        self.dll.xlFlushReceiveQueue(self.port_handle)
        
        # Ustaw notyfikacje (wymagane do odbierania)
        self.rx_event_handle = c_void_p()
        status = self.dll.xlSetNotification(
            self.port_handle,
            byref(self.rx_event_handle),
            c_int(1)  # queue level
        )
        if status != XL_SUCCESS:
            print(f"[WARN] xlSetNotification: {status}")
        else:
            print("[OK] Notyfikacje włączone")
        
        # Aktywuj kanał
        status = self.dll.xlActivateChannel(
            self.port_handle,
            self.channel_mask,
            c_uint(XL_BUS_TYPE_CAN),
            c_uint(XL_ACTIVATE_RESET_CLOCK)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlActivateChannel: {status}")
            return False
        
        self.is_on_bus = True
        self.is_fd_mode = False
        self.active_channel = channel
        print(f"[OK] Kanał {channel} aktywny - CAN klasyczny - ON BUS")
        return True
    
    # ========================================================================
    # START CAN FD
    # ========================================================================
    
    def start_fd(self, channel: int = 1) -> bool:
        """
        Uruchamia kanał w trybie CAN FD.
        
        Args:
            channel: Numer kanału (1, 2, 3 lub 4)
        """
        if not self.is_open:
            print("[BŁĄD] Najpierw użyj open()")
            return False
        
        if channel < 1 or channel > 4:
            print(f"[BŁĄD] Nieprawidłowy kanał: {channel}. Użyj 1-4")
            return False
        
        hw_channel = channel - 1
        
        self.dll.xlGetChannelMask.restype = c_uint64
        mask = self.dll.xlGetChannelMask(
            c_int(XL_HWTYPE_VN1640),
            c_int(0),
            c_int(hw_channel)
        )
        
        if mask == 0:
            print(f"[BŁĄD] Nie znaleziono kanału {channel}")
            return False
        
        self.channel_mask = c_uint64(mask)
        self.permission_mask = c_uint64(mask)
        
        print(f"[INFO] Kanał {channel} (FD): maska = 0x{mask:X}")
        
        # Otwórz port z interfejsem V4 dla CAN FD
        status = self.dll.xlOpenPort(
            byref(self.port_handle),
            b"PythonCANFD",
            self.channel_mask,
            byref(self.permission_mask),
            c_uint(256),
            c_uint(XL_INTERFACE_VERSION_V4),
            c_uint(XL_BUS_TYPE_CAN)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlOpenPort (FD): {status}")
            return False
        
        # Konfiguruj CAN FD
        fd_conf = XLcanFdConf()
        fd_conf.arbitrationBitRate = self.baudrate
        fd_conf.dataBitRate = self.baudrate_fd
        
        # Parametry timingu (sprawdzone - działające wartości)
        fd_conf.sjwAbr = 2
        fd_conf.tseg1Abr = 6
        fd_conf.tseg2Abr = 3
        fd_conf.sjwDbr = 2
        fd_conf.tseg1Dbr = 6
        fd_conf.tseg2Dbr = 3
        
        status = self.dll.xlCanFdSetConfiguration(
            self.port_handle,
            self.channel_mask,
            byref(fd_conf)
        )
        
        if status != XL_SUCCESS:
            print(f"[WARN] xlCanFdSetConfiguration: {status}")
            print(f"       Używam domyślnej konfiguracji FD")
        else:
            print(f"[OK] CAN FD: {self.baudrate // 1000}k / {self.baudrate_fd // 1000}k")
        
        # Wyczyść kolejkę odbiorczą
        self.dll.xlFlushReceiveQueue(self.port_handle)
        
        # Ustaw notyfikacje (wymagane do odbierania)
        self.rx_event_handle = c_void_p()
        status = self.dll.xlSetNotification(
            self.port_handle,
            byref(self.rx_event_handle),
            c_int(1)  # queue level
        )
        if status != XL_SUCCESS:
            print(f"[WARN] xlSetNotification: {status}")
        else:
            print("[OK] Notyfikacje włączone")
        
        # Aktywuj kanał
        status = self.dll.xlActivateChannel(
            self.port_handle,
            self.channel_mask,
            c_uint(XL_BUS_TYPE_CAN),
            c_uint(XL_ACTIVATE_RESET_CLOCK)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlActivateChannel: {status}")
            return False
        
        self.is_on_bus = True
        self.is_fd_mode = True
        self.active_channel = channel
        print(f"[OK] Kanał {channel} aktywny - CAN FD - ON BUS")
        return True
    
    # ========================================================================
    # STOP
    # ========================================================================
    
    def stop(self):
        """Zatrzymuje kanał (go off bus)."""
        self._stop_rx_thread()
        
        if self.dll and self.is_on_bus:
            self.dll.xlDeactivateChannel(self.port_handle, self.channel_mask)
        
        self.is_on_bus = False
        print(f"[OK] Kanał {self.active_channel} - OFF BUS")
    
    # ========================================================================
    # WYSYŁANIE - CAN KLASYCZNY
    # ========================================================================
    
    def send(self, msg_id: int, data, extended: bool = False) -> bool:
        """
        Wysyła wiadomość CAN (klasyczny, do 8 bajtów).
        
        Args:
            msg_id: ID wiadomości
                    - 11-bit (0x000-0x7FF) jeśli extended=False
                    - 29-bit (0x00000000-0x1FFFFFFF) jeśli extended=True
            data: Lista lub bytes danych (max 8)
            extended: True dla extended ID (29-bit)
        
        Returns:
            True jeśli wysłano pomyślnie
        
        Examples:
            # Standard ID (11-bit)
            vn.send(0x123, [0x11, 0x22, 0x33])
            
            # Extended ID (29-bit)
            vn.send(0x12345678, [0x11, 0x22], extended=True)
        """
        if not self.is_on_bus:
            print("[BŁĄD] Nie jesteś on bus! Użyj start() lub start_fd()")
            return False
        
        # Konwersja bytes na list
        if isinstance(data, bytes):
            data = list(data)
        
        if self.is_fd_mode:
            return self.send_fd(msg_id, data, extended=extended, fd=False)
        
        event = XLevent()
        event.tag = XL_TRANSMIT_MSG
        
        if extended:
            event.tagData.msg.id = (msg_id & 0x1FFFFFFF) | XL_CAN_EXT_MSG_ID
        else:
            event.tagData.msg.id = msg_id & 0x7FF
        
        dlc = min(len(data), 8)
        event.tagData.msg.dlc = dlc
        for i in range(dlc):
            event.tagData.msg.data[i] = data[i]
        
        msg_count = c_uint(1)
        status = self.dll.xlCanTransmit(
            self.port_handle,
            self.channel_mask,
            byref(msg_count),
            byref(event)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD TX] status={status}")
            return False
        
        self._log_tx(msg_id, data[:dlc], extended=extended)
        return True
    
    # ========================================================================
    # WYSYŁANIE - CAN FD
    # ========================================================================
    
    def send_fd(self, msg_id: int, data: list, 
                extended: bool = False, 
                brs: bool = True,
                fd: bool = True) -> bool:
        """
        Wysyła wiadomość CAN FD (do 64 bajtów).
        
        Args:
            msg_id: ID wiadomości
                    - 11-bit (0x000-0x7FF) jeśli extended=False
                    - 29-bit (0x00000000-0x1FFFFFFF) jeśli extended=True
            data: Lista bajtów danych (max 64 dla FD, max 8 dla klasyczny)
            extended: True dla extended ID (29-bit)
            brs: True dla Bit Rate Switch (szybsza faza danych)
            fd: True dla ramki FD (False = klasyczna ramka CAN)
        
        Returns:
            True jeśli wysłano pomyślnie
        
        Examples:
            # CAN FD z BRS, 32 bajty danych
            vn.send_fd(0x123, [0x11]*32, brs=True)
            
            # CAN FD z Extended ID, 64 bajty
            vn.send_fd(0x12345678, [0x11]*64, extended=True, brs=True)
            
            # Klasyczna ramka CAN przez interfejs FD
            vn.send_fd(0x123, [0x11, 0x22], fd=False)
        """
        if not self.is_on_bus:
            print("[BŁĄD] Nie jesteś on bus!")
            return False
        
        if not self.is_fd_mode:
            print("[WARN] Nie jesteś w trybie FD. Używam send() dla CAN klasyczny.")
            return self.send(msg_id, data[:8], extended)
        
        # Konwersja bytes na list
        if isinstance(data, bytes):
            data = list(data)
        
        tx_event = XLcanTxEvent()
        
        # Ustaw nagłówek (tag, transId, chanIndex)
        tx_event.tag = XL_CAN_EV_TAG_TX_MSG  # 0x0440
        tx_event.transId = 0xFFFF
        tx_event.chanIndex = 0  # indeks kanału (0-based)
        
        # Ustaw dane wiadomości
        if extended:
            tx_event.tagData.canMsg.canId = (msg_id & 0x1FFFFFFF) | XL_CAN_EXT_MSG_ID
        else:
            tx_event.tagData.canMsg.canId = msg_id & 0x7FF
        
        flags = 0
        if fd:
            flags |= XL_CAN_TXMSG_FLAG_EDL
        if brs and fd:
            flags |= XL_CAN_TXMSG_FLAG_BRS
        tx_event.tagData.canMsg.msgFlags = flags
        
        data_len = min(len(data), 64 if fd else 8)
        tx_event.tagData.canMsg.dlc = self._bytes_to_dlc(data_len)
        
        for i in range(data_len):
            tx_event.tagData.canMsg.data[i] = data[i]
        
        msg_count = c_uint(1)
        msg_sent = c_uint(0)
        status = self.dll.xlCanTransmitEx(
            self.port_handle,
            self.channel_mask,
            msg_count,           # wartość, nie pointer
            byref(msg_sent),     # pointer na liczbę wysłanych
            byref(tx_event)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD TX FD] status={status}")
            return False
        
        self._log_tx(msg_id, data[:data_len], extended=extended, fd=fd, brs=brs)
        return True
    
    def _bytes_to_dlc(self, num_bytes: int) -> int:
        """Konwertuje liczbę bajtów na DLC."""
        if num_bytes <= 8:
            return num_bytes
        for dlc in [9, 10, 11, 12, 13, 14, 15]:
            if CAN_FD_DLC_MAP[dlc] >= num_bytes:
                return dlc
        return 15
    
    def _log_tx(self, msg_id: int, data: list, extended: bool = False, 
                fd: bool = False, brs: bool = False):
        """Loguje wysłaną wiadomość."""
        hex_data = ' '.join(f'{b:02X}' for b in data)
        
        if extended:
            id_str = f"0x{msg_id:08X}"
        else:
            id_str = f"0x{msg_id:03X}"
        
        flags = []
        if fd:
            flags.append("FD")
        if brs:
            flags.append("BRS")
        if extended:
            flags.append("EXT")
        
        flags_str = f" [{','.join(flags)}]" if flags else ""
        print(f"[TX] ID={id_str} DLC={len(data)}{flags_str} [{hex_data}]")
    
    # ========================================================================
    # WYSYŁANIE - OBIEKT CANMsg
    # ========================================================================
    
    def send_msg(self, msg: CANMsg) -> bool:
        """Wysyła obiekt CANMsg."""
        if msg.is_fd or self.is_fd_mode:
            return self.send_fd(
                msg.id, 
                list(msg.data), 
                extended=msg.is_extended,
                brs=msg.is_brs,
                fd=msg.is_fd
            )
        else:
            return self.send(msg.id, list(msg.data), extended=msg.is_extended)
    
    # ========================================================================
    # ODBIERANIE
    # ========================================================================
    
    def receive(self, timeout_ms: int = 1000) -> Optional[CANMsg]:
        """
        Odbiera wiadomość CAN/CAN FD.
        
        Args:
            timeout_ms: Timeout w milisekundach
        
        Returns:
            CANMsg lub None jeśli timeout
        """
        if not self.is_on_bus:
            return None
        
        if self.is_fd_mode:
            return self._receive_fd(timeout_ms)
        else:
            return self._receive_classic(timeout_ms)
    
    def _receive_classic(self, timeout_ms: int) -> Optional[CANMsg]:
        """Odbiera wiadomość CAN klasyczny."""
        event = XLevent()
        event_count = c_uint(1)
        
        start = time.time()
        timeout_s = timeout_ms / 1000.0
        
        while (time.time() - start) < timeout_s:
            event_count.value = 1
            status = self.dll.xlReceive(
                self.port_handle,
                byref(event_count),
                byref(event)
            )
            
            if status == XL_SUCCESS and event_count.value > 0:
                if event.tag == XL_RECEIVE_MSG:
                    return self._parse_classic_message(event)
            
            time.sleep(0.001)
        
        return None
    
    def _receive_fd(self, timeout_ms: int) -> Optional[CANMsg]:
        """Odbiera wiadomość CAN FD."""
        rx_event = XLcanRxEvent()
        
        start = time.time()
        timeout_s = timeout_ms / 1000.0
        
        while (time.time() - start) < timeout_s:
            status = self.dll.xlCanReceive(
                self.port_handle,
                byref(rx_event)
            )
            
            if status == XL_SUCCESS:
                if rx_event.tag in [XL_CAN_EV_TAG_RX_OK, 0x0400]:
                    return self._parse_fd_message(rx_event)
            
            time.sleep(0.001)
        
        return None
    
    def _parse_classic_message(self, event: XLevent) -> CANMsg:
        """Parsuje wiadomość CAN klasyczny."""
        msg_data = event.tagData.msg
        
        is_ext = (msg_data.id & XL_CAN_EXT_MSG_ID) != 0
        msg_id = msg_data.id & 0x1FFFFFFF
        dlc = msg_data.dlc & 0x0F
        data = bytes(msg_data.data[:dlc])
        
        msg = CANMsg(
            id=msg_id,
            data=data,
            dlc=dlc,
            channel=self.active_channel,
            timestamp=event.timeStamp / 1e9,
            is_extended=is_ext,
            is_fd=False,
            is_brs=False,
        )
        
        self._log_rx(msg)
        return msg
    
    def _parse_fd_message(self, event: XLcanRxEvent) -> CANMsg:
        """Parsuje wiadomość CAN FD."""
        is_ext = (event.canId & XL_CAN_EXT_MSG_ID) != 0
        msg_id = event.canId & 0x1FFFFFFF
        
        is_fd = (event.msgFlags & XL_CAN_RXMSG_FLAG_EDL) != 0
        is_brs = (event.msgFlags & XL_CAN_RXMSG_FLAG_BRS) != 0
        is_error = (event.msgFlags & XL_CAN_RXMSG_FLAG_EF) != 0
        
        dlc = event.dlc & 0x0F
        data_len = CAN_FD_DLC_MAP.get(dlc, dlc if dlc <= 8 else 8)
        data = bytes(event.data[:data_len])
        
        msg = CANMsg(
            id=msg_id,
            data=data,
            dlc=dlc,
            channel=self.active_channel,
            timestamp=event.timeStamp / 1e9,
            is_extended=is_ext,
            is_fd=is_fd,
            is_brs=is_brs,
            is_error=is_error,
        )
        
        self._log_rx(msg)
        return msg
    
    def _log_rx(self, msg: CANMsg):
        """Loguje odebraną wiadomość."""
        print(f"[RX] {msg}")
    
    def receive_all(self, timeout_ms: int = 1000, max_count: int = 100) -> List[CANMsg]:
        """Odbiera wiele wiadomości."""
        messages = []
        start = time.time()
        
        while len(messages) < max_count and (time.time() - start) < (timeout_ms / 1000.0):
            msg = self.receive(timeout_ms=50)
            if msg:
                messages.append(msg)
        
        return messages
    
    # ========================================================================
    # ASYNCHRONICZNE ODBIERANIE
    # ========================================================================
    
    def start_receiving(self, callback: Callable[[CANMsg], None]):
        """
        Rozpoczyna ciągłe odbieranie w tle.
        
        Args:
            callback: Funkcja wywoływana dla każdej wiadomości
        """
        self._rx_callback = callback
        self._rx_running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()
        print("[OK] Nasłuchiwanie uruchomione")
    
    def stop_receiving(self):
        """Zatrzymuje odbieranie w tle."""
        self._stop_rx_thread()
        print("[OK] Nasłuchiwanie zatrzymane")
    
    def _rx_loop(self):
        """Pętla odbierająca."""
        while self._rx_running:
            msg = self.receive(timeout_ms=50)
            if msg and self._rx_callback:
                self._rx_callback(msg)
    
    def _stop_rx_thread(self):
        """Zatrzymuje wątek RX."""
        self._rx_running = False
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)
        self._rx_thread = None
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, *args):
        self.close()


# ============================================================================
# FUNKCJE POMOCNICZE
# ============================================================================

def quick_test_can():
    """Test CAN klasyczny."""
    print("\n" + "=" * 50)
    print("  TEST CAN KLASYCZNY (Kanał 1, 500k)")
    print("=" * 50)
    
    vn = VN1640A()
    try:
        vn.open()
        vn.start(channel=1)
        
        print("\n[TEST] Nasłuchiwanie 5 sek...")
        messages = vn.receive_all(timeout_ms=5000, max_count=50)
        print(f"\n[TEST] Odebrano {len(messages)} wiadomości")
        
    finally:
        vn.close()


def quick_test_fd():
    """Test CAN FD."""
    print("\n" + "=" * 50)
    print("  TEST CAN FD (Kanał 1, 500k/2M)")
    print("=" * 50)
    
    vn = VN1640A()
    try:
        vn.open()
        vn.start_fd(channel=1)
        
        print("\n[TEST] Nasłuchiwanie 5 sek...")
        messages = vn.receive_all(timeout_ms=5000, max_count=50)
        print(f"\n[TEST] Odebrano {len(messages)} wiadomości")
        
    finally:
        vn.close()


def interactive():
    """Tryb interaktywny."""
    vn = VN1640A()
    
    print("\n" + "=" * 50)
    print("  VN1640A - CAN/CAN FD INTERFACE")
    print("  Kanał 1, 500 kbit/s")
    print("=" * 50)
    
    try:
        while True:
            print("\n--- MENU ---")
            print("1. Połącz CAN klasyczny")
            print("2. Połącz CAN FD")
            print("3. Rozłącz")
            print("4. Wyślij (11-bit ID)")
            print("5. Wyślij (29-bit Extended ID)")
            print("6. Wyślij FD (do 64 bajtów)")
            print("7. Odbierz (5 sek)")
            print("8. Nasłuchuj (Ctrl+C)")
            print("0. Wyjście")
            
            choice = input("\nWybór: ").strip()
            
            if choice == '1':
                if vn.open():
                    vn.start(channel=1)
                    
            elif choice == '2':
                if vn.open():
                    vn.start_fd(channel=1)
                    
            elif choice == '3':
                vn.close()
                
            elif choice == '4':
                if not vn.is_on_bus:
                    print("[INFO] Najpierw połącz")
                    continue
                try:
                    msg_id = int(input("ID (hex, np. 123): "), 16)
                    data_str = input("Dane (hex, np. 11 22 33): ").strip()
                    data = [int(x, 16) for x in data_str.split()] if data_str else []
                    vn.send(msg_id, data, extended=False)
                except ValueError as e:
                    print(f"[BŁĄD] {e}")
                    
            elif choice == '5':
                if not vn.is_on_bus:
                    print("[INFO] Najpierw połącz")
                    continue
                try:
                    msg_id = int(input("Extended ID (hex, np. 12345678): "), 16)
                    data_str = input("Dane (hex, np. 11 22 33): ").strip()
                    data = [int(x, 16) for x in data_str.split()] if data_str else []
                    vn.send(msg_id, data, extended=True)
                except ValueError as e:
                    print(f"[BŁĄD] {e}")
                    
            elif choice == '6':
                if not vn.is_on_bus:
                    print("[INFO] Najpierw połącz CAN FD (opcja 2)")
                    continue
                try:
                    msg_id = int(input("ID (hex): "), 16)
                    ext = input("Extended ID 29-bit? (t/n) [n]: ").lower() == 't'
                    data_str = input("Dane (hex, do 64 bajtów): ").strip()
                    data = [int(x, 16) for x in data_str.split()] if data_str else []
                    brs = input("BRS? (t/n) [t]: ").lower() != 'n'
                    vn.send_fd(msg_id, data, extended=ext, brs=brs)
                except ValueError as e:
                    print(f"[BŁĄD] {e}")
                    
            elif choice == '7':
                if not vn.is_on_bus:
                    print("[INFO] Najpierw połącz")
                    continue
                print("[INFO] Odbieranie 5 sek...")
                messages = vn.receive_all(timeout_ms=5000)
                print(f"[INFO] Odebrano {len(messages)} wiadomości")
                
            elif choice == '8':
                if not vn.is_on_bus:
                    print("[INFO] Najpierw połącz")
                    continue
                print("[INFO] Nasłuchiwanie (Ctrl+C)...")
                try:
                    while True:
                        vn.receive(timeout_ms=100)
                except KeyboardInterrupt:
                    print("\n[INFO] Przerwano")
                    
            elif choice == '0':
                break
                
    except KeyboardInterrupt:
        pass
    finally:
        vn.close()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  VECTOR VN1640A - CAN / CAN FD")
    print("  Kanał 1, 500 kbit/s (2 Mbit/s FD)")
    print("=" * 50)
    
    print("\nOpcje:")
    print("  1 - Test CAN klasyczny")
    print("  2 - Test CAN FD")
    print("  3 - Tryb interaktywny")
    
    try:
        choice = input("\nWybór [3]: ").strip() or "3"
        
        if choice == '1':
            quick_test_can()
        elif choice == '2':
            quick_test_fd()
        elif choice == '3':
            interactive()
            
    except Exception as e:
        print(f"\n[BŁĄD] {e}")
        import traceback
        traceback.print_exc()
