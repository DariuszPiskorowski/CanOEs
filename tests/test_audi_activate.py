"""Test aktywacji modułu Audi i odbierania odpowiedzi CAN FD"""
import time
from vn1640a_can import VN1640A

print("="*60)
print("Aktywacja modułu Audi + odbieranie CAN FD")
print("="*60)

vn = VN1640A()

if not vn.open():
    print("Błąd otwarcia")
    exit(1)

if not vn.start_fd(channel=1):
    print("Błąd startu FD")
    vn.close()
    exit(1)

print("\n--- Wysyłam wiadomości aktywacyjne ---\n")

# Typowe ID diagnostyczne dla Audi/VW:
# 0x7DF - broadcast diagnostyczny (wszystkie moduły)
# 0x700-0x7FF - indywidualne adresy modułów

# TesterPresent (UDS 0x3E 0x00) - utrzymuje sesję diagnostyczną
# Format: [długość, SID, sub-function]
tester_present = [0x02, 0x3E, 0x00]  # TesterPresent, no response expected

# DiagnosticSessionControl (UDS 0x10) - wejście w sesję diagnostyczną
# 0x01 = default session, 0x03 = extended session
diag_session = [0x02, 0x10, 0x01]  # Default session

# Wyślij na broadcast ID
print("1. Wysyłam DiagnosticSessionControl (0x10) na 0x7DF...")
vn.send_fd(0x7DF, diag_session, brs=True)
time.sleep(0.1)

print("2. Wysyłam TesterPresent (0x3E) na 0x7DF...")
vn.send_fd(0x7DF, tester_present, brs=True)
time.sleep(0.1)

# Może moduł drzwi ma inny ID? Typowe dla drzwi kierowcy:
# 0x6B1, 0x631, 0x5F1 - zależy od modelu
door_ids = [0x631, 0x6B1, 0x5F1, 0x651]
for door_id in door_ids:
    print(f"3. Wysyłam TesterPresent na 0x{door_id:03X}...")
    vn.send_fd(door_id, tester_present, brs=True)
    time.sleep(0.05)

print("\n--- Nasłuchuję odpowiedzi (10 sekund) ---\n")

try:
    start = time.time()
    count = 0
    while (time.time() - start) < 10:
        msg = vn.receive(timeout_ms=100)
        if msg:
            count += 1
            print(f"[{count}] {msg}")
        
        # Co 2 sekundy wysyłaj TesterPresent żeby utrzymać moduł aktywny
        if int(time.time() - start) % 2 == 0:
            vn.send_fd(0x7DF, tester_present, brs=True)
            
except KeyboardInterrupt:
    pass

print(f"\nOdebrano {count} wiadomości.")
vn.close()
