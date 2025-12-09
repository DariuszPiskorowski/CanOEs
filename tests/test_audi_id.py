"""Test komunikacji z modułem Audi: TX=0x1BFEE200, RX=0x1BFEE201"""
import time
from vn1640a_can import VN1640A

TX_ID = 0x1BFEE200  # ID do wysyłania
RX_ID = 0x1BFEE201  # ID do odbierania

tester_present = [0x02, 0x3E, 0x00]

def main():
    print("="*60)
    print(f"Audi TX: 0x{TX_ID:X}, RX: 0x{RX_ID:X}")
    print("Wysyłam TesterPresent na TX, nasłuchuję RX...")
    print("="*60)

    vn = VN1640A()
    if not vn.open():
        print("Błąd otwarcia")
        return
    if not vn.start_fd(channel=1):
        print("Błąd startu FD")
        vn.close()
        return

    # Wyślij TesterPresent na TX_ID
    print(f"Wysyłam TesterPresent na 0x{TX_ID:X}...")
    vn.send_fd(TX_ID, tester_present, brs=True)
    time.sleep(0.1)

    print(f"Nasłuchuję odpowiedzi na 0x{RX_ID:X} przez 10 sekund...")
    start = time.time()
    count = 0
    while (time.time() - start) < 10:
        msg = vn.receive(timeout_ms=100)
        if msg and msg.id == RX_ID:
            count += 1
            print(f"[{count}] {msg}")
    print(f"\nOdebrano {count} wiadomości na RX.")
    vn.close()

if __name__ == "__main__":
    main()
