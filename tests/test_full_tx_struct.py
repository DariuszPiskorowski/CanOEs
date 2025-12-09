"""
Test z pełną strukturą XLcanTxEvent (z nagłówkiem)
Zgodnie z vxlapi.h:
  typedef struct {
    unsigned short tag;           // cyclic counter
    unsigned short transId;
    unsigned char  channelIndex;  
    unsigned char  reserved[3];
    XL_CAN_TX_MSG  tagData;
  } XLcanTxEvent;
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_ubyte, c_ushort, c_int, byref, sizeof, POINTER

dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

class XLcanFdConf(Structure):
    _pack_ = 1
    _fields_ = [
        ("arbitrationBitRate", c_uint),
        ("sjwAbr", c_uint),
        ("tseg1Abr", c_uint),
        ("tseg2Abr", c_uint),
        ("dataBitRate", c_uint),
        ("sjwDbr", c_uint),
        ("tseg1Dbr", c_uint),
        ("tseg2Dbr", c_uint),
        ("reserved", c_uint * 2),
    ]

class XL_CAN_TX_MSG(Structure):
    _pack_ = 1
    _fields_ = [
        ("canId", c_uint),
        ("msgFlags", c_uint),
        ("dlc", c_ubyte),
        ("txAttemptConf", c_ubyte),
        ("reserved", c_ushort),
        ("data", c_ubyte * 64),
    ]

class XLcanTxEvent(Structure):
    _pack_ = 1
    _fields_ = [
        ("tag", c_ushort),
        ("transId", c_ushort),
        ("channelIndex", c_ubyte),
        ("reserved", c_ubyte * 3),
        ("tagData", XL_CAN_TX_MSG),
    ]

print(f"XL_CAN_TX_MSG size: {sizeof(XL_CAN_TX_MSG)}")
print(f"XLcanTxEvent size: {sizeof(XLcanTxEvent)}")

XL_CAN_EV_TAG_TX_MSG = 0x0440

status = dll.xlOpenDriver()
print(f"\nxlOpenDriver: {status}")

dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
dll.xlGetChannelIndex.restype = c_int
idx = dll.xlGetChannelIndex(59, 0, 0)
channel_mask = c_uint64(1 << idx)

port_handle = c_int(0)
permission_mask = c_uint64(channel_mask.value)

status = dll.xlOpenPort(
    byref(port_handle),
    b"FullStructTest",
    channel_mask,
    byref(permission_mask),
    256,
    4,  # V4
    1   # CAN
)
print(f"xlOpenPort: {status}, handle={port_handle.value}")

if status == 0 and permission_mask.value != 0:
    fd_conf = XLcanFdConf()
    fd_conf.arbitrationBitRate = 500000
    fd_conf.sjwAbr = 2
    fd_conf.tseg1Abr = 6
    fd_conf.tseg2Abr = 3
    fd_conf.dataBitRate = 2000000
    fd_conf.sjwDbr = 2
    fd_conf.tseg1Dbr = 6
    fd_conf.tseg2Dbr = 3
    
    status = dll.xlCanFdSetConfiguration(port_handle, channel_mask, byref(fd_conf))
    print(f"xlCanFdSetConfiguration: {status}")
    
    status = dll.xlActivateChannel(port_handle, channel_mask, 1, 8)
    print(f"xlActivateChannel: {status}")
    
    if status == 0:
        print("\n--- Test z pełną strukturą XLcanTxEvent ---")
        
        tx = XLcanTxEvent()
        tx.tag = XL_CAN_EV_TAG_TX_MSG
        tx.transId = 0
        tx.channelIndex = idx
        tx.tagData.canId = 0x123
        tx.tagData.msgFlags = 0x0003  # EDL + BRS
        tx.tagData.dlc = 8
        for i in range(8):
            tx.tagData.data[i] = i + 1
        
        msg_count = c_uint(1)
        
        dll.xlCanTransmitEx.argtypes = [c_int, c_uint64, POINTER(c_uint), POINTER(XLcanTxEvent)]
        dll.xlCanTransmitEx.restype = c_int
        
        status = dll.xlCanTransmitEx(port_handle.value, channel_mask.value, byref(msg_count), byref(tx))
        print(f"xlCanTransmitEx (full struct): {status}")
        
        # Test z różnymi tagami
        print("\n--- Test różnych wartości tag ---")
        for tag_val in [0x0440, 0x0400, 0x0000, 0x0001, 10]:
            tx.tag = tag_val
            msg_count.value = 1
            status = dll.xlCanTransmitEx(port_handle.value, channel_mask.value, byref(msg_count), byref(tx))
            print(f"  tag=0x{tag_val:04X}: status={status}")
        
        # Test z samym XL_CAN_TX_MSG (bez nagłówka)
        print("\n--- Test z samym XL_CAN_TX_MSG (76 bajtów) ---")
        tx_simple = XL_CAN_TX_MSG()
        tx_simple.canId = 0x456
        tx_simple.msgFlags = 0x0003
        tx_simple.dlc = 8
        for i in range(8):
            tx_simple.data[i] = 0xAA
        
        dll.xlCanTransmitEx.argtypes = [c_int, c_uint64, POINTER(c_uint), POINTER(XL_CAN_TX_MSG)]
        msg_count.value = 1
        status = dll.xlCanTransmitEx(port_handle.value, channel_mask.value, byref(msg_count), byref(tx_simple))
        print(f"xlCanTransmitEx (XL_CAN_TX_MSG only): {status}")
        
    dll.xlDeactivateChannel(port_handle, channel_mask)
    dll.xlClosePort(port_handle)

dll.xlCloseDriver()
print("\nDone")
