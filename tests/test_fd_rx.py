"""Test odbierania CAN FD - dwa kanały VN1640A"""
import time
import threading
from vn1640a_can import VN1640A

def receiver_thread(vn_rx):
    """Wątek odbierający."""
    print("[RX] Czekam na wiadomości CAN FD...")
    for _ in range(10):  # czekaj max 10 sekund
        msg = vn_rx.receive(timeout_ms=1000)
        if msg:
            print(f"[RX] ODEBRANO: {msg}")
            return True
    print("[RX] Timeout - brak wiadomości")
    return False

# Kanał 1 = nadajnik
# Kanał 2 = odbiornik
# (połącz je fizycznie kablem lub na tym samym busie)

print("="*60)
print("Test CAN FD: Kanał 1 (TX) -> Kanał 2 (RX)")
print("UWAGA: Połącz kanały 1 i 2 kablem lub na tym samym busie!")
print("="*60)

# Utwórz dwa interfejsy
vn_tx = VN1640A()
vn_rx = VN1640A()

# Otwórz sterownik
if not vn_tx.open():
    print("Błąd otwarcia TX")
    exit(1)

if not vn_rx.open():
    print("Błąd otwarcia RX")
    vn_tx.close()
    exit(1)

# Uruchom kanały w trybie FD
print("\nUruchamiam kanał 1 (TX)...")
if not vn_tx.start_fd(channel=1):
    print("Błąd startu TX")
    vn_tx.close()
    vn_rx.close()
    exit(1)

print("\nUruchamiam kanał 2 (RX)...")
if not vn_rx.start_fd(channel=2):
    print("Błąd startu RX")
    vn_tx.close()
    vn_rx.close()
    exit(1)

# Uruchom wątek odbierający
rx_thread = threading.Thread(target=receiver_thread, args=(vn_rx,))
rx_thread.start()

# Poczekaj chwilę
time.sleep(0.5)

# Wyślij wiadomość CAN FD
print("\n[TX] Wysyłam CAN FD: ID=0x123, 12 bajtów, BRS=True")
result = vn_tx.send_fd(0x123, [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA, 0xBB, 0xCC], brs=True)
print(f"[TX] Wynik wysłania: {result}")

# Czekaj na wątek RX
rx_thread.join(timeout=5)

# Zamknij
print("\nZamykam...")
vn_tx.close()
vn_rx.close()

print("\nGotowe!")
