"""
Skrypt diagnostyczny V2 - poprawione struktury Vector XL API
"""

import ctypes
from ctypes import c_uint, c_int, c_char, c_ubyte, c_ushort, c_ulong, c_ulonglong, c_uint64
from ctypes import Structure, byref, sizeof, POINTER
import struct

# Użyj pack=1 dla dokładnego dopasowania do struktury C
class XLchannelConfig(Structure):
    _pack_ = 1
    _fields_ = [
        ("name", c_char * 32),                    # 32
        ("hwType", c_ubyte),                       # 1
        ("hwIndex", c_ubyte),                      # 1
        ("hwChannel", c_ubyte),                    # 1
        ("transceiverType", c_ushort),             # 2
        ("transceiverState", c_ushort),            # 2
        ("configError", c_ushort),                 # 2
        ("channelIndex", c_ubyte),                 # 1
        ("channelMask", c_uint64),                 # 8 - ważne! użyj c_uint64
        ("channelCapabilities", c_uint),           # 4
        ("channelBusCapabilities", c_uint),        # 4
        ("isOnBus", c_ubyte),                      # 1
        ("connectedBusType", c_uint),              # 4
        ("busParams", c_ubyte * 32),               # 32
        ("driverVersion", c_uint),                 # 4
        ("interfaceVersion", c_uint),              # 4
        ("raw_data", c_uint * 10),                 # 40
        ("serialNumber", c_uint),                  # 4
        ("articleNumber", c_uint),                 # 4
        ("transceiverName", c_char * 32),          # 32
        ("specialCabFlags", c_uint),               # 4
        ("dominantTimeout", c_uint),               # 4
        ("dominantRecessiveDelay", c_ubyte),       # 1
        ("recessiveDominantDelay", c_ubyte),       # 1
        ("connectionInfo", c_ubyte),               # 1
        ("currentlyAvailableTimestamps", c_ubyte), # 1
        ("minimalSupplyVoltage", c_ushort),        # 2
        ("maximalSupplyVoltage", c_ushort),        # 2
        ("maximalBaudrate", c_uint),               # 4
        ("fpgaCoreCapabilities", c_ubyte),         # 1
        ("specialDeviceStatus", c_ubyte),          # 1
        ("channelBusActiveCapabilities", c_ushort),# 2
        ("breakOffset", c_ushort),                 # 2
        ("delimiterOffset", c_ushort),             # 2
        ("reserved", c_uint * 3),                  # 12
    ]


class XLdriverConfig(Structure):
    _pack_ = 1
    _fields_ = [
        ("dllVersion", c_uint),
        ("channelCount", c_uint),
        ("reserved", c_uint * 10),
        ("channel", XLchannelConfig * 64),
    ]


def main():
    print(f"Rozmiar XLchannelConfig: {sizeof(XLchannelConfig)}")
    print(f"Rozmiar XLdriverConfig: {sizeof(XLdriverConfig)}")
    
    dll = ctypes.windll.LoadLibrary("vxlapi64.dll")
    
    status = dll.xlOpenDriver()
    print(f"\nxlOpenDriver: {status}")
    
    config = XLdriverConfig()
    status = dll.xlGetDriverConfig(byref(config))
    print(f"xlGetDriverConfig: {status}")
    print(f"DLL Version: 0x{config.dllVersion:08X}")
    print(f"Channel Count: {config.channelCount}")
    
    print("\n" + "=" * 80)
    print("WSZYSTKIE KANAŁY:")
    print("=" * 80)
    
    can_channels = []
    
    for i in range(min(config.channelCount, 64)):
        ch = config.channel[i]
        name = ch.name.decode('utf-8', errors='ignore').strip()
        
        if not name:
            continue
            
        transceiver = ch.transceiverName.decode('utf-8', errors='ignore').strip()
        
        print(f"\n[{i}] {name}")
        print(f"    hwType: {ch.hwType}, hwIndex: {ch.hwIndex}, hwChannel: {ch.hwChannel}")
        print(f"    channelIndex: {ch.channelIndex}")
        print(f"    channelMask: 0x{ch.channelMask:X}")
        print(f"    serialNumber: {ch.serialNumber}")
        print(f"    transceiver: {transceiver}")
        print(f"    isOnBus: {ch.isOnBus}")
        print(f"    channelBusCapabilities: 0x{ch.channelBusCapabilities:08X}")
        
        # Check for CAN capability (bit 0)
        has_can = (ch.channelBusCapabilities & 0x00000001) != 0
        has_lin = (ch.channelBusCapabilities & 0x00000002) != 0
        
        bus_list = []
        if has_can: bus_list.append("CAN")
        if has_lin: bus_list.append("LIN")
        print(f"    Magistrale: {', '.join(bus_list) if bus_list else 'inne'}")
        
        # Zapisz kanały CAN
        if has_can or 'CAN' in name.upper() or 'VN1640' in name:
            can_channels.append({
                'index': i,
                'name': name,
                'hwChannel': ch.hwChannel,
                'channelMask': ch.channelMask,
                'serial': ch.serialNumber,
            })
    
    print("\n" + "=" * 80)
    print("KANAŁY CAN (do użycia):")
    print("=" * 80)
    
    for i, ch in enumerate(can_channels):
        print(f"  CH{i+1}: {ch['name']}")
        print(f"        Maska: 0x{ch['channelMask']:X}")
        print(f"        Serial: {ch['serial']}")
    
    dll.xlCloseDriver()


if __name__ == "__main__":
    main()
