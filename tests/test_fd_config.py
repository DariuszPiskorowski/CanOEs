"""Test CAN FD - z poprawną konfiguracją"""
from ctypes import *

dll = WinDLL('vxlapi64.dll')

XL_SUCCESS = 0
XL_HWTYPE_VN1640 = 59
XL_BUS_TYPE_CAN = 0x00000001
XL_INTERFACE_VERSION_V4 = 4
XL_ACTIVATE_RESET_CLOCK = 8

class XLcanFdConf(Structure):
    _pack_ = 1
    _fields_ = [
        ("arbitrationBitRate", c_uint),
        ("sjwAbr", c_ubyte),
        ("tseg1Abr", c_ubyte),
        ("tseg2Abr", c_ubyte),
        ("reserved1", c_ubyte),
        ("dataBitRate", c_uint),
        ("sjwDbr", c_ubyte),
        ("tseg1Dbr", c_ubyte),
        ("tseg2Dbr", c_ubyte),
        ("reserved2", c_ubyte),
        ("reserved3", c_ubyte * 2),
        ("options", c_ushort),
        ("reserved4", c_ubyte * 8),
    ]

class XLcanTxEvent(Structure):
    _pack_ = 1
    _fields_ = [
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("channelIndex", c_ubyte),
        ("reserved1", c_ubyte * 3),
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("reserved2", c_ubyte * 7),
        ("data", c_ubyte * 64),
    ]

print(f"sizeof(XLcanFdConf) = {sizeof(XLcanFdConf)}")  # powinno być 24
print(f"sizeof(XLcanTxEvent) = {sizeof(XLcanTxEvent)}")  # powinno być 88

dll.xlOpenDriver()
dll.xlGetChannelMask.restype = c_uint64
mask = dll.xlGetChannelMask(c_int(XL_HWTYPE_VN1640), c_int(0), c_int(0))
print(f"Channel mask: 0x{mask:X}")

channel_mask = c_uint64(mask)
permission_mask = c_uint64(mask)
port_handle = c_int(-1)

# Otwórz port
status = dll.xlOpenPort(
    byref(port_handle),
    b"TestFD3",
    channel_mask,
    byref(permission_mask),
    c_uint(256),
    c_uint(XL_INTERFACE_VERSION_V4),
    c_uint(XL_BUS_TYPE_CAN)
)
print(f"xlOpenPort: {status}, permission: 0x{permission_mask.value:X}")

# Próba konfiguracji FD z różnymi parametrami
configs = [
    # (name, arb_rate, data_rate, sjwAbr, tseg1Abr, tseg2Abr, sjwDbr, tseg1Dbr, tseg2Dbr)
    ("500k/2M default", 500000, 2000000, 2, 63, 16, 2, 15, 4),
    ("500k/2M alt1", 500000, 2000000, 1, 59, 20, 1, 7, 2),
    ("500k/2M zeros", 500000, 2000000, 0, 0, 0, 0, 0, 0),  # może driver sam ustawi?
    ("500k only", 500000, 500000, 2, 63, 16, 2, 63, 16),
]

for name, arb, data, sjwA, t1A, t2A, sjwD, t1D, t2D in configs:
    fd_conf = XLcanFdConf()
    fd_conf.arbitrationBitRate = arb
    fd_conf.dataBitRate = data
    fd_conf.sjwAbr = sjwA
    fd_conf.tseg1Abr = t1A
    fd_conf.tseg2Abr = t2A
    fd_conf.sjwDbr = sjwD
    fd_conf.tseg1Dbr = t1D
    fd_conf.tseg2Dbr = t2D
    fd_conf.options = 0
    
    status = dll.xlCanFdSetConfiguration(port_handle, channel_mask, byref(fd_conf))
    print(f"xlCanFdSetConfiguration ({name}): {status}")
    
    if status == 0:
        print(f"  [OK] Konfiguracja {name} zaakceptowana!")
        break

# Aktywuj i wyślij
status = dll.xlActivateChannel(port_handle, channel_mask, c_uint(XL_BUS_TYPE_CAN), c_uint(XL_ACTIVATE_RESET_CLOCK))
print(f"xlActivateChannel: {status}")

tx = XLcanTxEvent()
tx.tag = 0x0401
tx.canId = 0x100
tx.msgFlags = 0x0001  # EDL (FD)
tx.dlc = 8
for i in range(8):
    tx.data[i] = i

msg_count = c_uint(1)
status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx))
print(f"xlCanTransmitEx (FD): {status}")

# Bez FD
tx.msgFlags = 0
status = dll.xlCanTransmitEx(port_handle, channel_mask, byref(msg_count), byref(tx))
print(f"xlCanTransmitEx (klasyczny): {status}")

dll.xlDeactivateChannel(port_handle, channel_mask)
dll.xlClosePort(port_handle)
dll.xlCloseDriver()
