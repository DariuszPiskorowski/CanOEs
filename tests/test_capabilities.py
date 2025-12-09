"""
Test to check VN1640A channel capabilities - especially CAN FD support flags
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_char, c_ubyte, c_ushort, c_int

# Load DLL
dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

# Capability flags (from vxlapi.h)
XL_CHANNEL_FLAG_CANFD_ISO_SUPPORT = 0x80000000
XL_CHANNEL_FLAG_CANFD_BOSCH_SUPPORT = 0x20000000

# Bus capabilities
XL_BUS_COMPATIBLE_CAN = 0x00000001
XL_BUS_ACTIVE_CAP_CAN = 0x00010000
XL_BUS_COMPATIBLE_CANFD = 0x00000002  # guessing
XL_BUS_ACTIVE_CAP_CANFD = 0x00020000  # guessing

class XLchannelConfig(Structure):
    _pack_ = 1
    _fields_ = [
        ("name", c_char * 32),
        ("hwType", c_ubyte),
        ("hwIndex", c_ubyte),
        ("hwChannel", c_ubyte),
        ("transceiverType", c_ushort),
        ("transceiverState", c_ushort),
        ("configError", c_ushort),
        ("channelIndex", c_ubyte),
        ("channelMask", c_uint64),
        ("channelCapabilities", c_uint),
        ("channelBusCapabilities", c_uint),
        ("isOnBus", c_ubyte),
        ("connectedBusType", c_uint),
        ("busParams", c_ubyte * 48),
        ("_doNotUse", c_uint),
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
    _pack_ = 1
    _fields_ = [
        ("dllVersion", c_uint),
        ("channelCount", c_uint),
        ("reserved", c_uint * 10),
        ("channel", XLchannelConfig * 64),
    ]

print("=" * 60)
print("VN1640A Channel Capabilities Check")
print("=" * 60)

# Open driver
status = dll.xlOpenDriver()
print(f"\nxlOpenDriver: {status}")

if status == 0:
    # Get driver config
    config = XLdriverConfig()
    status = dll.xlGetDriverConfig(ctypes.byref(config))
    print(f"xlGetDriverConfig: {status}")
    
    if status == 0:
        print(f"\nDLL Version: {config.dllVersion}")
        print(f"Channel Count: {config.channelCount}")
        print("\n" + "=" * 60)
        
        for i in range(config.channelCount):
            ch = config.channel[i]
            name = ch.name.decode('utf-8', errors='ignore')
            
            # Only show VN1640A channels (hwType=59)
            if ch.hwType == 59 or "VN1640" in name:
                print(f"\nChannel {i}: {name}")
                print(f"  hwType: {ch.hwType}")
                print(f"  hwIndex: {ch.hwIndex}")
                print(f"  hwChannel: {ch.hwChannel}")
                print(f"  channelMask: 0x{ch.channelMask:016X}")
                print(f"  channelIndex: {ch.channelIndex}")
                print(f"  serialNumber: {ch.serialNumber}")
                print(f"  transceiverType: {ch.transceiverType}")
                print(f"  connectedBusType: {ch.connectedBusType}")
                print(f"  isOnBus: {ch.isOnBus}")
                
                # Capabilities
                caps = ch.channelCapabilities
                print(f"\n  channelCapabilities: 0x{caps:08X}")
                if caps & XL_CHANNEL_FLAG_CANFD_ISO_SUPPORT:
                    print("    -> CAN FD ISO SUPPORT")
                if caps & XL_CHANNEL_FLAG_CANFD_BOSCH_SUPPORT:
                    print("    -> CAN FD BOSCH SUPPORT")
                if caps & 0x00000001:
                    print("    -> Bit 0 set")
                if caps & 0x00000002:
                    print("    -> Bit 1 set")
                if caps & 0x00010000:
                    print("    -> Bit 16 set (ACTIVE_CAP_CAN?)")
                    
                # Bus capabilities
                bus_caps = ch.channelBusCapabilities
                print(f"\n  channelBusCapabilities: 0x{bus_caps:08X}")
                if bus_caps & 0x00000001:
                    print("    -> CAN compatible")
                if bus_caps & 0x00000002:
                    print("    -> Bit 1 (possibly CANFD)")
                if bus_caps & 0x00010000:
                    print("    -> CAN active cap")
                if bus_caps & 0x00020000:
                    print("    -> Bit 17 (possibly CANFD active)")
                
                # Bus active capabilities
                bus_active = ch.channelBusActiveCapabilities
                print(f"\n  channelBusActiveCapabilities: 0x{bus_active:04X}")
                
                print("-" * 40)
    
    dll.xlCloseDriver()
    print("\nxlCloseDriver called")

print("\n" + "=" * 60)
print("Done")
