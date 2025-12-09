"""
Test to check license information for CAN FD
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_char, c_ubyte, c_int, c_char_p, byref, POINTER

# Load DLL
dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

print("=" * 60)
print("License and API Information Check")
print("=" * 60)

# Open driver
status = dll.xlOpenDriver()
print(f"\nxlOpenDriver: {status}")

if status == 0:
    # Get DLL version string
    try:
        dll.xlGetVersionString.restype = c_char_p
        version = dll.xlGetVersionString()
        print(f"Version String: {version.decode() if version else 'N/A'}")
    except:
        print("xlGetVersionString not available")
    
    # Try to get license info if available
    try:
        # xlGetLicenseInfo(XLportHandle portHandle, char* pBuffer, unsigned int bufferSize)
        buffer = ctypes.create_string_buffer(1024)
        status = dll.xlGetLicenseInfo(0, buffer, 1024)
        print(f"xlGetLicenseInfo: {status}")
        if status == 0:
            print(f"License Info: {buffer.value.decode()}")
    except Exception as e:
        print(f"xlGetLicenseInfo error: {e}")
    
    # Try different approach - check what happens with specific channel access rights
    print("\n" + "-" * 40)
    print("Testing channel access...")
    
    # Set up application config
    app_name = ctypes.create_string_buffer(b"CanOEs_Test")
    hw_type = 59  # VN1640A
    hw_index = 0
    hw_channel = 0
    bus_type = 0x00000001  # XL_BUS_TYPE_CAN
    
    # Get channel mask
    channel_mask = c_uint64()
    permission_mask = c_uint64()
    
    dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
    dll.xlGetChannelIndex.restype = c_int
    
    idx = dll.xlGetChannelIndex(hw_type, hw_index, hw_channel)
    print(f"xlGetChannelIndex({hw_type}, {hw_index}, {hw_channel}): {idx}")
    
    if idx >= 0:
        channel_mask.value = 1 << idx
        print(f"Channel mask: 0x{channel_mask.value:016X}")
        
        # Try to set app config
        status = dll.xlSetApplConfig(
            app_name,
            0,  # app channel
            hw_type,
            hw_index,
            hw_channel,
            bus_type
        )
        print(f"xlSetApplConfig: {status}")
        
        # Get app config
        app_hw_type = c_uint()
        app_hw_index = c_uint()
        app_hw_channel = c_uint()
        app_bus_type = c_uint()
        
        status = dll.xlGetApplConfig(
            app_name,
            0,
            byref(app_hw_type),
            byref(app_hw_index),
            byref(app_hw_channel),
            bus_type
        )
        print(f"xlGetApplConfig: {status}")
        if status == 0:
            print(f"  hwType={app_hw_type.value}, hwIndex={app_hw_index.value}, hwChannel={app_hw_channel.value}")
        
        # Open port 
        port_handle = c_int()
        port_name = ctypes.create_string_buffer(b"CanOEs_FD_Test")
        permission_mask.value = channel_mask.value
        
        status = dll.xlOpenPort(
            byref(port_handle),
            port_name,
            channel_mask,
            byref(permission_mask),
            256,  # rx queue size
            3,    # XL_INTERFACE_VERSION_V3 
            bus_type
        )
        print(f"\nxlOpenPort (V3): {status}")
        print(f"  port_handle: {port_handle.value}")
        print(f"  permission_mask: 0x{permission_mask.value:016X}")
        
        if status == 0 and port_handle.value > 0:
            # Check what features are available on this port
            
            # Try to set CAN FD config
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
            print(f"\nxlCanFdSetConfiguration: {status}")
            if status == 101:
                print("  -> XL_ERR_NO_LICENSE - FD license not available for this port")
            elif status == 0:
                print("  -> SUCCESS! FD configuration applied")
            else:
                print(f"  -> Other error")
            
            # Close port
            dll.xlClosePort(port_handle)
            print("Port closed")
        
        # Now try with XL_INTERFACE_VERSION_V4
        print("\n" + "-" * 40)
        print("Trying with V4 interface...")
        
        permission_mask.value = channel_mask.value
        status = dll.xlOpenPort(
            byref(port_handle),
            port_name,
            channel_mask,
            byref(permission_mask),
            256,
            4,    # XL_INTERFACE_VERSION_V4 
            bus_type
        )
        print(f"\nxlOpenPort (V4): {status}")
        print(f"  port_handle: {port_handle.value}")
        print(f"  permission_mask: 0x{permission_mask.value:016X}")
        
        if status == 0 and port_handle.value > 0:
            status = dll.xlCanFdSetConfiguration(port_handle, channel_mask, byref(fd_conf))
            print(f"\nxlCanFdSetConfiguration (V4): {status}")
            if status == 101:
                print("  -> XL_ERR_NO_LICENSE")
            elif status == 0:
                print("  -> SUCCESS!")
            
            dll.xlClosePort(port_handle)
            print("Port closed")
    
    dll.xlCloseDriver()
    print("\nxlCloseDriver called")

print("\n" + "=" * 60)
print("Done")
