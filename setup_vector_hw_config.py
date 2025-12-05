"""
Skrypt pomocniczy do konfiguracji Vector Hardware Config
Otwiera Vector Hardware Config i pokazuje instrukcje
"""

import subprocess
import os


def find_vector_hw_config():
    """Szuka Vector Hardware Config na dysku."""
    possible_paths = [
        r"C:\Program Files\Vector CANoe\Exec32\VHWConfig.exe",
        r"C:\Program Files (x86)\Vector CANoe\Exec32\VHWConfig.exe",
        r"C:\Program Files\Vector\VHWConfig.exe",
        r"C:\Program Files (x86)\Vector\VHWConfig.exe",
        r"C:\Users\Public\Documents\Vector XL Driver Library\bin\vHWConfig.exe",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Szukaj w PATH
    try:
        result = subprocess.run(
            ["where", "vHWConfig.exe"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    
    return None


def main():
    print("=" * 60)
    print("  KONFIGURACJA VECTOR HARDWARE CONFIG")
    print("=" * 60)
    
    print("""
Aby używać python-can z Vector VN1640A, musisz skonfigurować
aplikację w Vector Hardware Config:

1. Otwórz Vector Hardware Config
2. Kliknij "Application" w menu
3. Wybierz "Add..." 
4. Wpisz nazwę aplikacji: PythonVectorCAN
5. Przypisz kanały:
   - Channel 0 -> VN1640A Channel 1
   - Channel 1 -> VN1640A Channel 2
   - Channel 2 -> VN1640A Channel 3
   - Channel 3 -> VN1640A Channel 4
6. Kliknij OK i zapisz konfigurację

WAŻNE: Zamknij CANoe/CANalyzer przed użyciem tego skryptu!
""")
    
    # Szukaj Vector Hardware Config
    hw_config = find_vector_hw_config()
    
    if hw_config:
        print(f"Znaleziono Vector Hardware Config: {hw_config}")
        print("\nCzy chcesz otworzyć Vector Hardware Config? (t/n): ", end="")
        
        try:
            if input().lower() in ['t', 'y', 'tak', 'yes']:
                subprocess.Popen([hw_config])
                print("[OK] Uruchomiono Vector Hardware Config")
        except:
            pass
    else:
        print("Nie znaleziono Vector Hardware Config.")
        print("Otwórz go ręcznie z menu Start lub z katalogu instalacji Vector.")
    
    print("\n" + "=" * 60)
    print("  ALTERNATYWNA METODA (bez konfiguracji)")
    print("=" * 60)
    
    print("""
Jeśli nie chcesz konfigurować aplikacji, możesz użyć
biblioteki vxlapi64.dll bezpośrednio (vector_can_interface.py).

Ta metoda wymaga więcej kodu ale daje pełną kontrolę
nad sprzętem bez konieczności używania Vector Hardware Config.
""")


if __name__ == "__main__":
    main()
