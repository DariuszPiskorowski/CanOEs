"""
Test biblioteki vn1640a_can.py z CAN FD
"""
from vn1640a_can import VN1640A, CANMsg

print("=" * 60)
print("Test VN1640A - CAN FD")
print("=" * 60)

vn = VN1640A()

try:
    # Otwórz sterownik
    if not vn.open():
        print("Błąd otwarcia sterownika!")
        exit(1)
    
    # Uruchom CAN FD na kanale 1
    print("\nUruchamiam CAN FD na kanale 1...")
    if not vn.start_fd(channel=1):
        print("Błąd uruchomienia CAN FD!")
        exit(1)
    
    print("\n*** CAN FD DZIAŁA! ***")
    
    # Wyślij testową wiadomość FD
    print("\nWysyłam wiadomość CAN FD (32 bajty)...")
    data = list(range(32))  # 0x00, 0x01, ..., 0x1F
    success = vn.send_fd(0x123, data, brs=True)
    
    if success:
        print("Wiadomość wysłana pomyślnie!")
    else:
        print("Błąd wysyłania (może brak drugiego węzła na magistrali)")
    
    # Nasłuchuj przez 3 sekundy
    print("\nNasłuchiwanie 3 sek...")
    messages = vn.receive_all(timeout_ms=3000, max_count=10)
    print(f"Odebrano {len(messages)} wiadomości")
    
finally:
    vn.close()

print("\n" + "=" * 60)
print("Test zakończony!")
