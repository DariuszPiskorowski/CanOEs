"""
Skrypt diagnostyczny - pokazuje wszystkie kanały z konfiguracji Vector
"""

import ctypes
from ctypes import c_uint, c_char, c_ubyte, c_ushort, c_ulong, c_ulonglong
from ctypes import Structure, byref

XLuint64 = c_ulonglong

class XLchannelConfig(Structure):
    _fields_ = [
        ("name", c_char * 32),
        ("hwType", c_ubyte),
        ("hwIndex", c_ubyte),
        ("hwChannel", c_ubyte),
        ("transceiverType", c_ushort),
        ("transceiverState", c_ushort),
        ("configError", c_ushort),
        ("channelIndex", c_ubyte),
        ("channelMask", XLuint64),
        ("channelCapabilities", c_uint),
        ("channelBusCapabilities", c_uint),
        ("isOnBus", c_ubyte),
        ("connectedBusType", c_uint),
        ("busParams", c_ubyte * 32),
        ("driverVersion", c_uint),
        ("interfaceVersion", c_uint),
        ("raw_data", c_uint * 10),
        ("serialNumber", c_uint),
        ("articleNumber", c_uint),
        ("transceiverName", c_char * 32),
        ("specialCabFlags", c_uint),
        ("dominantTimeout", c_uint),
        ("dominantRecessiveDelay", c_ubyte),
        ("recessiveDominantDelay", c_ubyte),
        ("connectionInfo", c_ubyte),
        ("currentlyAvailableTimestamps", c_ubyte),
        ("minimalSupplyVoltage", c_ushort),
        ("maximalSupplyVoltage", c_ushort),
        ("maximalBaudrate", c_uint),
        ("fpgaCoreCapabilities", c_ubyte),
        ("specialDeviceStatus", c_ubyte),
        ("channelBusActiveCapabilities", c_ushort),
        ("breakOffset", c_ushort),
        ("delimiterOffset", c_ushort),
        ("reserved", c_uint * 3),
    ]

class XLdriverConfig(Structure):
    _fields_ = [
        ("dllVersion", c_uint),
        ("channelCount", c_uint),
        ("reserved", c_uint * 10),
        ("channel", XLchannelConfig * 64),
    ]


def main():
    dll = ctypes.windll.LoadLibrary("vxlapi64.dll")
    
    status = dll.xlOpenDriver()
    print(f"xlOpenDriver: {status}")
    
    config = XLdriverConfig()
    status = dll.xlGetDriverConfig(byref(config))
    print(f"xlGetDriverConfig: {status}")
    print(f"DLL Version: {config.dllVersion}")
    print(f"Channel Count: {config.channelCount}")
    
    print("\n" + "=" * 80)
    print("WSZYSTKIE KANAŁY:")
    print("=" * 80)
    
    for i in range(config.channelCount):
        ch = config.channel[i]
        name = ch.name.decode('utf-8', errors='ignore').strip()
        transceiver = ch.transceiverName.decode('utf-8', errors='ignore').strip()
        
        print(f"\n[{i}] {name}")
        print(f"    hwType: {ch.hwType}, hwIndex: {ch.hwIndex}, hwChannel: {ch.hwChannel}")
        print(f"    channelIndex: {ch.channelIndex}")
        print(f"    channelMask: 0x{ch.channelMask:X}")
        print(f"    serialNumber: {ch.serialNumber}")
        print(f"    articleNumber: {ch.articleNumber}")
        print(f"    transceiver: {transceiver}")
        print(f"    isOnBus: {ch.isOnBus}")
        print(f"    connectedBusType: {ch.connectedBusType}")
        print(f"    channelBusCapabilities: 0x{ch.channelBusCapabilities:X}")
        
        # Decode bus type
        bus_types = []
        if ch.channelBusCapabilities & 0x00000001: bus_types.append("CAN")
        if ch.channelBusCapabilities & 0x00000002: bus_types.append("LIN")
        if ch.channelBusCapabilities & 0x00000004: bus_types.append("FlexRay")
        if ch.channelBusCapabilities & 0x00010000: bus_types.append("DAIO")
        if ch.channelBusCapabilities & 0x00100000: bus_types.append("Ethernet")
        if ch.channelBusCapabilities & 0x01000000: bus_types.append("ARINC429")
        print(f"    Obsługiwane magistrale: {', '.join(bus_types) if bus_types else 'N/A'}")
    
    dll.xlCloseDriver()
    print("\n[OK] Zakończono diagnostykę")


if __name__ == "__main__":
    main()
