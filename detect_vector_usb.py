"""
Skrypt do wykrywania urządzeń USB Vector (CANoe/CANalyzer)
Autor: D. Piskorowski
Data: December.2025
"""

import subprocess
import re
from typing import List, Dict, Optional

def get_usb_devices_wmi() -> List[Dict]:
    """
    Pobiera listę urządzeń USB za pomocą WMI (Windows Management Instrumentation).
    """
    devices = []
    
    # Pobierz urządzenia USB przez PowerShell/WMI
    ps_command = '''
    Get-WmiObject Win32_PnPEntity | Where-Object { 
        $_.DeviceID -like "USB*" -or $_.DeviceID -like "*VID_*" 
    } | Select-Object Name, DeviceID, Description, Manufacturer, Status | ConvertTo-Json
    '''
    
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode == 0 and result.stdout.strip():
            import json
            data = json.loads(result.stdout)
            
            # Jeśli jest tylko jedno urządzenie, PowerShell zwraca obiekt, nie listę
            if isinstance(data, dict):
                data = [data]
            
            devices = data
    except Exception as e:
        print(f"Błąd podczas pobierania urządzeń WMI: {e}")
    
    return devices


def get_vector_devices(all_devices: List[Dict]) -> List[Dict]:
    """
    Filtruje urządzenia Vector z listy wszystkich urządzeń USB.
    
    Vector używa następujących identyfikatorów:
    - VID (Vendor ID): 1CBE (hex) = 7358 (dec) - Vector Informatik GmbH
    - Alternatywnie szukamy "Vector" w nazwie/opisie/producencie
    """
    vector_devices = []
    
    # Vector Vendor ID w różnych formatach
    VECTOR_VID_HEX = "1CBE"
    VECTOR_VID_PATTERNS = [
        f"VID_{VECTOR_VID_HEX}",
        f"VID&{VECTOR_VID_HEX}",
        "VECTOR",
    ]
    
    for device in all_devices:
        device_id = str(device.get('DeviceID', '')).upper()
        name = str(device.get('Name', '')).upper()
        description = str(device.get('Description', '')).upper()
        manufacturer = str(device.get('Manufacturer', '')).upper()
        
        # Sprawdź czy to urządzenie Vector
        is_vector = False
        
        for pattern in VECTOR_VID_PATTERNS:
            if pattern in device_id or pattern in name or pattern in description or pattern in manufacturer:
                is_vector = True
                break
        
        if is_vector:
            vector_devices.append(device)
    
    return vector_devices


def get_vector_hardware_detailed() -> List[Dict]:
    """
    Pobiera szczegółowe informacje o urządzeniach Vector.
    Szuka specyficznych urządzeń jak CANcaseXL, VN1610, VN1630, itp.
    """
    vector_hardware = []
    
    # Lista znanych nazw urządzeń Vector
    vector_device_names = [
        "CANcaseXL",
        "CANboardXL",
        "CANcardXL", 
        "VN1610",
        "VN1611",
        "VN1630",
        "VN1640",
        "VN5610",
        "VN5620",
        "VN7600",
        "VN8900",
        "VN1530",
        "VN1531",
        "VN89",
        "Vector",
    ]
    
    # Szukaj w rejestrze urządzeń
    ps_command = '''
    Get-WmiObject Win32_PnPEntity | Where-Object { 
        $_.Name -like "*Vector*" -or 
        $_.Name -like "*CAN*" -or
        $_.Name -like "*VN1*" -or
        $_.Name -like "*VN5*" -or
        $_.Name -like "*VN7*" -or
        $_.Name -like "*VN8*" -or
        $_.Manufacturer -like "*Vector*"
    } | Select-Object Name, DeviceID, Description, Manufacturer, Status, Service | ConvertTo-Json
    '''
    
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode == 0 and result.stdout.strip():
            import json
            data = json.loads(result.stdout)
            
            if isinstance(data, dict):
                data = [data]
            
            vector_hardware = data
    except Exception as e:
        print(f"Błąd: {e}")
    
    return vector_hardware


def check_vector_driver_installed() -> bool:
    """
    Sprawdza czy sterowniki Vector są zainstalowane w systemie.
    """
    ps_command = '''
    Get-WmiObject Win32_SystemDriver | Where-Object {
        $_.Name -like "*vector*" -or $_.Name -like "*vxl*"
    } | Select-Object Name, State, Status | ConvertTo-Json
    '''
    
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode == 0 and result.stdout.strip():
            import json
            data = json.loads(result.stdout)
            if data:
                print("\n=== Sterowniki Vector ===")
                if isinstance(data, dict):
                    data = [data]
                for driver in data:
                    print(f"  Nazwa: {driver.get('Name', 'N/A')}")
                    print(f"  Stan: {driver.get('State', 'N/A')}")
                    print(f"  Status: {driver.get('Status', 'N/A')}")
                    print()
                return True
    except Exception as e:
        print(f"Błąd sprawdzania sterowników: {e}")
    
    return False


def parse_vid_pid(device_id: str) -> Dict[str, Optional[str]]:
    """
    Wyciąga VID i PID z DeviceID.
    """
    vid_match = re.search(r'VID[_&]([0-9A-Fa-f]{4})', device_id)
    pid_match = re.search(r'PID[_&]([0-9A-Fa-f]{4})', device_id)
    
    return {
        'VID': vid_match.group(1) if vid_match else None,
        'PID': pid_match.group(1) if pid_match else None
    }


def print_device_info(device: Dict, index: int = 0):
    """
    Wyświetla informacje o urządzeniu w czytelnym formacie.
    """
    print(f"\n--- Urządzenie #{index + 1} ---")
    print(f"  Nazwa: {device.get('Name', 'N/A')}")
    print(f"  Opis: {device.get('Description', 'N/A')}")
    print(f"  Producent: {device.get('Manufacturer', 'N/A')}")
    print(f"  Status: {device.get('Status', 'N/A')}")
    
    device_id = device.get('DeviceID', '')
    print(f"  DeviceID: {device_id}")
    
    # Parsuj VID/PID
    vid_pid = parse_vid_pid(device_id)
    if vid_pid['VID']:
        print(f"  VID: 0x{vid_pid['VID']} (Vendor ID)")
    if vid_pid['PID']:
        print(f"  PID: 0x{vid_pid['PID']} (Product ID)")


def main():
    print("=" * 60)
    print("  DETEKCJA URZĄDZEŃ USB - FOCUS NA VECTOR (CANoe)")
    print("=" * 60)
    
    # 1. Sprawdź sterowniki Vector
    print("\n[1] Sprawdzanie sterowników Vector...")
    drivers_found = check_vector_driver_installed()
    if not drivers_found:
        print("  Nie znaleziono sterowników Vector w systemie.")
    
    # 2. Szukaj urządzeń Vector
    print("\n[2] Szukanie urządzeń Vector...")
    vector_devices = get_vector_hardware_detailed()
    
    if vector_devices:
        print(f"\n>>> ZNALEZIONO {len(vector_devices)} URZĄDZENIE(A) VECTOR <<<")
        for i, device in enumerate(vector_devices):
            print_device_info(device, i)
    else:
        print("\n  Nie znaleziono urządzeń Vector.")
        print("  Upewnij się, że urządzenie jest podłączone do USB.")
    
    # 3. Pokaż wszystkie urządzenia USB (dla kontekstu)
    print("\n" + "=" * 60)
    print("[3] Wszystkie urządzenia USB w systemie:")
    print("=" * 60)
    
    all_usb = get_usb_devices_wmi()
    
    if all_usb:
        # Filtruj tylko te z VID (prawdziwe urządzenia USB)
        real_usb = [d for d in all_usb if 'VID_' in str(d.get('DeviceID', ''))]
        print(f"\nZnaleziono {len(real_usb)} urządzeń USB z VID/PID:")
        
        for i, device in enumerate(real_usb[:15]):  # Ogranicz do 15 dla czytelności
            name = device.get('Name', 'Nieznane')
            manufacturer = device.get('Manufacturer', 'N/A')
            device_id = device.get('DeviceID', '')
            vid_pid = parse_vid_pid(device_id)
            
            vid_str = f"0x{vid_pid['VID']}" if vid_pid['VID'] else "N/A"
            
            # Zaznacz urządzenia Vector
            marker = " [VECTOR]" if vid_pid['VID'] and vid_pid['VID'].upper() == "1CBE" else ""
            
            print(f"  {i+1}. {name} (VID: {vid_str}){marker}")
    else:
        print("  Nie udało się pobrać listy urządzeń USB.")
    
    print("\n" + "=" * 60)
    print("  KONIEC SKANOWANIA")
    print("=" * 60)
    
    return vector_devices


if __name__ == "__main__":
    detected_vector = main()
    
    # Zwróć wynik dla dalszego użycia
    if detected_vector:
        print(f"\n[INFO] Wykryto {len(detected_vector)} urządzenie(a) Vector - gotowe do dalszej pracy!")
    else:
        print("\n[INFO] Brak urządzeń Vector - podłącz urządzenie i uruchom ponownie.")
