"""
Interaktywny menedżer kanałów CAN dla VN1640A
Prosty interfejs do włączania/wyłączania kanałów i testowania komunikacji
"""

from vector_can_interface import VectorCANInterface, CANMessage, CANBaudrate
import time


class CANChannelManager:
    """
    Prosty menedżer kanałów CAN z interaktywnym menu.
    """
    
    def __init__(self):
        self.can = VectorCANInterface()
        self.is_initialized = False
    
    def initialize(self) -> bool:
        """Inicjalizuje interfejs Vector."""
        print("\n[INIT] Inicjalizacja interfejsu Vector...")
        
        if self.can.open_driver():
            self.is_initialized = True
            return True
        return False
    
    def show_menu(self):
        """Wyświetla menu główne."""
        print("\n" + "=" * 50)
        print("  MENEDŻER KANAŁÓW VN1640A")
        print("=" * 50)
        print("  1. Włącz/wyłącz kanał")
        print("  2. Ustaw baudrate kanału")
        print("  3. Pokaż status kanałów")
        print("  4. Połącz (Go On Bus)")
        print("  5. Rozłącz (Go Off Bus)")
        print("  6. Wyślij testową wiadomość")
        print("  7. Nasłuchuj wiadomości")
        print("  8. Szybka konfiguracja (tylko CH1)")
        print("  9. Szybka konfiguracja (CH1 + CH2)")
        print("  0. Wyjście")
        print("-" * 50)
    
    def toggle_channel(self):
        """Włącza lub wyłącza kanał."""
        print("\nWybierz kanał (1-4): ", end="")
        try:
            ch = int(input())
            if ch < 1 or ch > 4:
                print("[BŁĄD] Nieprawidłowy kanał")
                return
            
            current = self.can.channel_enabled[ch - 1]
            new_state = not current
            self.can.enable_channel(ch, new_state)
            
        except ValueError:
            print("[BŁĄD] Wprowadź liczbę 1-4")
    
    def set_baudrate(self):
        """Ustawia baudrate dla kanału."""
        print("\nDostępne prędkości:")
        print("  1. 1000 kbit/s")
        print("  2. 500 kbit/s")
        print("  3. 250 kbit/s")
        print("  4. 125 kbit/s")
        print("  5. 100 kbit/s")
        
        print("\nWybierz kanał (1-4): ", end="")
        try:
            ch = int(input())
            print("Wybierz prędkość (1-5): ", end="")
            speed = int(input())
            
            baudrates = {
                1: CANBaudrate.BAUD_1M,
                2: CANBaudrate.BAUD_500K,
                3: CANBaudrate.BAUD_250K,
                4: CANBaudrate.BAUD_125K,
                5: CANBaudrate.BAUD_100K,
            }
            
            if speed in baudrates:
                self.can.set_channel_baudrate(ch, baudrates[speed])
            else:
                print("[BŁĄD] Nieprawidłowy wybór")
                
        except ValueError:
            print("[BŁĄD] Wprowadź prawidłowe liczby")
    
    def show_status(self):
        """Pokazuje status wszystkich kanałów."""
        self.can.print_status()
    
    def go_on_bus(self):
        """Łączy się z magistralą CAN."""
        enabled = self.can.get_enabled_channels()
        if not enabled:
            print("[BŁĄD] Najpierw włącz przynajmniej jeden kanał!")
            return
        
        print(f"\n[INFO] Łączenie kanałów: {enabled}")
        
        if self.can.port_handle.value == 0:
            self.can.open_port("PythonCANManager")
            self.can.set_baudrate()
        
        self.can.go_on_bus()
    
    def go_off_bus(self):
        """Rozłącza się z magistrali CAN."""
        self.can.go_off_bus()
    
    def send_test_message(self):
        """Wysyła testową wiadomość."""
        if not self.can.is_on_bus:
            print("[BŁĄD] Najpierw połącz się (opcja 4)")
            return
        
        enabled = self.can.get_enabled_channels()
        print(f"\nDostępne kanały: {enabled}")
        print("Wybierz kanał: ", end="")
        
        try:
            ch = int(input())
            print("Podaj ID wiadomości (hex, np. 123): ", end="")
            msg_id = int(input(), 16)
            print("Podaj dane (hex, np. 11 22 33): ", end="")
            data_str = input()
            data_bytes = bytes([int(x, 16) for x in data_str.split()])
            
            msg = CANMessage(id=msg_id, data=data_bytes)
            self.can.send_message(msg, channel=ch)
            
        except (ValueError, IndexError) as e:
            print(f"[BŁĄD] Nieprawidłowe dane: {e}")
    
    def listen_messages(self):
        """Nasłuchuje wiadomości CAN."""
        if not self.can.is_on_bus:
            print("[BŁĄD] Najpierw połącz się (opcja 4)")
            return
        
        print("\nNasłuchiwanie (Ctrl+C aby przerwać)...")
        print("-" * 50)
        
        try:
            while True:
                msg = self.can.receive_message(timeout_ms=100)
                if msg:
                    pass  # receive_message już drukuje
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\n[INFO] Przerwano nasłuchiwanie")
    
    def quick_setup_ch1(self):
        """Szybka konfiguracja - tylko kanał 1."""
        # Wyłącz wszystkie
        for i in range(1, 5):
            self.can.enable_channel(i, False)
        
        # Włącz tylko CH1
        self.can.enable_channel(1, True)
        self.can.set_channel_baudrate(1, CANBaudrate.BAUD_500K)
        
        self.go_on_bus()
    
    def quick_setup_ch1_ch2(self):
        """Szybka konfiguracja - kanały 1 i 2."""
        # Wyłącz wszystkie
        for i in range(1, 5):
            self.can.enable_channel(i, False)
        
        # Włącz CH1 i CH2
        self.can.enable_channel(1, True)
        self.can.enable_channel(2, True)
        self.can.set_channel_baudrate(1, CANBaudrate.BAUD_500K)
        self.can.set_channel_baudrate(2, CANBaudrate.BAUD_500K)
        
        self.go_on_bus()
    
    def run(self):
        """Główna pętla programu."""
        if not self.initialize():
            print("[BŁĄD] Nie można zainicjalizować interfejsu")
            return
        
        try:
            while True:
                self.show_menu()
                print("Wybór: ", end="")
                
                try:
                    choice = input().strip()
                    
                    if choice == '1':
                        self.toggle_channel()
                    elif choice == '2':
                        self.set_baudrate()
                    elif choice == '3':
                        self.show_status()
                    elif choice == '4':
                        self.go_on_bus()
                    elif choice == '5':
                        self.go_off_bus()
                    elif choice == '6':
                        self.send_test_message()
                    elif choice == '7':
                        self.listen_messages()
                    elif choice == '8':
                        self.quick_setup_ch1()
                    elif choice == '9':
                        self.quick_setup_ch1_ch2()
                    elif choice == '0':
                        print("\n[INFO] Do widzenia!")
                        break
                    else:
                        print("[BŁĄD] Nieprawidłowy wybór")
                        
                except EOFError:
                    break
                    
        finally:
            self.can.close()


# ============================================================================
# PRZYKŁADY UŻYCIA PROGRAMISTYCZNEGO
# ============================================================================

def example_simple_usage():
    """
    Przykład prostego użycia - preferowany sposób dla Twojego przypadku
    (głównie kanał 1).
    """
    # Utwórz interfejs
    can = VectorCANInterface()
    
    try:
        # Szybka konfiguracja - kanał 1, 500 kbit/s
        can.quick_setup(channels=[1], baudrate=CANBaudrate.BAUD_500K)
        
        # Wyślij wiadomość
        msg = CANMessage(id=0x123, data=bytes([0x01, 0x02, 0x03, 0x04]))
        can.send_message(msg, channel=1)
        
        # Odbierz wiadomości
        received = can.receive_messages(count=10, timeout_ms=1000)
        for rx_msg in received:
            print(f"Odebrano: {rx_msg}")
            
    finally:
        can.close()


def example_switch_channels():
    """
    Przykład przełączania między kanałami w runtime.
    """
    can = VectorCANInterface()
    
    try:
        can.open_driver()
        
        # Faza 1: Pracuj na kanale 1
        print("\n=== FAZA 1: Kanał 1 ===")
        can.enable_channel(1, True)
        can.open_port()
        can.set_baudrate()
        can.go_on_bus()
        
        # ... praca z kanałem 1 ...
        time.sleep(1)
        
        # Przełącz na kanał 2
        print("\n=== FAZA 2: Przełączanie na Kanał 2 ===")
        can.go_off_bus()
        can.enable_channel(1, False)
        can.enable_channel(2, True)
        # Uwaga: może być konieczne ponowne otwarcie portu
        
    finally:
        can.close()


# ============================================================================
# GŁÓWNA FUNKCJA
# ============================================================================

if __name__ == "__main__":
    manager = CANChannelManager()
    manager.run()
