import time
from typing import Callable, Optional

from vector_can_interface import VectorCANInterface, CANMessage, CANBaudrate


class CANChannelManager:
    """Prosty menedżer kanałów CAN z interaktywnym menu."""

    def __init__(
        self,
        can_interface: Optional[VectorCANInterface] = None,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
        sleep_func: Callable[[float], None] = time.sleep,
    ):
        self.can = can_interface or VectorCANInterface()
        self.is_initialized = False
        self.input = input_func
        self.output = output_func
        self.sleep = sleep_func

    def initialize(self) -> bool:
        """Inicjalizuje interfejs Vector."""
        self.output("\n[INIT] Inicjalizacja interfejsu Vector...")

        if self.can.open_driver():
            self.is_initialized = True
            return True
        return False

    def show_menu(self):
        """Wyświetla menu główne."""
        self.output("\n" + "=" * 50)
        self.output("  MENEDŻER KANAŁÓW VN1640A")
        self.output("=" * 50)
        self.output("  1. Włącz/wyłącz kanał")
        self.output("  2. Ustaw baudrate kanału")
        self.output("  3. Pokaż status kanałów")
        self.output("  4. Połącz (Go On Bus)")
        self.output("  5. Rozłącz (Go Off Bus)")
        self.output("  6. Wyślij testową wiadomość")
        self.output("  7. Nasłuchuj wiadomości")
        self.output("  8. Szybka konfiguracja (tylko CH1)")
        self.output("  9. Szybka konfiguracja (CH1 + CH2)")
        self.output("  0. Wyjście")
        self.output("-" * 50)

    def toggle_channel(self):
        """Włącza lub wyłącza kanał."""
        self.output("\nWybierz kanał (1-4): ", end="")
        try:
            ch = int(self.input("") or 0)
            if ch < 1 or ch > 4:
                self.output("[BŁĄD] Nieprawidłowy kanał")
                return

            current = self.can.channel_enabled[ch - 1]
            new_state = not current
            self.can.enable_channel(ch, new_state)

        except ValueError:
            self.output("[BŁĄD] Wprowadź liczbę 1-4")

    def set_baudrate(self):
        """Ustawia baudrate dla kanału."""
        self.output("\nDostępne prędkości:")
        self.output("  1. 1000 kbit/s")
        self.output("  2. 500 kbit/s")
        self.output("  3. 250 kbit/s")
        self.output("  4. 125 kbit/s")
        self.output("  5. 100 kbit/s")

        self.output("\nWybierz kanał (1-4): ", end="")
        try:
            ch = int(self.input("") or 0)
            self.output("Wybierz prędkość (1-5): ", end="")
            speed = int(self.input("") or 0)

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
                self.output("[BŁĄD] Nieprawidłowy wybór")

        except ValueError:
            self.output("[BŁĄD] Wprowadź prawidłowe liczby")

    def show_status(self):
        """Pokazuje status wszystkich kanałów."""
        self.can.print_status()

    def go_on_bus(self):
        """Łączy się z magistralą CAN."""
        enabled = self.can.get_enabled_channels()
        if not enabled:
            self.output("[BŁĄD] Najpierw włącz przynajmniej jeden kanał!")
            return

        self.output(f"\n[INFO] Łączenie kanałów: {enabled}")

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
            self.output("[BŁĄD] Najpierw połącz się (opcja 4)")
            return

        enabled = self.can.get_enabled_channels()
        self.output(f"\nDostępne kanały: {enabled}")
        self.output("Wybierz kanał: ", end="")

        try:
            ch = int(self.input("") or 0)
            self.output("Podaj ID wiadomości (hex, np. 123): ", end="")
            msg_id = int(self.input("") or "0", 16)
            self.output("Podaj dane (hex, np. 11 22 33): ", end="")
            data_str = self.input("") or ""
            data_bytes = bytes([int(x, 16) for x in data_str.split()])

            msg = CANMessage(id=msg_id, data=data_bytes)
            self.can.send_message(msg, channel=ch)

        except (ValueError, IndexError) as e:
            self.output(f"[BŁĄD] Nieprawidłowe dane: {e}")

    def listen_messages(
        self,
        max_messages: Optional[int] = None,
        message_handler: Optional[Callable[[CANMessage], None]] = None,
        stop_condition: Optional[Callable[[], bool]] = None,
    ):
        """Nasłuchuje wiadomości CAN."""
        if not self.can.is_on_bus:
            self.output("[BŁĄD] Najpierw połącz się (opcja 4)")
            return

        self.output("\nNasłuchiwanie (Ctrl+C aby przerwać)...")
        self.output("-" * 50)

        handled = 0
        handler = message_handler or (lambda m: None)
        try:
            while True:
                if stop_condition and stop_condition():
                    break
                msg = self.can.receive_message(timeout_ms=100)
                if msg:
                    handler(msg)
                    handled += 1
                    if max_messages and handled >= max_messages:
                        break
                self.sleep(0.01)
        except KeyboardInterrupt:
            self.output("\n[INFO] Przerwano nasłuchiwanie")

    def quick_setup_ch1(self):
        """Szybka konfiguracja - tylko kanał 1."""
        for i in range(1, 5):
            self.can.enable_channel(i, False)

        self.can.enable_channel(1, True)
        self.can.set_channel_baudrate(1, CANBaudrate.BAUD_500K)

        self.go_on_bus()

    def quick_setup_ch1_ch2(self):
        """Szybka konfiguracja - kanały 1 i 2."""
        for i in range(1, 5):
            self.can.enable_channel(i, False)

        self.can.enable_channel(1, True)
        self.can.enable_channel(2, True)
        self.can.set_channel_baudrate(1, CANBaudrate.BAUD_500K)
        self.can.set_channel_baudrate(2, CANBaudrate.BAUD_500K)

        self.go_on_bus()

    def run(self):
        """Główna pętla programu."""
        if not self.initialize():
            self.output("[BŁĄD] Nie można zainicjalizować interfejsu")
            return

        try:
            while True:
                self.show_menu()
                self.output("Wybór: ", end="")

                try:
                    choice = (self.input("") or "").strip()

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
                        self.output("\n[INFO] Do widzenia!")
                        break
                    else:
                        self.output("[BŁĄD] Nieprawidłowy wybór")

                except ValueError:
                    self.output("[BŁĄD] Nieprawidłowe dane")

        except KeyboardInterrupt:
            self.output("\n[INFO] Zamykanie programu...")

        finally:
            self.can.close()
