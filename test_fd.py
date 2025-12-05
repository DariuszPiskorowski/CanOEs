"""Test CAN FD capabilities"""
from vn1640a_can import VN1640A, XL_SUCCESS
from ctypes import *

vn = VN1640A()
vn.open()

print("=" * 50)
print("Test CAN FD dla VN1640A")
print("=" * 50)

# Test 1: CAN klasyczny (powinno działać)
print("\n[TEST 1] CAN klasyczny...")
vn.start(1)
result = vn.send(0x100, [0x01, 0x02, 0x03, 0x04])
print(f"Wynik CAN klasyczny: {result}")
vn.stop()

# Test 2: CAN FD
print("\n[TEST 2] CAN FD...")
vn.start_fd(1)
result = vn.send_fd(0x100, [0x01, 0x02, 0x03, 0x04], fd=True, brs=False)
print(f"Wynik CAN FD (bez BRS): {result}")

result = vn.send_fd(0x100, [0x01, 0x02, 0x03, 0x04], fd=True, brs=True)
print(f"Wynik CAN FD (z BRS): {result}")

result = vn.send_fd(0x100, [0x01, 0x02, 0x03, 0x04], fd=False)
print(f"Wynik CAN klasyczny przez FD port: {result}")
vn.stop()

vn.close()
print("\n[KONIEC]")
