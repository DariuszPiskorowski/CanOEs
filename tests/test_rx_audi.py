"""Test odbierania CAN FD z modułu Audi - kanał 1"""
import time
from vn1640a_can import VN1640A

print("="*60)
print("Odbieranie CAN FD z modułu Audi - kanał 1")
print("="*60)

vn = VN1640A()

if not vn.open():
    print("Błąd otwarcia")
    exit(1)

if not vn.start_fd(channel=1):
    print("Błąd startu FD")
    vn.close()
    exit(1)

print("\nCzekam na wiadomości z modułu Audi...")
print("(Ctrl+C aby przerwać)\n")

try:
    count = 0
    while True:
        msg = vn.receive(timeout_ms=100)
        if msg:
            count += 1
            print(f"[{count}] {msg}")
except KeyboardInterrupt:
    print(f"\n\nPrzerwano. Odebrano {count} wiadomości.")

vn.close()
