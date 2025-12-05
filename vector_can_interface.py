"""
Interfejs komunikacji CAN z urządzeniem Vector VN1640A
Obsługa 4 kanałów CAN z możliwością włączania/wyłączania
Autor: GitHub Copilot
Data: 2024
"""

import ctypes
from ctypes import c_uint, c_int, c_char, c_ubyte, c_ushort, c_ulong, c_ulonglong
from ctypes import Structure, POINTER, byref, sizeof, create_string_buffer
from typing import Optional, List, Dict, Tuple
from enum import IntEnum, IntFlag
from dataclasses import dataclass
import time


# ============================================================================
# STAŁE I DEFINICJE Z VXLAPI
# ============================================================================

# Ścieżka do biblioteki Vector XL Driver
VXLAPI_DLL = "vxlapi64.dll"  # Dla 64-bit, użyj "vxlapi.dll" dla 32-bit

# Status kody
XL_SUCCESS = 0
XL_ERR_QUEUE_IS_EMPTY = 10
XL_ERR_NO_LICENSE = 14

# Typy kanałów
XL_BUS_TYPE_CAN = 0x00000001

# Flagi dostępu
XL_INTERFACE_VERSION = 3
XL_ACTIVATE_NONE = 0
XL_ACTIVATE_RESET_CLOCK = 8

# Tryby CAN
XL_CAN_CMD_TX = 0x0001
XL_CAN_TXMSG_FLAG_NO_TX_COMPLETE = 0x0040

# Typy zdarzeń
XL_RECEIVE_MSG = 1
XL_CHIP_STATE = 4
XL_TRANSCEIVER = 6
XL_TIMER = 8
XL_TRANSMIT_MSG = 10

# Prędkości CAN (baud rate)
class CANBaudrate(IntEnum):
    BAUD_1M = 1000000
    BAUD_500K = 500000
    BAUD_250K = 250000
    BAUD_125K = 125000
    BAUD_100K = 100000
    BAUD_50K = 50000
    BAUD_20K = 20000
    BAUD_10K = 10000


# ============================================================================
# STRUKTURY VXLAPI
# ============================================================================

XLuint64 = c_ulonglong
XLaccess = c_ulonglong
XLhandle = ctypes.c_void_p
XLstatus = c_int
XLportHandle = c_long = ctypes.c_long


class XLcanTxEvent(Structure):
    _fields_ = [
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("channelIndex", c_ubyte),
        ("reserved", c_ubyte * 3),
        ("id", c_uint),
        ("dlc", c_ushort),
        ("msgFlags", c_ushort),
        ("data", c_ubyte * 8),
    ]


class XLeventTag(Structure):
    _fields_ = [
        ("msg", XLcanTxEvent),
    ]


class XLevent(Structure):
    _fields_ = [
        ("tag", c_ubyte),
        ("chanIndex", c_ubyte),
        ("transId", c_ushort),
        ("portHandle", c_ushort),
        ("flags", c_ubyte),
        ("reserved", c_ubyte),
        ("timeStamp", XLuint64),
        ("tagData", XLeventTag),
    ]


class XLchannelConfig(Structure):
    _fields_ = [
        ("name", c_char * 32),
        ("hwType", c_ubyte),
        ("hwIndex", c_ubyte),
        ("hwChannel", c_ubyte),
        ("transceiverType", c_ushort),
        ("transceiverState", c_ushort),
        ("configError", c_ushort),
        ("channelIndex", c_ubyte),
        ("channelMask", XLuint64),
        ("channelCapabilities", c_uint),
        ("channelBusCapabilities", c_uint),
        ("isOnBus", c_ubyte),
        ("connectedBusType", c_uint),
        ("busParams", c_ubyte * 32),
        ("driverVersion", c_uint),
        ("interfaceVersion", c_uint),
        ("raw_data", c_uint * 10),
        ("serialNumber", c_uint),
        ("articleNumber", c_uint),
        ("transceiverName", c_char * 32),
        ("specialCabFlags", c_uint),
        ("dominantTimeout", c_uint),
        ("dominantRecessiveDelay", c_ubyte),
        ("recessiveDominantDelay", c_ubyte),
        ("connectionInfo", c_ubyte),
        ("currentlyAvailableTimestamps", c_ubyte),
        ("minimalSupplyVoltage", c_ushort),
        ("maximalSupplyVoltage", c_ushort),
        ("maximalBaudrate", c_uint),
        ("fpgaCoreCapabilities", c_ubyte),
        ("specialDeviceStatus", c_ubyte),
        ("channelBusActiveCapabilities", c_ushort),
        ("breakOffset", c_ushort),
        ("delimiterOffset", c_ushort),
        ("reserved", c_uint * 3),
    ]


class XLdriverConfig(Structure):
    _fields_ = [
        ("dllVersion", c_uint),
        ("channelCount", c_uint),
        ("reserved", c_uint * 10),
        ("channel", XLchannelConfig * 64),
    ]


# ============================================================================
# KLASA WIADOMOŚCI CAN
# ============================================================================

@dataclass
class CANMessage:
    """Reprezentacja wiadomości CAN."""
    id: int
    data: bytes
    dlc: int = None
    timestamp: float = 0.0
    channel: int = 0
    is_extended: bool = False
    is_remote: bool = False
    
    def __post_init__(self):
        if self.dlc is None:
            self.dlc = len(self.data)
        # Upewnij się, że data ma max 8 bajtów
        if len(self.data) > 8:
            self.data = self.data[:8]
    
    def __repr__(self):
        hex_data = ' '.join(f'{b:02X}' for b in self.data)
        return f"CAN[CH{self.channel}] ID=0x{self.id:03X} DLC={self.dlc} Data=[{hex_data}]"


# ============================================================================
# GŁÓWNA KLASA INTERFEJSU VECTOR CAN
# ============================================================================

class VectorCANInterface:
    """
    Interfejs do komunikacji CAN przez urządzenie Vector VN1640A.
    Obsługuje 4 kanały CAN z możliwością indywidualnego włączania/wyłączania.
    """
    
    # VN1640A ma 4 kanały CAN
    MAX_CHANNELS = 4
    
    def __init__(self, dll_path: str = VXLAPI_DLL):
        """
        Inicjalizacja interfejsu.
        
        Args:
            dll_path: Ścieżka do biblioteki vxlapi64.dll
        """
        self.dll_path = dll_path
        self.dll: Optional[ctypes.CDLL] = None
        self.driver_config: Optional[XLdriverConfig] = None
        
        # Stan kanałów
        self.port_handle: XLportHandle = XLportHandle()
        self.access_mask: XLaccess = XLaccess(0)
        self.permission_mask: XLaccess = XLaccess(0)
        
        # Konfiguracja kanałów (indeks 0-3 dla 4 kanałów)
        self.channel_masks: List[XLaccess] = [XLaccess(0)] * self.MAX_CHANNELS
        self.channel_enabled: List[bool] = [False] * self.MAX_CHANNELS
        self.channel_baudrate: List[int] = [CANBaudrate.BAUD_500K] * self.MAX_CHANNELS
        
        # Stan połączenia
        self.is_connected = False
        self.is_on_bus = False
        
        # Informacje o urządzeniu
        self.device_info: Dict = {}
        
    def load_dll(self) -> bool:
        """Ładuje bibliotekę Vector XL Driver."""
        try:
            self.dll = ctypes.windll.LoadLibrary(self.dll_path)
            print(f"[OK] Załadowano bibliotekę: {self.dll_path}")
            return True
        except OSError as e:
            print(f"[BŁĄD] Nie można załadować {self.dll_path}: {e}")
            print("       Upewnij się, że Vector Driver Library jest zainstalowana.")
            print("       Domyślna lokalizacja: C:\\Users\\Public\\Documents\\Vector XL Driver Library\\")
            return False
    
    def open_driver(self) -> bool:
        """Otwiera sterownik i pobiera konfigurację."""
        if not self.dll:
            if not self.load_dll():
                return False
        
        # Otwórz sterownik
        status = self.dll.xlOpenDriver()
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlOpenDriver zwróciło: {status}")
            return False
        
        print("[OK] Sterownik Vector otwarty")
        
        # Pobierz konfigurację
        self.driver_config = XLdriverConfig()
        status = self.dll.xlGetDriverConfig(byref(self.driver_config))
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlGetDriverConfig zwróciło: {status}")
            return False
        
        print(f"[OK] Znaleziono {self.driver_config.channelCount} kanałów")
        self._parse_channel_config()
        
        self.is_connected = True
        return True
    
    def _parse_channel_config(self):
        """Parsuje konfigurację kanałów i znajduje kanały VN1640A."""
        vn1640_channels = []
        channel_index = 0  # Licznik kanałów VN1640
        
        for i in range(self.driver_config.channelCount):
            ch = self.driver_config.channel[i]
            name = ch.name.decode('utf-8', errors='ignore').strip()
            
            # Szukaj kanałów VN1640 (lub innych urządzeń Vector CAN)
            if 'VN1640' in name or 'VN16' in name or ch.hwType == 57:
                vn1640_channels.append({
                    'index': i,
                    'name': name,
                    'hw_channel': ch.hwChannel,
                    'channel_mask': ch.channelMask,
                    'serial': ch.serialNumber,
                    'on_bus': ch.isOnBus,
                    'transceiver': ch.transceiverName.decode('utf-8', errors='ignore'),
                    'channel_index': channel_index,
                })
                
                # Przypisz maskę kanału sekwencyjnie (0, 1, 2, 3)
                if channel_index < self.MAX_CHANNELS:
                    self.channel_masks[channel_index] = XLaccess(ch.channelMask)
                
                channel_index += 1
        
        self.device_info['channels'] = vn1640_channels
        self.device_info['channel_count'] = channel_index
        
        print(f"\n=== Kanały VN1640A ({channel_index} znalezionych) ===")
        for ch in vn1640_channels:
            status = "ON BUS" if ch['on_bus'] else "OFF BUS"
            print(f"  Kanał {ch['channel_index'] + 1}: {ch['name']} [{status}]")
            print(f"           Maska: 0x{ch['channel_mask']:X}, SN: {ch['serial']}")
    
    def enable_channel(self, channel: int, enabled: bool = True) -> bool:
        """
        Włącza lub wyłącza kanał CAN.
        
        Args:
            channel: Numer kanału (1-4)
            enabled: True = włącz, False = wyłącz
        
        Returns:
            True jeśli operacja się powiodła
        """
        if channel < 1 or channel > self.MAX_CHANNELS:
            print(f"[BŁĄD] Nieprawidłowy numer kanału: {channel}. Użyj 1-{self.MAX_CHANNELS}")
            return False
        
        idx = channel - 1  # Konwertuj na indeks 0-based
        self.channel_enabled[idx] = enabled
        
        status = "WŁĄCZONY" if enabled else "WYŁĄCZONY"
        print(f"[OK] Kanał {channel} -> {status}")
        
        return True
    
    def set_channel_baudrate(self, channel: int, baudrate: int) -> bool:
        """
        Ustawia prędkość transmisji dla kanału.
        
        Args:
            channel: Numer kanału (1-4)
            baudrate: Prędkość w bit/s (np. 500000 dla 500 kbit/s)
        """
        if channel < 1 or channel > self.MAX_CHANNELS:
            print(f"[BŁĄD] Nieprawidłowy numer kanału: {channel}")
            return False
        
        idx = channel - 1
        self.channel_baudrate[idx] = baudrate
        
        print(f"[OK] Kanał {channel} -> Baudrate: {baudrate // 1000} kbit/s")
        return True
    
    def get_enabled_channels(self) -> List[int]:
        """Zwraca listę włączonych kanałów (1-based)."""
        return [i + 1 for i, enabled in enumerate(self.channel_enabled) if enabled]
    
    def _build_access_mask(self) -> XLaccess:
        """Buduje maskę dostępu na podstawie włączonych kanałów."""
        mask = 0
        for i in range(self.MAX_CHANNELS):
            if self.channel_enabled[i]:
                mask |= self.channel_masks[i].value
        return XLaccess(mask)
    
    def open_port(self, app_name: str = "PythonCAN") -> bool:
        """
        Otwiera port dla włączonych kanałów.
        
        Args:
            app_name: Nazwa aplikacji (widoczna w Vector Hardware Config)
        """
        if not self.is_connected:
            print("[BŁĄD] Najpierw połącz z sterownikiem (open_driver)")
            return False
        
        enabled = self.get_enabled_channels()
        if not enabled:
            print("[BŁĄD] Brak włączonych kanałów. Użyj enable_channel()")
            return False
        
        print(f"\n[INFO] Otwieranie portu dla kanałów: {enabled}")
        
        # Zbuduj maskę dostępu
        self.access_mask = self._build_access_mask()
        self.permission_mask = self.access_mask
        
        # Otwórz port
        app_name_bytes = app_name.encode('utf-8')
        
        status = self.dll.xlOpenPort(
            byref(self.port_handle),
            app_name_bytes,
            self.access_mask,
            byref(self.permission_mask),
            c_uint(256),  # rxQueueSize
            c_uint(XL_INTERFACE_VERSION),
            c_uint(XL_BUS_TYPE_CAN)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlOpenPort zwróciło: {status}")
            if status == XL_ERR_NO_LICENSE:
                print("       Brak licencji Vector!")
            return False
        
        print(f"[OK] Port otwarty. Handle: {self.port_handle.value}")
        print(f"     Access mask: 0x{self.access_mask.value:X}")
        print(f"     Permission mask: 0x{self.permission_mask.value:X}")
        
        return True
    
    def set_baudrate(self) -> bool:
        """Ustawia prędkość transmisji dla wszystkich włączonych kanałów."""
        for i in range(self.MAX_CHANNELS):
            if self.channel_enabled[i] and self.channel_masks[i].value:
                status = self.dll.xlCanSetChannelBitrate(
                    self.port_handle,
                    self.channel_masks[i],
                    c_uint(self.channel_baudrate[i])
                )
                
                if status != XL_SUCCESS:
                    print(f"[BŁĄD] Nie można ustawić baudrate dla kanału {i+1}: {status}")
                    return False
                
                print(f"[OK] Kanał {i+1}: {self.channel_baudrate[i] // 1000} kbit/s")
        
        return True
    
    def go_on_bus(self) -> bool:
        """Aktywuje transmisję na magistrali CAN."""
        if not self.port_handle.value:
            print("[BŁĄD] Port nie jest otwarty")
            return False
        
        status = self.dll.xlActivateChannel(
            self.port_handle,
            self.access_mask,
            c_uint(XL_BUS_TYPE_CAN),
            c_uint(XL_ACTIVATE_RESET_CLOCK)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlActivateChannel zwróciło: {status}")
            return False
        
        self.is_on_bus = True
        print("[OK] Kanały aktywne - ON BUS")
        return True
    
    def go_off_bus(self) -> bool:
        """Dezaktywuje transmisję na magistrali CAN."""
        if not self.is_on_bus:
            return True
        
        status = self.dll.xlDeactivateChannel(
            self.port_handle,
            self.access_mask
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlDeactivateChannel zwróciło: {status}")
            return False
        
        self.is_on_bus = False
        print("[OK] Kanały nieaktywne - OFF BUS")
        return True
    
    def send_message(self, msg: CANMessage, channel: int = 1) -> bool:
        """
        Wysyła wiadomość CAN.
        
        Args:
            msg: Wiadomość CAN do wysłania
            channel: Numer kanału (1-4)
        """
        if not self.is_on_bus:
            print("[BŁĄD] Nie jesteś na magistrali. Użyj go_on_bus()")
            return False
        
        if channel < 1 or channel > self.MAX_CHANNELS:
            print(f"[BŁĄD] Nieprawidłowy kanał: {channel}")
            return False
        
        idx = channel - 1
        if not self.channel_enabled[idx]:
            print(f"[BŁĄD] Kanał {channel} nie jest włączony")
            return False
        
        # Przygotuj strukturę zdarzenia
        event = XLevent()
        event.tag = XL_TRANSMIT_MSG
        event.tagData.msg.id = msg.id
        event.tagData.msg.dlc = msg.dlc
        event.tagData.msg.msgFlags = 0
        
        # Kopiuj dane
        for i, byte in enumerate(msg.data[:8]):
            event.tagData.msg.data[i] = byte
        
        # Wyślij
        msg_count = c_uint(1)
        status = self.dll.xlCanTransmit(
            self.port_handle,
            self.channel_masks[idx],
            byref(msg_count),
            byref(event)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlCanTransmit zwróciło: {status}")
            return False
        
        print(f"[TX] {msg}")
        return True
    
    def receive_message(self, timeout_ms: int = 100) -> Optional[CANMessage]:
        """
        Odbiera wiadomość CAN.
        
        Args:
            timeout_ms: Timeout w milisekundach
        
        Returns:
            CANMessage lub None jeśli brak wiadomości
        """
        if not self.is_on_bus:
            return None
        
        event = XLevent()
        event_count = c_uint(1)
        
        status = self.dll.xlReceive(
            self.port_handle,
            byref(event_count),
            byref(event)
        )
        
        if status == XL_ERR_QUEUE_IS_EMPTY:
            return None
        
        if status != XL_SUCCESS:
            return None
        
        # Sprawdź typ zdarzenia
        if event.tag == XL_RECEIVE_MSG:
            msg_data = event.tagData.msg
            
            data = bytes(msg_data.data[:msg_data.dlc])
            
            can_msg = CANMessage(
                id=msg_data.id & 0x1FFFFFFF,  # Usuń flagi
                data=data,
                dlc=msg_data.dlc,
                timestamp=event.timeStamp / 1e9,  # Konwertuj na sekundy
                channel=event.chanIndex + 1,
                is_extended=(msg_data.id & 0x80000000) != 0,
                is_remote=(msg_data.msgFlags & 0x0010) != 0,
            )
            
            print(f"[RX] {can_msg}")
            return can_msg
        
        return None
    
    def receive_messages(self, count: int = 10, timeout_ms: int = 1000) -> List[CANMessage]:
        """
        Odbiera wiele wiadomości CAN.
        
        Args:
            count: Maksymalna liczba wiadomości do odebrania
            timeout_ms: Całkowity timeout w milisekundach
        """
        messages = []
        start_time = time.time()
        timeout_s = timeout_ms / 1000.0
        
        while len(messages) < count:
            if time.time() - start_time > timeout_s:
                break
            
            msg = self.receive_message(timeout_ms=10)
            if msg:
                messages.append(msg)
            else:
                time.sleep(0.001)  # Krótka pauza
        
        return messages
    
    def close(self):
        """Zamyka połączenie i zwalnia zasoby."""
        if self.is_on_bus:
            self.go_off_bus()
        
        if self.port_handle.value:
            self.dll.xlClosePort(self.port_handle)
            print("[OK] Port zamknięty")
        
        if self.dll:
            self.dll.xlCloseDriver()
            print("[OK] Sterownik zamknięty")
        
        self.is_connected = False
        self.is_on_bus = False
    
    def __enter__(self):
        """Context manager - wejście."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager - wyjście."""
        self.close()
        return False
    
    # ========================================================================
    # METODY POMOCNICZE - SZYBKA KONFIGURACJA
    # ========================================================================
    
    def quick_setup(self, channels: List[int] = [1], baudrate: int = CANBaudrate.BAUD_500K) -> bool:
        """
        Szybka konfiguracja - otwiera sterownik, włącza kanały i przechodzi on bus.
        
        Args:
            channels: Lista kanałów do włączenia (1-4)
            baudrate: Prędkość transmisji dla wszystkich kanałów
        
        Example:
            can.quick_setup([1, 2], CANBaudrate.BAUD_500K)
        """
        print("\n" + "=" * 50)
        print("  SZYBKA KONFIGURACJA VN1640A")
        print("=" * 50)
        
        # 1. Otwórz sterownik
        if not self.open_driver():
            return False
        
        # 2. Włącz kanały
        for ch in channels:
            self.enable_channel(ch, True)
            self.set_channel_baudrate(ch, baudrate)
        
        # 3. Otwórz port
        if not self.open_port():
            return False
        
        # 4. Ustaw baudrate
        if not self.set_baudrate():
            return False
        
        # 5. Przejdź on bus
        if not self.go_on_bus():
            return False
        
        print("\n" + "=" * 50)
        print(f"  GOTOWE! Aktywne kanały: {self.get_enabled_channels()}")
        print("=" * 50 + "\n")
        
        return True
    
    def print_status(self):
        """Wyświetla aktualny status interfejsu."""
        print("\n=== STATUS VN1640A ===")
        print(f"  Połączony: {'TAK' if self.is_connected else 'NIE'}")
        print(f"  On Bus: {'TAK' if self.is_on_bus else 'NIE'}")
        print(f"  Port Handle: {self.port_handle.value}")
        print(f"  Access Mask: 0x{self.access_mask.value:X}")
        print("\n  Kanały:")
        for i in range(self.MAX_CHANNELS):
            status = "WŁĄCZONY" if self.channel_enabled[i] else "wyłączony"
            baud = self.channel_baudrate[i] // 1000
            mask = self.channel_masks[i].value
            print(f"    CH{i+1}: {status:10} | {baud:4} kbit/s | Mask: 0x{mask:X}")
        print()


# ============================================================================
# PRZYKŁAD UŻYCIA
# ============================================================================

def demo_basic():
    """Podstawowa demonstracja - tylko kanał 1."""
    print("\n" + "=" * 60)
    print("  DEMO: Podstawowa komunikacja CAN (Kanał 1)")
    print("=" * 60)
    
    can = VectorCANInterface()
    
    try:
        # Szybka konfiguracja - tylko kanał 1, 500 kbit/s
        if not can.quick_setup(channels=[1], baudrate=CANBaudrate.BAUD_500K):
            print("[BŁĄD] Nie udało się skonfigurować interfejsu")
            return
        
        # Wyświetl status
        can.print_status()
        
        # Wyślij testową wiadomość
        test_msg = CANMessage(
            id=0x123,
            data=bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88])
        )
        can.send_message(test_msg, channel=1)
        
        # Nasłuchuj przez 3 sekundy
        print("\n[INFO] Nasłuchiwanie przez 3 sekundy...")
        messages = can.receive_messages(count=100, timeout_ms=3000)
        
        print(f"\n[INFO] Odebrano {len(messages)} wiadomości")
        
    finally:
        can.close()


def demo_multi_channel():
    """Demonstracja z wieloma kanałami."""
    print("\n" + "=" * 60)
    print("  DEMO: Multi-kanałowa komunikacja CAN")
    print("=" * 60)
    
    can = VectorCANInterface()
    
    try:
        # Otwórz sterownik
        if not can.open_driver():
            return
        
        # Włącz kanały 1 i 2 z różnymi prędkościami
        can.enable_channel(1, True)
        can.set_channel_baudrate(1, CANBaudrate.BAUD_500K)
        
        can.enable_channel(2, True)
        can.set_channel_baudrate(2, CANBaudrate.BAUD_250K)
        
        # Kanały 3 i 4 wyłączone
        can.enable_channel(3, False)
        can.enable_channel(4, False)
        
        # Otwórz port i przejdź on bus
        can.open_port("MultiChannelDemo")
        can.set_baudrate()
        can.go_on_bus()
        
        can.print_status()
        
        # Wyślij wiadomości na różne kanały
        msg1 = CANMessage(id=0x100, data=bytes([0x01, 0x02, 0x03]))
        msg2 = CANMessage(id=0x200, data=bytes([0x0A, 0x0B, 0x0C]))
        
        can.send_message(msg1, channel=1)
        can.send_message(msg2, channel=2)
        
        # Nasłuchuj
        time.sleep(1)
        messages = can.receive_messages(count=50, timeout_ms=2000)
        
    finally:
        can.close()


def demo_channel_switching():
    """Demonstracja przełączania między kanałami."""
    print("\n" + "=" * 60)
    print("  DEMO: Przełączanie kanałów")
    print("=" * 60)
    
    can = VectorCANInterface()
    
    try:
        can.open_driver()
        
        # Scenariusz 1: Tylko kanał 1
        print("\n--- Scenariusz 1: Kanał 1 ---")
        can.enable_channel(1, True)
        can.enable_channel(2, False)
        can.enable_channel(3, False)
        can.enable_channel(4, False)
        print(f"Aktywne kanały: {can.get_enabled_channels()}")
        
        # Scenariusz 2: Kanały 1 i 3
        print("\n--- Scenariusz 2: Kanały 1 i 3 ---")
        can.enable_channel(3, True)
        print(f"Aktywne kanały: {can.get_enabled_channels()}")
        
        # Scenariusz 3: Wszystkie kanały
        print("\n--- Scenariusz 3: Wszystkie kanały ---")
        can.enable_channel(2, True)
        can.enable_channel(4, True)
        print(f"Aktywne kanały: {can.get_enabled_channels()}")
        
        can.print_status()
        
    finally:
        can.close()


# ============================================================================
# GŁÓWNA FUNKCJA
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  VECTOR VN1640A - INTERFEJS CAN DLA PYTHON")
    print("=" * 60)
    print("\nDostępne demo:")
    print("  1. demo_basic()          - Podstawowa komunikacja (CH1)")
    print("  2. demo_multi_channel()  - Wiele kanałów")
    print("  3. demo_channel_switching() - Przełączanie kanałów")
    print("\nWybierz demo lub użyj klasy VectorCANInterface bezpośrednio.")
    print("-" * 60)
    
    # Uruchom podstawowe demo
    try:
        demo_channel_switching()
    except Exception as e:
        print(f"\n[BŁĄD] {e}")
        print("\nMożliwe przyczyny:")
        print("  1. Brak zainstalowanej biblioteki Vector XL Driver")
        print("  2. Urządzenie VN1640A nie jest podłączone")
        print("  3. Sterowniki Vector nie są zainstalowane")
        print("  4. Inny program używa urządzenia (np. CANoe)")
