"""
Test to check why permission is denied for CAN FD
"""
import ctypes
from ctypes import Structure, c_uint, c_uint64, c_char, c_ubyte, c_int, byref

# Load DLL
dll = ctypes.windll.LoadLibrary("vxlapi64.dll")

print("=" * 60)
print("Permission and Init Access Check")
print("=" * 60)

# Open driver
status = dll.xlOpenDriver()
print(f"\nxlOpenDriver: {status}")

if status == 0:
    # Set up
    hw_type = 59
    hw_index = 0
    hw_channel = 0
    bus_type = 0x00000001  # XL_BUS_TYPE_CAN
    
    # Get channel index
    dll.xlGetChannelIndex.argtypes = [c_int, c_int, c_int]
    dll.xlGetChannelIndex.restype = c_int
    idx = dll.xlGetChannelIndex(hw_type, hw_index, hw_channel)
    print(f"xlGetChannelIndex: {idx}")
    
    channel_mask = c_uint64(1 << idx)
    print(f"Channel mask: 0x{channel_mask.value:016X}")
    
    # Test 1: Open with init access required (grant=channel_mask)
    print("\n" + "=" * 40)
    print("TEST 1: Request init access")
    
    port_handle = c_int()
    permission_mask = c_uint64(channel_mask.value)  # Request permission
    port_name = ctypes.create_string_buffer(b"Test1")
    
    status = dll.xlOpenPort(
        byref(port_handle),
        port_name,
        channel_mask,
        byref(permission_mask),
        256,
        3,  # V3
        bus_type
    )
    print(f"xlOpenPort: status={status}, handle={port_handle.value}")
    print(f"Requested permission: 0x{channel_mask.value:016X}")
    print(f"Granted permission:   0x{permission_mask.value:016X}")
    
    if permission_mask.value == 0:
        print("** INIT ACCESS DENIED - Another app may have exclusive access **")
    
    if port_handle.value > 0:
        dll.xlClosePort(port_handle)
        print("Closed port")
    
    # Test 2: Open without init access (permission_mask = 0)
    print("\n" + "=" * 40)
    print("TEST 2: Without init access request")
    
    port_handle = c_int()
    permission_mask = c_uint64(0)  # Don't request permission
    
    status = dll.xlOpenPort(
        byref(port_handle),
        port_name,
        channel_mask,
        byref(permission_mask),
        256,
        3,
        bus_type
    )
    print(f"xlOpenPort: status={status}, handle={port_handle.value}")
    print(f"Granted permission: 0x{permission_mask.value:016X}")
    
    if port_handle.value > 0:
        # Try to activate - should fail without init access
        status = dll.xlActivateChannel(port_handle, channel_mask, bus_type, 0)
        print(f"xlActivateChannel: {status}")
        
        dll.xlClosePort(port_handle)
        print("Closed port")
    
    # Test 3: Check if device is in use
    print("\n" + "=" * 40)
    print("TEST 3: Check device availability with different app names")
    
    # Try opening with a different port name
    for name in [b"CANalyzer", b"CANoe", b"vSignalyzer", b"TestApp"]:
        port_handle = c_int()
        permission_mask = c_uint64(channel_mask.value)
        port_name = ctypes.create_string_buffer(name)
        
        status = dll.xlOpenPort(
            byref(port_handle),
            port_name,
            channel_mask,
            byref(permission_mask),
            256,
            3,
            bus_type
        )
        got_permission = permission_mask.value != 0
        print(f"  {name.decode():15} -> status={status}, handle={port_handle.value}, permission={got_permission}")
        
        if port_handle.value > 0:
            dll.xlClosePort(port_handle)
    
    # Test 4: Try with XL_ACTIVATE_RESET flag
    print("\n" + "=" * 40)
    print("TEST 4: Full CAN FD test with init access")
    
    XL_ACTIVATE_RESET = 8
    
    port_handle = c_int()
    permission_mask = c_uint64(channel_mask.value)
    port_name = ctypes.create_string_buffer(b"ResetTest")
    
    status = dll.xlOpenPort(
        byref(port_handle),
        port_name,
        channel_mask,
        byref(permission_mask),
        256,
        3,
        bus_type
    )
    print(f"xlOpenPort: status={status}, handle={port_handle.value}")
    print(f"Granted permission: 0x{permission_mask.value:016X}")
    
    if port_handle.value > 0 and permission_mask.value != 0:
        # Set baud rate
        class XLchipParams(Structure):
            _fields_ = [
                ("bitRate", c_uint),
                ("sjw", c_ubyte),
                ("tseg1", c_ubyte),
                ("tseg2", c_ubyte),
                ("sam", c_ubyte),
            ]
        
        params = XLchipParams()
        params.bitRate = 500000
        params.sjw = 1
        params.tseg1 = 4
        params.tseg2 = 3
        params.sam = 1
        
        status = dll.xlCanSetChannelBitrate(port_handle, channel_mask, 500000)
        print(f"xlCanSetChannelBitrate: {status}")
        
        # Activate with reset
        status = dll.xlActivateChannel(port_handle, channel_mask, bus_type, XL_ACTIVATE_RESET)
        print(f"xlActivateChannel (with RESET): {status}")
        
        if status == 0:
            print("** CAN Classic channel activated successfully! **")
            
            # Now try FD config
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
            
            # Deactivate first
            dll.xlDeactivateChannel(port_handle, channel_mask)
            print("Channel deactivated")
            
            status = dll.xlCanFdSetConfiguration(port_handle, channel_mask, byref(fd_conf))
            print(f"xlCanFdSetConfiguration: {status}")
            if status == 101:
                print("  -> NO_LICENSE for CAN FD")
            elif status == 0:
                print("  -> SUCCESS! CAN FD configured!")
            else:
                print(f"  -> Error code: {status}")
        
        dll.xlClosePort(port_handle)
        print("Closed port")
    
    dll.xlCloseDriver()

print("\n" + "=" * 60)
print("Done")
