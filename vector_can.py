"""
Interfejs CAN dla Vector VN1640A używając biblioteki python-can
Prostsza i bardziej stabilna wersja

Autor: GitHub Copilot
"""

import can
from can.interfaces.vector import VectorBus
from can.interfaces.vector import xldefine
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass, field
from enum import IntEnum
import time
import threading


# ============================================================================
# KONFIGURACJA
# ============================================================================

class CANBaudrate(IntEnum):
    """Standardowe prędkości CAN."""
    BAUD_1M = 1000000
    BAUD_500K = 500000
    BAUD_250K = 250000
    BAUD_125K = 125000
    BAUD_100K = 100000
    BAUD_50K = 50000
    BAUD_20K = 20000
    BAUD_10K = 10000


@dataclass
class ChannelConfig:
    """Konfiguracja pojedynczego kanału CAN."""
    number: int  # 1-4
    enabled: bool = False
    baudrate: int = CANBaudrate.BAUD_500K
    bus: Optional[can.Bus] = field(default=None, repr=False)
    is_on_bus: bool = False


# ============================================================================
# GŁÓWNA KLASA INTERFEJSU
# ============================================================================

class VectorCAN:
    """
    Prosty interfejs do komunikacji CAN przez Vector VN1640A.
    
    Używa biblioteki python-can dla stabilności.
    Obsługuje 4 kanały z możliwością indywidualnego zarządzania.
    
    Przykład użycia:
        can = VectorCAN()
        can.enable_channel(1)
        can.connect()
        can.send(0x123, [0x11, 0x22, 0x33])
        msg = can.receive()
        can.disconnect()
    """
    
    MAX_CHANNELS = 4
    APP_NAME = "PythonVectorCAN"
    
    def __init__(self, app_name: str = None):
        """
        Inicjalizacja interfejsu.
        
        Args:
            app_name: Nazwa aplikacji widoczna w Vector Hardware Config
        """
        self.app_name = app_name or self.APP_NAME
        
        # Konfiguracja 4 kanałów
        self.channels: Dict[int, ChannelConfig] = {
            i: ChannelConfig(number=i) for i in range(1, self.MAX_CHANNELS + 1)
        }
        
        # Callback dla odebranych wiadomości
        self._rx_callback: Optional[Callable] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._rx_running = False
        
    # ========================================================================
    # ZARZĄDZANIE KANAŁAMI
    # ========================================================================
    
    def enable_channel(self, channel: int, baudrate: int = CANBaudrate.BAUD_500K) -> bool:
        """
        Włącza kanał CAN.
        
        Args:
            channel: Numer kanału (1-4)
            baudrate: Prędkość transmisji (domyślnie 500 kbit/s)
        """
        if channel < 1 or channel > self.MAX_CHANNELS:
            print(f"[BŁĄD] Nieprawidłowy kanał: {channel}. Użyj 1-{self.MAX_CHANNELS}")
            return False
        
        self.channels[channel].enabled = True
        self.channels[channel].baudrate = baudrate
        
        print(f"[OK] Kanał {channel} włączony ({baudrate // 1000} kbit/s)")
        return True
    
    def disable_channel(self, channel: int) -> bool:
        """Wyłącza kanał CAN."""
        if channel < 1 or channel > self.MAX_CHANNELS:
            return False
        
        # Najpierw rozłącz jeśli aktywny
        if self.channels[channel].bus:
            self.disconnect_channel(channel)
        
        self.channels[channel].enabled = False
        print(f"[OK] Kanał {channel} wyłączony")
        return True
    
    def set_baudrate(self, channel: int, baudrate: int) -> bool:
        """Ustawia prędkość transmisji dla kanału."""
        if channel < 1 or channel > self.MAX_CHANNELS:
            return False
        
        self.channels[channel].baudrate = baudrate
        print(f"[OK] Kanał {channel}: {baudrate // 1000} kbit/s")
        return True
    
    def get_enabled_channels(self) -> List[int]:
        """Zwraca listę włączonych kanałów."""
        return [ch for ch, cfg in self.channels.items() if cfg.enabled]
    
    # ========================================================================
    # POŁĄCZENIE
    # ========================================================================
    
    def connect(self) -> bool:
        """
        Łączy wszystkie włączone kanały z magistralą CAN.
        """
        enabled = self.get_enabled_channels()
        if not enabled:
            print("[BŁĄD] Brak włączonych kanałów! Użyj enable_channel()")
            return False
        
        print(f"\n[INFO] Łączenie kanałów: {enabled}")
        
        success = True
        for ch_num in enabled:
            if not self.connect_channel(ch_num):
                success = False
        
        return success
    
    def connect_channel(self, channel: int) -> bool:
        """
        Łączy pojedynczy kanał z magistralą.
        
        Args:
            channel: Numer kanału (1-4)
        """
        cfg = self.channels.get(channel)
        if not cfg or not cfg.enabled:
            print(f"[BŁĄD] Kanał {channel} nie jest włączony")
            return False
        
        if cfg.bus:
            print(f"[INFO] Kanał {channel} już połączony")
            return True
        
        try:
            # Vector używa indeksowania od 0
            vector_channel = channel - 1
            
            # Użyj bezpośredniego dostępu do kanału sprzętowego
            # bez wymagania konfiguracji aplikacji w Vector Hardware Config
            bus = can.Bus(
                interface='vector',
                channel=vector_channel,
                bitrate=cfg.baudrate,
                app_name=self.app_name,
                # Automatycznie znajdź i użyj dostępny kanał
                serial=None,  # Użyj dowolnego dostępnego urządzenia
            )
            
            cfg.bus = bus
            cfg.is_on_bus = True
            
            print(f"[OK] Kanał {channel} połączony (Vector CH{vector_channel})")
            return True
            
        except can.CanError as e:
            error_msg = str(e)
            if "not assigned" in error_msg:
                print(f"[INFO] Kanał {channel}: Próba połączenia bez konfiguracji aplikacji...")
                return self._connect_channel_direct(channel)
            print(f"[BŁĄD] Kanał {channel}: {e}")
            return False
        except Exception as e:
            print(f"[BŁĄD] Kanał {channel}: {e}")
            return False
    
    def _connect_channel_direct(self, channel: int) -> bool:
        """
        Bezpośrednie połączenie z kanałem bez konfiguracji aplikacji.
        Używa xlOpenPort z bezpośrednią maską kanału.
        """
        cfg = self.channels.get(channel)
        vector_channel = channel - 1
        
        try:
            # Spróbuj z fd=False i bez app_name
            bus = can.Bus(
                interface='vector',
                channel=vector_channel,
                bitrate=cfg.baudrate,
                fd=False,
                # Puste app_name wymusza użycie domyślnej konfiguracji
                app_name="",
            )
            
            cfg.bus = bus
            cfg.is_on_bus = True
            print(f"[OK] Kanał {channel} połączony bezpośrednio")
            return True
            
        except Exception as e:
            print(f"[BŁĄD] Kanał {channel} (bezpośredni): {e}")
            print(f"       Skonfiguruj aplikację '{self.app_name}' w Vector Hardware Config")
            print(f"       lub zamknij CANoe jeśli jest uruchomione")
            return False
    
    def disconnect(self):
        """Rozłącza wszystkie kanały."""
        self._stop_rx_thread()
        
        for ch_num in range(1, self.MAX_CHANNELS + 1):
            self.disconnect_channel(ch_num)
        
        print("[OK] Wszystkie kanały rozłączone")
    
    def disconnect_channel(self, channel: int):
        """Rozłącza pojedynczy kanał."""
        cfg = self.channels.get(channel)
        if cfg and cfg.bus:
            try:
                cfg.bus.shutdown()
            except:
                pass
            cfg.bus = None
            cfg.is_on_bus = False
            print(f"[OK] Kanał {channel} rozłączony")
    
    # ========================================================================
    # WYSYŁANIE I ODBIERANIE
    # ========================================================================
    
    def send(self, msg_id: int, data: list, channel: int = 1, 
             extended: bool = False) -> bool:
        """
        Wysyła wiadomość CAN.
        
        Args:
            msg_id: ID wiadomości (11-bit lub 29-bit)
            data: Lista bajtów danych (max 8)
            channel: Numer kanału (1-4)
            extended: True dla extended ID (29-bit)
        
        Returns:
            True jeśli wysłano pomyślnie
        
        Example:
            can.send(0x123, [0x11, 0x22, 0x33])
        """
        cfg = self.channels.get(channel)
        if not cfg or not cfg.bus:
            print(f"[BŁĄD] Kanał {channel} nie jest połączony")
            return False
        
        try:
            msg = can.Message(
                arbitration_id=msg_id,
                data=bytes(data),
                is_extended_id=extended,
            )
            
            cfg.bus.send(msg)
            
            hex_data = ' '.join(f'{b:02X}' for b in data)
            print(f"[TX CH{channel}] ID=0x{msg_id:03X} Data=[{hex_data}]")
            return True
            
        except can.CanError as e:
            print(f"[BŁĄD TX] {e}")
            return False
    
    def receive(self, channel: int = 1, timeout: float = 1.0) -> Optional[can.Message]:
        """
        Odbiera wiadomość CAN.
        
        Args:
            channel: Numer kanału (1-4)
            timeout: Timeout w sekundach
        
        Returns:
            can.Message lub None
        """
        cfg = self.channels.get(channel)
        if not cfg or not cfg.bus:
            return None
        
        try:
            msg = cfg.bus.recv(timeout=timeout)
            
            if msg:
                hex_data = ' '.join(f'{b:02X}' for b in msg.data)
                print(f"[RX CH{channel}] ID=0x{msg.arbitration_id:03X} "
                      f"DLC={msg.dlc} Data=[{hex_data}]")
            
            return msg
            
        except can.CanError:
            return None
    
    def receive_all(self, timeout: float = 1.0) -> List[can.Message]:
        """
        Odbiera wiadomości ze wszystkich połączonych kanałów.
        
        Args:
            timeout: Timeout w sekundach
        """
        messages = []
        
        for ch_num, cfg in self.channels.items():
            if cfg.bus:
                msg = self.receive(channel=ch_num, timeout=timeout / self.MAX_CHANNELS)
                if msg:
                    messages.append(msg)
        
        return messages
    
    # ========================================================================
    # ASYNCHRONICZNE ODBIERANIE
    # ========================================================================
    
    def start_receiving(self, callback: Callable[[can.Message, int], None]):
        """
        Rozpoczyna asynchroniczne odbieranie wiadomości.
        
        Args:
            callback: Funkcja wywoływana dla każdej wiadomości
                     callback(message, channel_number)
        """
        self._rx_callback = callback
        self._rx_running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()
        print("[OK] Rozpoczęto nasłuchiwanie")
    
    def stop_receiving(self):
        """Zatrzymuje asynchroniczne odbieranie."""
        self._stop_rx_thread()
        print("[OK] Zatrzymano nasłuchiwanie")
    
    def _rx_loop(self):
        """Wątek odbierający wiadomości."""
        while self._rx_running:
            for ch_num, cfg in self.channels.items():
                if cfg.bus and self._rx_running:
                    try:
                        msg = cfg.bus.recv(timeout=0.01)
                        if msg and self._rx_callback:
                            self._rx_callback(msg, ch_num)
                    except:
                        pass
    
    def _stop_rx_thread(self):
        """Zatrzymuje wątek odbierający."""
        self._rx_running = False
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)
        self._rx_thread = None
    
    # ========================================================================
    # NARZĘDZIA
    # ========================================================================
    
    def print_status(self):
        """Wyświetla status wszystkich kanałów."""
        print("\n" + "=" * 50)
        print("  STATUS KANAŁÓW VN1640A")
        print("=" * 50)
        
        for ch_num, cfg in self.channels.items():
            status_enabled = "WŁĄCZONY" if cfg.enabled else "wyłączony"
            status_bus = "ON BUS" if cfg.is_on_bus else "OFF BUS"
            baud = cfg.baudrate // 1000
            
            marker = ">>>" if cfg.is_on_bus else "   "
            print(f"{marker} CH{ch_num}: {status_enabled:10} | {baud:4} kbit/s | {status_bus}")
        
        print("=" * 50 + "\n")
    
    @staticmethod
    def list_available_channels():
        """
        Wyświetla dostępne kanały Vector.
        """
        print("\n[INFO] Skanowanie urządzeń Vector...")
        
        try:
            from can.interfaces.vector import VectorBus
            configs = VectorBus.get_application_config(app_name="", app_channel=0)
            
            print("\nDostępne kanały Vector:")
            for i, (hw_type, hw_index, hw_channel) in enumerate(configs):
                print(f"  [{i}] hwType={hw_type}, hwIndex={hw_index}, hwChannel={hw_channel}")
                
        except Exception as e:
            print(f"[INFO] Użyj Vector Hardware Config do sprawdzenia konfiguracji")
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False


# ============================================================================
# PRZYKŁADY UŻYCIA
# ============================================================================

def example_basic():
    """
    Podstawowy przykład - jeden kanał.
    """
    print("\n" + "=" * 60)
    print("  PRZYKŁAD: Podstawowa komunikacja CAN")
    print("=" * 60)
    
    can_if = VectorCAN()
    
    try:
        # Włącz kanał 1 z prędkością 500 kbit/s
        can_if.enable_channel(1, CANBaudrate.BAUD_500K)
        
        # Połącz
        if not can_if.connect():
            print("[BŁĄD] Nie można połączyć")
            return
        
        can_if.print_status()
        
        # Wyślij testową wiadomość
        can_if.send(0x123, [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88])
        
        # Nasłuchuj przez 3 sekundy
        print("\n[INFO] Nasłuchiwanie przez 3 sekundy...")
        start = time.time()
        count = 0
        
        while time.time() - start < 3.0:
            msg = can_if.receive(channel=1, timeout=0.1)
            if msg:
                count += 1
        
        print(f"\n[INFO] Odebrano {count} wiadomości")
        
    finally:
        can_if.disconnect()


def example_multi_channel():
    """
    Przykład z wieloma kanałami.
    """
    print("\n" + "=" * 60)
    print("  PRZYKŁAD: Komunikacja wielokanałowa")
    print("=" * 60)
    
    can_if = VectorCAN()
    
    try:
        # Włącz kanały 1 i 2
        can_if.enable_channel(1, CANBaudrate.BAUD_500K)
        can_if.enable_channel(2, CANBaudrate.BAUD_500K)
        
        # Kanały 3 i 4 wyłączone
        # can_if.enable_channel(3)
        # can_if.enable_channel(4)
        
        can_if.connect()
        can_if.print_status()
        
        # Wyślij na różne kanały
        can_if.send(0x100, [0x01, 0x02, 0x03], channel=1)
        can_if.send(0x200, [0x0A, 0x0B, 0x0C], channel=2)
        
        time.sleep(1)
        
    finally:
        can_if.disconnect()


def example_async_receive():
    """
    Przykład asynchronicznego odbierania.
    """
    print("\n" + "=" * 60)
    print("  PRZYKŁAD: Asynchroniczne odbieranie")
    print("=" * 60)
    
    received_count = [0]  # Lista bo modyfikujemy w callback
    
    def on_message(msg: can.Message, channel: int):
        """Callback wywoływany dla każdej wiadomości."""
        hex_data = ' '.join(f'{b:02X}' for b in msg.data)
        print(f"[ASYNC RX CH{channel}] ID=0x{msg.arbitration_id:03X} Data=[{hex_data}]")
        received_count[0] += 1
    
    can_if = VectorCAN()
    
    try:
        can_if.enable_channel(1)
        can_if.connect()
        
        # Rozpocznij asynchroniczne odbieranie
        can_if.start_receiving(on_message)
        
        print("[INFO] Nasłuchiwanie przez 5 sekund...")
        print("       Wyślij wiadomości CAN na kanał 1")
        
        # Główny wątek może robić inne rzeczy
        for i in range(5):
            time.sleep(1)
            print(f"       ... {5-i} sekund pozostało")
        
        can_if.stop_receiving()
        print(f"\n[INFO] Odebrano {received_count[0]} wiadomości")
        
    finally:
        can_if.disconnect()


def example_channel_switching():
    """
    Przykład dynamicznego przełączania kanałów.
    """
    print("\n" + "=" * 60)
    print("  PRZYKŁAD: Przełączanie kanałów")
    print("=" * 60)
    
    can_if = VectorCAN()
    
    try:
        # Faza 1: Tylko kanał 1
        print("\n--- Faza 1: Kanał 1 ---")
        can_if.enable_channel(1)
        can_if.connect_channel(1)
        can_if.print_status()
        
        can_if.send(0x111, [0x01], channel=1)
        time.sleep(0.5)
        
        # Faza 2: Dodaj kanał 2 (kanał 1 nadal aktywny)
        print("\n--- Faza 2: Dodaj kanał 2 ---")
        can_if.enable_channel(2)
        can_if.connect_channel(2)
        can_if.print_status()
        
        can_if.send(0x222, [0x02], channel=2)
        time.sleep(0.5)
        
        # Faza 3: Wyłącz kanał 1, zostaw kanał 2
        print("\n--- Faza 3: Wyłącz kanał 1 ---")
        can_if.disable_channel(1)
        can_if.print_status()
        
        can_if.send(0x333, [0x03], channel=2)
        
    finally:
        can_if.disconnect()


# ============================================================================
# INTERAKTYWNE MENU
# ============================================================================

def interactive_menu():
    """Interaktywne menu do testowania."""
    can_if = VectorCAN()
    
    print("\n" + "=" * 50)
    print("  VECTOR VN1640A - INTERAKTYWNY TEST")
    print("=" * 50)
    
    try:
        while True:
            print("\n--- MENU ---")
            print("1. Włącz kanał")
            print("2. Wyłącz kanał")
            print("3. Połącz")
            print("4. Rozłącz")
            print("5. Wyślij wiadomość")
            print("6. Odbierz wiadomość")
            print("7. Status")
            print("8. Szybki start (CH1, 500k)")
            print("0. Wyjście")
            
            choice = input("\nWybór: ").strip()
            
            if choice == '1':
                ch = int(input("Kanał (1-4): "))
                baud = int(input("Baudrate [500000]: ") or "500000")
                can_if.enable_channel(ch, baud)
                
            elif choice == '2':
                ch = int(input("Kanał (1-4): "))
                can_if.disable_channel(ch)
                
            elif choice == '3':
                can_if.connect()
                
            elif choice == '4':
                can_if.disconnect()
                
            elif choice == '5':
                ch = int(input("Kanał (1-4): "))
                msg_id = int(input("ID (hex): "), 16)
                data_str = input("Dane (hex, np. 11 22 33): ")
                data = [int(x, 16) for x in data_str.split()]
                can_if.send(msg_id, data, channel=ch)
                
            elif choice == '6':
                ch = int(input("Kanał (1-4): "))
                msg = can_if.receive(channel=ch, timeout=2.0)
                if not msg:
                    print("[INFO] Brak wiadomości")
                    
            elif choice == '7':
                can_if.print_status()
                
            elif choice == '8':
                can_if.enable_channel(1, CANBaudrate.BAUD_500K)
                can_if.connect()
                can_if.print_status()
                
            elif choice == '0':
                break
                
    except KeyboardInterrupt:
        print("\n[INFO] Przerwano")
    finally:
        can_if.disconnect()


# ============================================================================
# GŁÓWNA FUNKCJA
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  VECTOR VN1640A - PYTHON CAN INTERFACE")
    print("  Używa biblioteki python-can")
    print("=" * 60)
    
    print("\nDostępne tryby:")
    print("  1 - Podstawowy przykład")
    print("  2 - Wielokanałowy przykład")
    print("  3 - Asynchroniczne odbieranie")
    print("  4 - Przełączanie kanałów")
    print("  5 - Interaktywne menu")
    
    choice = input("\nWybierz tryb [1]: ").strip() or "1"
    
    try:
        if choice == '1':
            example_basic()
        elif choice == '2':
            example_multi_channel()
        elif choice == '3':
            example_async_receive()
        elif choice == '4':
            example_channel_switching()
        elif choice == '5':
            interactive_menu()
        else:
            print("[BŁĄD] Nieprawidłowy wybór")
            
    except Exception as e:
        print(f"\n[BŁĄD] {e}")
        print("\nMożliwe przyczyny:")
        print("  1. Urządzenie VN1640A nie jest podłączone")
        print("  2. Inny program używa urządzenia (np. CANoe)")
        print("  3. Sterowniki Vector nie są zainstalowane")
        print("  4. Brak licencji Vector")
