"""
Vector VN1640A CAN Interface - Wersja bezpośrednia (bez python-can)
Używa bezpośrednio vxlapi64.dll z prawidłowo zdefiniowanymi strukturami

Autor: GitHub Copilot
Dla: VN1640A (4 kanały CAN)
"""

import ctypes
from ctypes import (
    c_uint, c_int, c_char, c_ubyte, c_ushort, c_ulong, c_ulonglong,
    c_uint64, c_int64, c_void_p, c_char_p,
    Structure, Union, POINTER, byref, sizeof, create_string_buffer
)
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
from enum import IntEnum
import time
import threading


# ============================================================================
# STAŁE VXLAPI
# ============================================================================

XL_SUCCESS = 0
XL_PENDING = 1
XL_ERR_QUEUE_IS_EMPTY = 10
XL_ERR_QUEUE_IS_FULL = 11
XL_ERR_INVALID_ACCESS = 13
XL_ERR_NO_LICENSE = 14
XL_ERR_WRONG_PARAMETER = 101
XL_ERR_HW_NOT_PRESENT = 129

XL_BUS_TYPE_CAN = 0x00000001
XL_INTERFACE_VERSION = 3
XL_ACTIVATE_RESET_CLOCK = 8

XL_RECEIVE_MSG = 1
XL_CHIP_STATE = 4
XL_TRANSMIT_MSG = 10
XL_SYNC_PULSE = 11
XL_APPLICATION_NOTIFICATION = 15

XL_CAN_EXT_MSG_ID = 0x80000000

XL_HWTYPE_VN1610 = 55
XL_HWTYPE_VN1630 = 57
XL_HWTYPE_VN1640 = 57


class CANBaudrate(IntEnum):
    """Prędkości CAN w bit/s."""
    BAUD_1M = 1000000
    BAUD_500K = 500000
    BAUD_250K = 250000
    BAUD_125K = 125000
    BAUD_100K = 100000


# ============================================================================
# STRUKTURY VXLAPI (wyrównane dla 64-bit)
# ============================================================================

class s_xl_can_msg(Structure):
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


class s_xl_sync_pulse(Structure):
    _fields_ = [
        ("pulseCode", c_ubyte),
        ("time", c_uint64),
    ]


class s_xl_tag_data(Union):
    _fields_ = [
        ("msg", s_xl_can_msg),
        ("chipState", s_xl_chip_state),
        ("syncPulse", s_xl_sync_pulse),
    ]


class XLevent(Structure):
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
# KLASA WIADOMOŚCI CAN
# ============================================================================

@dataclass
class CANMessage:
    """Wiadomość CAN."""
    id: int
    data: bytes
    dlc: int = None
    channel: int = 1
    timestamp: float = 0.0
    is_extended: bool = False
    
    def __post_init__(self):
        if self.dlc is None:
            self.dlc = len(self.data)
        if len(self.data) > 8:
            self.data = self.data[:8]
    
    def __repr__(self):
        hex_data = ' '.join(f'{b:02X}' for b in self.data)
        id_fmt = f"0x{self.id:08X}" if self.is_extended else f"0x{self.id:03X}"
        return f"CAN[CH{self.channel}] ID={id_fmt} DLC={self.dlc} Data=[{hex_data}]"


# ============================================================================
# GŁÓWNA KLASA VN1640A
# ============================================================================

class VN1640A:
    """
    Interfejs do komunikacji z Vector VN1640A.
    
    Obsługuje 4 kanały CAN z możliwością indywidualnego zarządzania.
    Używa bezpośrednio vxlapi64.dll bez potrzeby konfiguracji w Vector HW Config.
    
    Przykład:
        vn = VN1640A()
        vn.open()
        vn.enable_channel(1)  # Włącz kanał 1
        vn.start()            # Przejdź on bus
        vn.send(0x123, [0x11, 0x22, 0x33])
        msg = vn.receive()
        vn.stop()
        vn.close()
    """
    
    NUM_CHANNELS = 4
    DLL_NAME = "vxlapi64.dll"
    
    def __init__(self):
        self.dll: ctypes.CDLL = None
        
        # Konfiguracja kanałów (1-4)
        self.channel_config: Dict[int, Dict] = {}
        for i in range(1, self.NUM_CHANNELS + 1):
            self.channel_config[i] = {
                'enabled': False,
                'baudrate': CANBaudrate.BAUD_500K,
                'mask': 0,
                'hw_channel': i - 1,
                'index': -1,
            }
        
        # Stan
        self.port_handle = c_int(-1)
        self.access_mask = c_uint64(0)
        self.permission_mask = c_uint64(0)
        self.is_open = False
        self.is_on_bus = False
        
        # Callback dla RX
        self._rx_callback: Optional[Callable] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._rx_running = False
    
    # ========================================================================
    # INICJALIZACJA
    # ========================================================================
    
    def open(self) -> bool:
        """Otwiera sterownik Vector i wykrywa kanały VN1640A."""
        try:
            self.dll = ctypes.windll.LoadLibrary(self.DLL_NAME)
            print(f"[OK] Załadowano {self.DLL_NAME}")
        except OSError as e:
            print(f"[BŁĄD] Nie można załadować {self.DLL_NAME}: {e}")
            return False
        
        # Otwórz sterownik
        status = self.dll.xlOpenDriver()
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlOpenDriver: {status}")
            return False
        
        print("[OK] Sterownik Vector otwarty")
        
        # Pobierz konfigurację kanałów
        self._detect_channels()
        
        self.is_open = True
        return True
    
    def _detect_channels(self):
        """Wykrywa kanały VN1640A."""
        # Pobierz liczbę kanałów
        channel_count = c_uint(0)
        channel_mask = c_uint64(0)
        
        self.dll.xlGetChannelIndex.restype = c_int
        self.dll.xlGetChannelMask.restype = c_uint64
        
        # Iteruj przez kanały sprzętowe (0-3 dla VN1640A)
        print("\n[INFO] Wykrywanie kanałów VN1640A...")
        
        for hw_ch in range(4):
            # Pobierz maskę kanału
            # xlGetChannelMask(hwType, hwIndex, hwChannel)
            mask = self.dll.xlGetChannelMask(
                c_int(XL_HWTYPE_VN1640),  # hwType
                c_int(0),                  # hwIndex (pierwsze urządzenie)
                c_int(hw_ch)               # hwChannel
            )
            
            if mask > 0:
                ch_num = hw_ch + 1
                self.channel_config[ch_num]['mask'] = mask
                self.channel_config[ch_num]['index'] = hw_ch
                print(f"  CH{ch_num}: Maska=0x{mask:X}")
    
    def close(self):
        """Zamyka sterownik i zwalnia zasoby."""
        if self.is_on_bus:
            self.stop()
        
        if self.port_handle.value >= 0:
            self.dll.xlClosePort(self.port_handle)
            self.port_handle = c_int(-1)
        
        if self.dll:
            self.dll.xlCloseDriver()
        
        self.is_open = False
        print("[OK] Sterownik zamknięty")
    
    # ========================================================================
    # ZARZĄDZANIE KANAŁAMI
    # ========================================================================
    
    def enable_channel(self, channel: int, baudrate: int = CANBaudrate.BAUD_500K) -> bool:
        """
        Włącza kanał CAN.
        
        Args:
            channel: Numer kanału (1-4)
            baudrate: Prędkość w bit/s
        """
        if channel < 1 or channel > self.NUM_CHANNELS:
            print(f"[BŁĄD] Nieprawidłowy kanał: {channel}")
            return False
        
        cfg = self.channel_config[channel]
        cfg['enabled'] = True
        cfg['baudrate'] = baudrate
        
        # Aktualizuj access mask
        self.access_mask.value |= cfg['mask']
        
        print(f"[OK] Kanał {channel} włączony ({baudrate // 1000} kbit/s)")
        return True
    
    def disable_channel(self, channel: int) -> bool:
        """Wyłącza kanał CAN."""
        if channel < 1 or channel > self.NUM_CHANNELS:
            return False
        
        cfg = self.channel_config[channel]
        cfg['enabled'] = False
        
        # Usuń z access mask
        self.access_mask.value &= ~cfg['mask']
        
        print(f"[OK] Kanał {channel} wyłączony")
        return True
    
    def get_enabled_channels(self) -> List[int]:
        """Zwraca listę włączonych kanałów."""
        return [ch for ch, cfg in self.channel_config.items() if cfg['enabled']]
    
    # ========================================================================
    # POŁĄCZENIE Z MAGISTRALĄ
    # ========================================================================
    
    def start(self, app_name: str = "PythonCAN") -> bool:
        """
        Otwiera port i przechodzi on bus.
        
        Args:
            app_name: Nazwa aplikacji
        """
        if not self.is_open:
            print("[BŁĄD] Najpierw otwórz sterownik (open())")
            return False
        
        enabled = self.get_enabled_channels()
        if not enabled:
            print("[BŁĄD] Brak włączonych kanałów!")
            return False
        
        print(f"\n[INFO] Uruchamianie kanałów: {enabled}")
        
        # Otwórz port
        self.permission_mask = c_uint64(self.access_mask.value)
        
        status = self.dll.xlOpenPort(
            byref(self.port_handle),
            app_name.encode('utf-8'),
            self.access_mask,
            byref(self.permission_mask),
            c_uint(256),  # rxQueueSize
            c_uint(XL_INTERFACE_VERSION),
            c_uint(XL_BUS_TYPE_CAN)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlOpenPort: {status}")
            self._print_error_help(status)
            return False
        
        print(f"[OK] Port otwarty (handle={self.port_handle.value})")
        
        # Ustaw baudrate dla każdego kanału
        for ch_num, cfg in self.channel_config.items():
            if cfg['enabled'] and cfg['mask']:
                status = self.dll.xlCanSetChannelBitrate(
                    self.port_handle,
                    c_uint64(cfg['mask']),
                    c_uint(cfg['baudrate'])
                )
                if status != XL_SUCCESS:
                    print(f"[WARN] Nie można ustawić baudrate dla CH{ch_num}: {status}")
                else:
                    print(f"[OK] CH{ch_num}: {cfg['baudrate'] // 1000} kbit/s")
        
        # Aktywuj kanały (go on bus)
        status = self.dll.xlActivateChannel(
            self.port_handle,
            self.access_mask,
            c_uint(XL_BUS_TYPE_CAN),
            c_uint(XL_ACTIVATE_RESET_CLOCK)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD] xlActivateChannel: {status}")
            return False
        
        self.is_on_bus = True
        print("[OK] Kanały aktywne - ON BUS")
        return True
    
    def stop(self):
        """Rozłącza z magistrali (go off bus)."""
        if not self.is_on_bus:
            return
        
        self._stop_rx_thread()
        
        self.dll.xlDeactivateChannel(self.port_handle, self.access_mask)
        self.is_on_bus = False
        print("[OK] OFF BUS")
    
    def _print_error_help(self, error_code: int):
        """Wyświetla pomoc dla błędu."""
        errors = {
            XL_ERR_NO_LICENSE: "Brak licencji Vector!",
            XL_ERR_HW_NOT_PRESENT: "Urządzenie nie jest podłączone!",
            XL_ERR_INVALID_ACCESS: "Nieprawidłowy dostęp - czy CANoe jest zamknięte?",
            255: "Kanał nie jest skonfigurowany w Vector Hardware Config",
        }
        if error_code in errors:
            print(f"       {errors[error_code]}")
    
    # ========================================================================
    # WYSYŁANIE I ODBIERANIE
    # ========================================================================
    
    def send(self, msg_id: int, data: list, channel: int = 1, extended: bool = False) -> bool:
        """
        Wysyła wiadomość CAN.
        
        Args:
            msg_id: ID wiadomości
            data: Lista bajtów (max 8)
            channel: Numer kanału (1-4)
            extended: True dla 29-bit ID
        """
        if not self.is_on_bus:
            print("[BŁĄD] Nie jesteś on bus!")
            return False
        
        cfg = self.channel_config.get(channel)
        if not cfg or not cfg['enabled']:
            print(f"[BŁĄD] Kanał {channel} nie jest włączony")
            return False
        
        # Przygotuj zdarzenie
        event = XLevent()
        event.tag = XL_TRANSMIT_MSG
        event.chanIndex = cfg['index']
        
        # Ustaw ID
        if extended:
            event.tagData.msg.id = msg_id | XL_CAN_EXT_MSG_ID
        else:
            event.tagData.msg.id = msg_id
        
        # Ustaw dane
        dlc = min(len(data), 8)
        event.tagData.msg.dlc = dlc
        for i, byte in enumerate(data[:8]):
            event.tagData.msg.data[i] = byte
        
        # Wyślij
        msg_count = c_uint(1)
        status = self.dll.xlCanTransmit(
            self.port_handle,
            c_uint64(cfg['mask']),
            byref(msg_count),
            byref(event)
        )
        
        if status != XL_SUCCESS:
            print(f"[BŁĄD TX] status={status}")
            return False
        
        # Log
        hex_data = ' '.join(f'{b:02X}' for b in data[:dlc])
        print(f"[TX CH{channel}] ID=0x{msg_id:03X} DLC={dlc} Data=[{hex_data}]")
        return True
    
    def receive(self, timeout_ms: int = 100) -> Optional[CANMessage]:
        """
        Odbiera wiadomość CAN.
        
        Args:
            timeout_ms: Timeout w milisekundach
        
        Returns:
            CANMessage lub None
        """
        if not self.is_on_bus:
            return None
        
        event = XLevent()
        event_count = c_uint(1)
        
        # Czekaj na zdarzenie
        # Note: xlReceive jest nieblokujące, więc robimy polling
        start = time.time()
        timeout_s = timeout_ms / 1000.0
        
        while time.time() - start < timeout_s:
            status = self.dll.xlReceive(
                self.port_handle,
                byref(event_count),
                byref(event)
            )
            
            if status == XL_SUCCESS and event_count.value > 0:
                if event.tag == XL_RECEIVE_MSG:
                    return self._parse_rx_message(event)
            elif status == XL_ERR_QUEUE_IS_EMPTY:
                time.sleep(0.001)  # Krótka pauza
            else:
                break
        
        return None
    
    def _parse_rx_message(self, event: XLevent) -> CANMessage:
        """Parsuje odebrane zdarzenie na CANMessage."""
        msg_data = event.tagData.msg
        
        # Sprawdź extended ID
        is_ext = (msg_data.id & XL_CAN_EXT_MSG_ID) != 0
        msg_id = msg_data.id & 0x1FFFFFFF
        
        # Pobierz dane
        dlc = msg_data.dlc & 0x0F
        data = bytes(msg_data.data[:dlc])
        
        # Znajdź numer kanału (1-based)
        channel = event.chanIndex + 1
        
        msg = CANMessage(
            id=msg_id,
            data=data,
            dlc=dlc,
            channel=channel,
            timestamp=event.timeStamp / 1e9,
            is_extended=is_ext,
        )
        
        # Log
        hex_data = ' '.join(f'{b:02X}' for b in data)
        print(f"[RX CH{channel}] ID=0x{msg_id:03X} DLC={dlc} Data=[{hex_data}]")
        
        return msg
    
    def receive_all(self, count: int = 100, timeout_ms: int = 1000) -> List[CANMessage]:
        """Odbiera wiele wiadomości."""
        messages = []
        start = time.time()
        
        while len(messages) < count and (time.time() - start) < (timeout_ms / 1000.0):
            msg = self.receive(timeout_ms=10)
            if msg:
                messages.append(msg)
        
        return messages
    
    # ========================================================================
    # ASYNCHRONICZNE ODBIERANIE
    # ========================================================================
    
    def start_receiving(self, callback: Callable[[CANMessage], None]):
        """
        Rozpoczyna asynchroniczne odbieranie.
        
        Args:
            callback: Funkcja wywoływana dla każdej wiadomości
        """
        self._rx_callback = callback
        self._rx_running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()
        print("[OK] Rozpoczęto nasłuchiwanie (async)")
    
    def stop_receiving(self):
        """Zatrzymuje asynchroniczne odbieranie."""
        self._stop_rx_thread()
    
    def _rx_loop(self):
        """Pętla odbierająca wiadomości."""
        event = XLevent()
        event_count = c_uint(1)
        
        while self._rx_running:
            event_count.value = 1
            status = self.dll.xlReceive(
                self.port_handle,
                byref(event_count),
                byref(event)
            )
            
            if status == XL_SUCCESS and event_count.value > 0:
                if event.tag == XL_RECEIVE_MSG:
                    msg = self._parse_rx_message(event)
                    if self._rx_callback:
                        self._rx_callback(msg)
            else:
                time.sleep(0.001)
    
    def _stop_rx_thread(self):
        """Zatrzymuje wątek RX."""
        self._rx_running = False
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)
        self._rx_thread = None
    
    # ========================================================================
    # NARZĘDZIA
    # ========================================================================
    
    def print_status(self):
        """Wyświetla status."""
        print("\n" + "=" * 50)
        print("  STATUS VN1640A")
        print("=" * 50)
        print(f"  Otwarty: {'TAK' if self.is_open else 'NIE'}")
        print(f"  On Bus:  {'TAK' if self.is_on_bus else 'NIE'}")
        print(f"  Handle:  {self.port_handle.value}")
        print("\n  Kanały:")
        
        for ch, cfg in self.channel_config.items():
            status = "WŁĄCZONY" if cfg['enabled'] else "wyłączony"
            baud = cfg['baudrate'] // 1000
            mask = cfg['mask']
            marker = ">>>" if cfg['enabled'] else "   "
            print(f"  {marker} CH{ch}: {status:10} | {baud:4} kbit/s | Mask: 0x{mask:X}")
        
        print("=" * 50)
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, *args):
        self.close()


# ============================================================================
# PRZYKŁADY
# ============================================================================

def example_basic():
    """Podstawowy przykład - kanał 1."""
    print("\n" + "=" * 60)
    print("  PRZYKŁAD: Podstawowa komunikacja")
    print("=" * 60)
    
    vn = VN1640A()
    
    try:
        if not vn.open():
            return
        
        # Włącz tylko kanał 1
        vn.enable_channel(1, CANBaudrate.BAUD_500K)
        
        # Start
        if not vn.start():
            return
        
        vn.print_status()
        
        # Wyślij testową wiadomość
        vn.send(0x123, [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88], channel=1)
        
        # Nasłuchuj
        print("\n[INFO] Nasłuchiwanie przez 3 sekundy...")
        messages = vn.receive_all(count=100, timeout_ms=3000)
        print(f"[INFO] Odebrano {len(messages)} wiadomości")
        
    finally:
        vn.close()


def example_multi_channel():
    """Przykład z wieloma kanałami."""
    print("\n" + "=" * 60)
    print("  PRZYKŁAD: Wiele kanałów")
    print("=" * 60)
    
    vn = VN1640A()
    
    try:
        vn.open()
        
        # Włącz kanały 1 i 2
        vn.enable_channel(1, CANBaudrate.BAUD_500K)
        vn.enable_channel(2, CANBaudrate.BAUD_250K)
        
        vn.start()
        vn.print_status()
        
        # Wyślij na różne kanały
        vn.send(0x100, [0x01], channel=1)
        vn.send(0x200, [0x02], channel=2)
        
        time.sleep(2)
        
    finally:
        vn.close()


def example_switching():
    """Przykład przełączania kanałów."""
    print("\n" + "=" * 60)
    print("  PRZYKŁAD: Przełączanie kanałów")
    print("=" * 60)
    
    vn = VN1640A()
    
    try:
        vn.open()
        
        print("\n--- Faza 1: Kanał 1 ---")
        vn.enable_channel(1)
        print(f"Aktywne: {vn.get_enabled_channels()}")
        
        print("\n--- Faza 2: Dodaj kanał 2 ---")
        vn.enable_channel(2)
        print(f"Aktywne: {vn.get_enabled_channels()}")
        
        print("\n--- Faza 3: Wyłącz kanał 1 ---")
        vn.disable_channel(1)
        print(f"Aktywne: {vn.get_enabled_channels()}")
        
        print("\n--- Faza 4: Wszystkie kanały ---")
        for ch in range(1, 5):
            vn.enable_channel(ch)
        print(f"Aktywne: {vn.get_enabled_channels()}")
        
        vn.print_status()
        
    finally:
        vn.close()


def interactive():
    """Tryb interaktywny."""
    vn = VN1640A()
    
    print("\n" + "=" * 50)
    print("  VN1640A - TRYB INTERAKTYWNY")
    print("=" * 50)
    
    try:
        while True:
            print("\n--- MENU ---")
            print("1. Otwórz sterownik")
            print("2. Włącz kanał")
            print("3. Wyłącz kanał")
            print("4. Start (go on bus)")
            print("5. Stop (go off bus)")
            print("6. Wyślij wiadomość")
            print("7. Odbierz wiadomość")
            print("8. Status")
            print("0. Wyjście")
            
            choice = input("\nWybór: ").strip()
            
            if choice == '1':
                vn.open()
            elif choice == '2':
                ch = int(input("Kanał (1-4): "))
                baud = int(input("Baudrate [500000]: ") or "500000")
                vn.enable_channel(ch, baud)
            elif choice == '3':
                ch = int(input("Kanał (1-4): "))
                vn.disable_channel(ch)
            elif choice == '4':
                vn.start()
            elif choice == '5':
                vn.stop()
            elif choice == '6':
                ch = int(input("Kanał: "))
                msg_id = int(input("ID (hex): "), 16)
                data_str = input("Dane (hex): ")
                data = [int(x, 16) for x in data_str.split()] if data_str else []
                vn.send(msg_id, data, channel=ch)
            elif choice == '7':
                msg = vn.receive(timeout_ms=2000)
                if not msg:
                    print("[INFO] Brak wiadomości")
            elif choice == '8':
                vn.print_status()
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
    print("=" * 60)
    print("  VECTOR VN1640A - INTERFEJS CAN")
    print("=" * 60)
    print("\nTryby:")
    print("  1 - Podstawowy przykład")
    print("  2 - Wiele kanałów")
    print("  3 - Przełączanie kanałów")
    print("  4 - Tryb interaktywny")
    
    try:
        choice = input("\nWybór [3]: ").strip() or "3"
        
        if choice == '1':
            example_basic()
        elif choice == '2':
            example_multi_channel()
        elif choice == '3':
            example_switching()
        elif choice == '4':
            interactive()
            
    except Exception as e:
        print(f"\n[BŁĄD] {e}")
        import traceback
        traceback.print_exc()
