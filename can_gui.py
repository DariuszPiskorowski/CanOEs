"""
CAN GUI - Graficzny interfejs dla VN1640A
Prosty interfejs do wysyłania/odbierania wiadomości CAN/CAN FD
z filtrami i kontrolą timingu.

Uruchomienie:
    py can_gui.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import queue
from datetime import datetime
from typing import List, Tuple, Optional, Set
from dataclasses import dataclass, field
from vn1640a_can import VN1640A, CANMsg, Baudrate

# =============================================================================
# Filtry wiadomości
# =============================================================================

@dataclass
class MessageFilter:
    """Filtr wiadomości CAN"""
    name: str
    filter_type: str  # 'single', 'range', 'mask'
    enabled: bool = True
    
    # Dla typu 'single'
    single_id: int = 0
    
    # Dla typu 'range'
    id_from: int = 0
    id_to: int = 0
    
    # Dla typu 'mask'
    base_id: int = 0
    mask: int = 0x7FF
    
    # Czy filtr akceptuje czy odrzuca
    accept: bool = True  # True = pokazuj tylko pasujące, False = ukryj pasujące
    
    def matches(self, msg_id: int) -> bool:
        """Sprawdza czy ID pasuje do filtra"""
        if self.filter_type == 'single':
            return msg_id == self.single_id
        elif self.filter_type == 'range':
            return self.id_from <= msg_id <= self.id_to
        elif self.filter_type == 'mask':
            return (msg_id & self.mask) == (self.base_id & self.mask)
        return False


@dataclass
class PeriodicMessage:
    """Wiadomość wysyłana cyklicznie"""
    msg_id: int
    data: bytes
    interval_ms: int  # Interwał w milisekundach
    extended: bool = False
    fd: bool = False
    brs: bool = False
    enabled: bool = True
    last_sent: float = 0
    count: int = 0  # Liczba wysłań (0 = nieskończenie)
    sent_count: int = 0


# =============================================================================
# Główna klasa GUI
# =============================================================================

class CANGui:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("VN1640A CAN Interface")
        self.root.geometry("1200x800")
        
        # CAN interface
        self.can: Optional[VN1640A] = None
        self.connected = False
        self.receiving = False
        self.receive_thread: Optional[threading.Thread] = None
        
        # Kolejka wiadomości do wyświetlenia
        self.msg_queue: queue.Queue = queue.Queue()
        
        # Filtry
        self.filters: List[MessageFilter] = []
        self.filter_mode = "pass_all"  # 'pass_all', 'accept_list', 'reject_list'
        
        # Wiadomości periodyczne
        self.periodic_messages: List[PeriodicMessage] = []
        self.periodic_thread: Optional[threading.Thread] = None
        self.periodic_running = False
        
        # Timing
        self.min_frame_gap_ms = 0  # Minimalne opóźnienie między ramkami
        self.last_send_time = 0
        
        # Statystyki
        self.tx_count = 0
        self.rx_count = 0
        self.error_count = 0
        
        # Tworzenie GUI
        self._create_gui()
        
        # Timer do aktualizacji GUI
        self._update_gui()
    
    def _create_gui(self):
        """Tworzy główny interfejs"""
        # Notebook z zakładkami
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Zakładka główna
        self.main_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.main_frame, text="Główne")
        
        # Zakładka filtrów
        self.filter_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.filter_frame, text="Filtry")
        
        # Zakładka wiadomości periodycznych
        self.periodic_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.periodic_frame, text="Periodyczne")
        
        # Zakładka ustawień
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Ustawienia")
        
        self._create_main_tab()
        self._create_filter_tab()
        self._create_periodic_tab()
        self._create_settings_tab()
        
        # Pasek statusu
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = ttk.Label(self.status_bar, text="Rozłączony")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        self.stats_label = ttk.Label(self.status_bar, text="TX: 0 | RX: 0 | Err: 0")
        self.stats_label.pack(side=tk.RIGHT, padx=5)
    
    def _create_main_tab(self):
        """Tworzy główną zakładkę"""
        # Panel połączenia
        conn_frame = ttk.LabelFrame(self.main_frame, text="Połączenie")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(conn_frame, text="Kanał:").pack(side=tk.LEFT, padx=5)
        self.channel_var = tk.StringVar(value="1")
        self.channel_combo = ttk.Combobox(conn_frame, textvariable=self.channel_var,
                                          values=["1", "2", "3", "4"], width=5)
        self.channel_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(conn_frame, text="Baudrate:").pack(side=tk.LEFT, padx=5)
        self.baudrate_var = tk.StringVar(value="500k")
        self.baudrate_combo = ttk.Combobox(conn_frame, textvariable=self.baudrate_var,
                                           values=["125k", "250k", "500k", "1M"], width=8)
        self.baudrate_combo.pack(side=tk.LEFT, padx=5)
        
        self.fd_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(conn_frame, text="CAN FD", variable=self.fd_var).pack(side=tk.LEFT, padx=5)
        
        self.connect_btn = ttk.Button(conn_frame, text="Połącz", command=self._toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, padx=10)
        
        # Panel wysyłania
        send_frame = ttk.LabelFrame(self.main_frame, text="Wysyłanie")
        send_frame.pack(fill=tk.X, padx=5, pady=5)
        
        row1 = ttk.Frame(send_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="ID (hex):").pack(side=tk.LEFT, padx=5)
        self.send_id_var = tk.StringVar(value="100")
        self.send_id_entry = ttk.Entry(row1, textvariable=self.send_id_var, width=10)
        self.send_id_entry.pack(side=tk.LEFT, padx=5)
        
        self.extended_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="Extended ID", variable=self.extended_var).pack(side=tk.LEFT, padx=5)
        
        self.send_fd_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="FD", variable=self.send_fd_var).pack(side=tk.LEFT, padx=5)
        
        self.brs_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="BRS", variable=self.brs_var).pack(side=tk.LEFT, padx=5)
        
        row2 = ttk.Frame(send_frame)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="Dane (hex):").pack(side=tk.LEFT, padx=5)
        self.send_data_var = tk.StringVar(value="01 02 03 04 05 06 07 08")
        self.send_data_entry = ttk.Entry(row2, textvariable=self.send_data_var, width=60)
        self.send_data_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.send_btn = ttk.Button(row2, text="Wyślij", command=self._send_message)
        self.send_btn.pack(side=tk.LEFT, padx=10)
        
        # Panel odbioru
        recv_frame = ttk.LabelFrame(self.main_frame, text="Odebrane wiadomości")
        recv_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Toolbar
        toolbar = ttk.Frame(recv_frame)
        toolbar.pack(fill=tk.X)
        
        self.receive_btn = ttk.Button(toolbar, text="▶ Start", command=self._toggle_receiving)
        self.receive_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(toolbar, text="Wyczyść", command=self._clear_messages).pack(side=tk.LEFT, padx=5)
        
        self.autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Auto-scroll", variable=self.autoscroll_var).pack(side=tk.LEFT, padx=5)
        
        self.show_time_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Pokaż czas", variable=self.show_time_var).pack(side=tk.LEFT, padx=5)
        
        # Lista wiadomości (Treeview)
        columns = ("time", "dir", "id", "dlc", "data", "flags")
        self.msg_tree = ttk.Treeview(recv_frame, columns=columns, show="headings", height=15)
        
        self.msg_tree.heading("time", text="Czas")
        self.msg_tree.heading("dir", text="Dir")
        self.msg_tree.heading("id", text="ID")
        self.msg_tree.heading("dlc", text="DLC")
        self.msg_tree.heading("data", text="Dane")
        self.msg_tree.heading("flags", text="Flagi")
        
        self.msg_tree.column("time", width=100)
        self.msg_tree.column("dir", width=40)
        self.msg_tree.column("id", width=100)
        self.msg_tree.column("dlc", width=40)
        self.msg_tree.column("data", width=400)
        self.msg_tree.column("flags", width=100)
        
        scrollbar = ttk.Scrollbar(recv_frame, orient=tk.VERTICAL, command=self.msg_tree.yview)
        self.msg_tree.configure(yscrollcommand=scrollbar.set)
        
        self.msg_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _create_filter_tab(self):
        """Tworzy zakładkę filtrów"""
        # Tryb filtrowania
        mode_frame = ttk.LabelFrame(self.filter_frame, text="Tryb filtrowania")
        mode_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.filter_mode_var = tk.StringVar(value="pass_all")
        ttk.Radiobutton(mode_frame, text="Przepuść wszystko", 
                       variable=self.filter_mode_var, value="pass_all").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="Tylko pasujące (whitelist)", 
                       variable=self.filter_mode_var, value="accept_list").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="Ukryj pasujące (blacklist)", 
                       variable=self.filter_mode_var, value="reject_list").pack(side=tk.LEFT, padx=10)
        
        # Dodawanie filtra
        add_frame = ttk.LabelFrame(self.filter_frame, text="Dodaj filtr")
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        row1 = ttk.Frame(add_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Nazwa:").pack(side=tk.LEFT, padx=5)
        self.filter_name_var = tk.StringVar(value="Filtr1")
        ttk.Entry(row1, textvariable=self.filter_name_var, width=15).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="Typ:").pack(side=tk.LEFT, padx=5)
        self.filter_type_var = tk.StringVar(value="single")
        filter_type_combo = ttk.Combobox(row1, textvariable=self.filter_type_var,
                                         values=["single", "range", "mask"], width=10)
        filter_type_combo.pack(side=tk.LEFT, padx=5)
        filter_type_combo.bind("<<ComboboxSelected>>", self._on_filter_type_change)
        
        # Parametry filtra
        self.filter_params_frame = ttk.Frame(add_frame)
        self.filter_params_frame.pack(fill=tk.X, pady=2)
        
        # Single ID
        self.single_frame = ttk.Frame(self.filter_params_frame)
        ttk.Label(self.single_frame, text="ID (hex):").pack(side=tk.LEFT, padx=5)
        self.filter_single_id_var = tk.StringVar(value="100")
        ttk.Entry(self.single_frame, textvariable=self.filter_single_id_var, width=10).pack(side=tk.LEFT, padx=5)
        self.single_frame.pack(fill=tk.X)
        
        # Range
        self.range_frame = ttk.Frame(self.filter_params_frame)
        ttk.Label(self.range_frame, text="Od (hex):").pack(side=tk.LEFT, padx=5)
        self.filter_from_var = tk.StringVar(value="100")
        ttk.Entry(self.range_frame, textvariable=self.filter_from_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(self.range_frame, text="Do (hex):").pack(side=tk.LEFT, padx=5)
        self.filter_to_var = tk.StringVar(value="200")
        ttk.Entry(self.range_frame, textvariable=self.filter_to_var, width=10).pack(side=tk.LEFT, padx=5)
        
        # Mask
        self.mask_frame = ttk.Frame(self.filter_params_frame)
        ttk.Label(self.mask_frame, text="Base ID (hex):").pack(side=tk.LEFT, padx=5)
        self.filter_base_var = tk.StringVar(value="100")
        ttk.Entry(self.mask_frame, textvariable=self.filter_base_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(self.mask_frame, text="Maska (hex):").pack(side=tk.LEFT, padx=5)
        self.filter_mask_var = tk.StringVar(value="7F0")
        ttk.Entry(self.mask_frame, textvariable=self.filter_mask_var, width=10).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(add_frame, text="Dodaj filtr", command=self._add_filter).pack(pady=5)
        
        # Lista filtrów
        list_frame = ttk.LabelFrame(self.filter_frame, text="Aktywne filtry")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ("name", "type", "params", "enabled")
        self.filter_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        self.filter_tree.heading("name", text="Nazwa")
        self.filter_tree.heading("type", text="Typ")
        self.filter_tree.heading("params", text="Parametry")
        self.filter_tree.heading("enabled", text="Aktywny")
        
        self.filter_tree.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="Włącz/Wyłącz", command=self._toggle_filter).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Usuń", command=self._remove_filter).pack(side=tk.LEFT, padx=5)
    
    def _create_periodic_tab(self):
        """Tworzy zakładkę wiadomości periodycznych"""
        # Dodawanie
        add_frame = ttk.LabelFrame(self.periodic_frame, text="Dodaj wiadomość periodyczną")
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        row1 = ttk.Frame(add_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="ID (hex):").pack(side=tk.LEFT, padx=5)
        self.periodic_id_var = tk.StringVar(value="100")
        ttk.Entry(row1, textvariable=self.periodic_id_var, width=10).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="Interwał (ms):").pack(side=tk.LEFT, padx=5)
        self.periodic_interval_var = tk.StringVar(value="100")
        ttk.Entry(row1, textvariable=self.periodic_interval_var, width=8).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="Liczba (0=∞):").pack(side=tk.LEFT, padx=5)
        self.periodic_count_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.periodic_count_var, width=6).pack(side=tk.LEFT, padx=5)
        
        row2 = ttk.Frame(add_frame)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="Dane (hex):").pack(side=tk.LEFT, padx=5)
        self.periodic_data_var = tk.StringVar(value="01 02 03 04 05 06 07 08")
        ttk.Entry(row2, textvariable=self.periodic_data_var, width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        row3 = ttk.Frame(add_frame)
        row3.pack(fill=tk.X, pady=2)
        
        self.periodic_extended_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="Extended ID", variable=self.periodic_extended_var).pack(side=tk.LEFT, padx=5)
        
        self.periodic_fd_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="FD", variable=self.periodic_fd_var).pack(side=tk.LEFT, padx=5)
        
        self.periodic_brs_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="BRS", variable=self.periodic_brs_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(row3, text="Dodaj", command=self._add_periodic).pack(side=tk.LEFT, padx=10)
        
        # Lista
        list_frame = ttk.LabelFrame(self.periodic_frame, text="Wiadomości periodyczne")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ("id", "interval", "data", "count", "sent", "enabled")
        self.periodic_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        self.periodic_tree.heading("id", text="ID")
        self.periodic_tree.heading("interval", text="Interwał (ms)")
        self.periodic_tree.heading("data", text="Dane")
        self.periodic_tree.heading("count", text="Limit")
        self.periodic_tree.heading("sent", text="Wysłano")
        self.periodic_tree.heading("enabled", text="Aktywny")
        
        self.periodic_tree.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X)
        
        self.periodic_start_btn = ttk.Button(btn_frame, text="▶ Start wysyłania", 
                                             command=self._toggle_periodic)
        self.periodic_start_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Włącz/Wyłącz", command=self._toggle_periodic_msg).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Usuń", command=self._remove_periodic).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Reset liczników", command=self._reset_periodic_counters).pack(side=tk.LEFT, padx=5)
    
    def _create_settings_tab(self):
        """Tworzy zakładkę ustawień"""
        timing_frame = ttk.LabelFrame(self.settings_frame, text="Timing")
        timing_frame.pack(fill=tk.X, padx=5, pady=5)
        
        row1 = ttk.Frame(timing_frame)
        row1.pack(fill=tk.X, pady=5)
        
        ttk.Label(row1, text="Min. przerwa między ramkami (ms):").pack(side=tk.LEFT, padx=5)
        self.frame_gap_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.frame_gap_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text="Zastosuj", command=self._apply_timing).pack(side=tk.LEFT, padx=10)
        
        info_frame = ttk.LabelFrame(self.settings_frame, text="Informacje o timingu CAN")
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        info_text = """
Timing między ramkami CAN:

1. Minimalna przerwa (Interframe Space - IFS):
   - CAN wymaga minimum 3 bity przerwy między ramkami
   - Dla 500 kbit/s: 3 * 2µs = 6µs
   - Dla 1 Mbit/s: 3 * 1µs = 3µs

2. Przepustowość teoretyczna:
   - Przy 500 kbit/s i 8 bajtów danych (~100 bitów/ramka):
     Max ~5000 ramek/s
   
3. Praktyczne opóźnienia:
   - Software overhead: 0.1-1 ms
   - USB latency: 1-5 ms
   - Zalecane min. gap: 1-5 ms dla stabilności

4. Tryby wysyłania:
   - Natychmiastowe: bez dodatkowego opóźnienia
   - Z minimalnym gap: opóźnienie między ramkami
   - Periodyczne: stały interwał czasowy
        """
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(padx=5, pady=5)
    
    def _on_filter_type_change(self, event=None):
        """Zmiana typu filtra"""
        filter_type = self.filter_type_var.get()
        
        self.single_frame.pack_forget()
        self.range_frame.pack_forget()
        self.mask_frame.pack_forget()
        
        if filter_type == "single":
            self.single_frame.pack(fill=tk.X)
        elif filter_type == "range":
            self.range_frame.pack(fill=tk.X)
        elif filter_type == "mask":
            self.mask_frame.pack(fill=tk.X)
    
    # =========================================================================
    # Obsługa połączenia
    # =========================================================================
    
    def _toggle_connection(self):
        """Przełącza połączenie"""
        if self.connected:
            self._disconnect()
        else:
            self._connect()
    
    def _connect(self):
        """Łączy z urządzeniem"""
        try:
            channel = int(self.channel_var.get())
            baudrate_str = self.baudrate_var.get()
            use_fd = self.fd_var.get()
            
            # Mapowanie baudrate
            baudrate_map = {
                "125k": Baudrate.BAUD_125K,
                "250k": Baudrate.BAUD_250K,
                "500k": Baudrate.BAUD_500K,
                "1M": Baudrate.BAUD_1M
            }
            baudrate = baudrate_map.get(baudrate_str, Baudrate.BAUD_500K)
            
            # Utwórz instancję VN1640A z baudrate
            from vn1640a_can import BaudrateFD
            self.can = VN1640A(baudrate=baudrate, baudrate_fd=BaudrateFD.BAUD_2M)
            
            # Otwórz sterownik
            if not self.can.open():
                messagebox.showerror("Błąd", "Nie udało się otworzyć sterownika Vector")
                self.can = None
                return
            
            # Uruchom kanał
            if use_fd:
                success = self.can.start_fd(channel=channel)
            else:
                success = self.can.start(channel=channel)
            
            if success:
                self.connected = True
                self.connect_btn.config(text="Rozłącz")
                self.status_label.config(text=f"Połączony: Kanał {channel}, {baudrate_str}")
                self.channel_combo.config(state="disabled")
                self.baudrate_combo.config(state="disabled")
            else:
                messagebox.showerror("Błąd", "Nie udało się połączyć z urządzeniem")
                self.can = None
                
        except Exception as e:
            messagebox.showerror("Błąd", f"Błąd połączenia: {e}")
            self.can = None
    
    def _disconnect(self):
        """Rozłącza"""
        if self.receiving:
            self._toggle_receiving()
        
        if self.periodic_running:
            self._toggle_periodic()
        
        if self.can:
            self.can.stop()
            self.can.close()
            self.can = None
        
        self.connected = False
        self.connect_btn.config(text="Połącz")
        self.status_label.config(text="Rozłączony")
        self.channel_combo.config(state="normal")
        self.baudrate_combo.config(state="normal")
    
    # =========================================================================
    # Wysyłanie wiadomości
    # =========================================================================
    
    def _send_message(self):
        """Wysyła wiadomość"""
        if not self.connected:
            messagebox.showwarning("Uwaga", "Najpierw połącz się z urządzeniem")
            return
        
        try:
            # Parsowanie ID
            msg_id = int(self.send_id_var.get(), 16)
            extended = self.extended_var.get()
            use_fd = self.send_fd_var.get()
            brs = self.brs_var.get()
            
            # Parsowanie danych
            data_str = self.send_data_var.get().strip()
            data_bytes = bytes.fromhex(data_str.replace(" ", ""))
            
            print(f"[GUI DEBUG] Wysyłanie: ID=0x{msg_id:X}, data={data_bytes.hex()}, extended={extended}, fd={use_fd}, brs={brs}")
            print(f"[GUI DEBUG] self.can = {self.can}")
            print(f"[GUI DEBUG] self.can.is_on_bus = {self.can.is_on_bus if self.can else 'N/A'}")
            
            # Sprawdzenie timingu
            if self.min_frame_gap_ms > 0:
                elapsed = (time.time() - self.last_send_time) * 1000
                if elapsed < self.min_frame_gap_ms:
                    time.sleep((self.min_frame_gap_ms - elapsed) / 1000)
            
            # Wysłanie
            if use_fd:
                print("[GUI DEBUG] Wywołuję send_fd()...")
                success = self.can.send_fd(msg_id, data_bytes, extended=extended, brs=brs)
            else:
                print("[GUI DEBUG] Wywołuję send()...")
                success = self.can.send(msg_id, data_bytes, extended=extended)
            
            print(f"[GUI DEBUG] Wynik wysyłania: {success}")
            
            self.last_send_time = time.time()
            
            if success:
                self.tx_count += 1
                # Dodaj do listy
                self._add_message_to_tree("TX", msg_id, data_bytes, extended, use_fd, brs)
            else:
                self.error_count += 1
                messagebox.showerror("Błąd", "Nie udało się wysłać wiadomości")
                
        except Exception as e:
            print(f"[GUI DEBUG] Wyjątek: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Błąd", f"Błąd: {e}")
    
    def _add_message_to_tree(self, direction: str, msg_id: int, data: bytes, 
                            extended: bool = False, fd: bool = False, brs: bool = False):
        """Dodaje wiadomość do drzewa"""
        if self.show_time_var.get():
            time_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        else:
            time_str = ""
        
        if extended:
            id_str = f"0x{msg_id:08X}"
        else:
            id_str = f"0x{msg_id:03X}"
        
        data_str = " ".join(f"{b:02X}" for b in data)
        dlc = len(data)
        
        flags = []
        if extended:
            flags.append("EXT")
        if fd:
            flags.append("FD")
        if brs:
            flags.append("BRS")
        flags_str = " ".join(flags)
        
        self.msg_tree.insert("", tk.END, values=(time_str, direction, id_str, dlc, data_str, flags_str))
        
        if self.autoscroll_var.get():
            self.msg_tree.yview_moveto(1)
        
        # Limit wiadomości (żeby nie zapychać pamięci)
        children = self.msg_tree.get_children()
        if len(children) > 1000:
            self.msg_tree.delete(children[0])
    
    # =========================================================================
    # Odbieranie wiadomości
    # =========================================================================
    
    def _toggle_receiving(self):
        """Przełącza odbieranie"""
        if self.receiving:
            self.receiving = False
            self.receive_btn.config(text="▶ Start")
        else:
            if not self.connected:
                messagebox.showwarning("Uwaga", "Najpierw połącz się z urządzeniem")
                return
            
            self.receiving = True
            self.receive_btn.config(text="⏹ Stop")
            
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
    
    def _receive_loop(self):
        """Pętla odbierania"""
        print("[GUI] Rozpoczęto odbieranie...")
        while self.receiving and self.can:
            try:
                msg = self.can.receive(timeout_ms=100)
                if msg:
                    print(f"[GUI] Odebrano: ID=0x{msg.id:X}, DLC={msg.dlc}")
                    # Sprawdź filtry
                    if self._should_show_message(msg.id):
                        self.msg_queue.put(msg)
                        self.rx_count += 1
            except Exception as e:
                print(f"[GUI] Błąd odbierania: {e}")
                self.error_count += 1
        print("[GUI] Zatrzymano odbieranie")
    
    def _should_show_message(self, msg_id: int) -> bool:
        """Sprawdza czy wiadomość powinna być wyświetlona (na podstawie filtrów)"""
        mode = self.filter_mode_var.get()
        
        if mode == "pass_all":
            return True
        
        # Sprawdź czy którykolwiek aktywny filtr pasuje
        any_match = False
        for f in self.filters:
            if f.enabled and f.matches(msg_id):
                any_match = True
                break
        
        if mode == "accept_list":
            return any_match  # Pokazuj tylko pasujące
        elif mode == "reject_list":
            return not any_match  # Ukryj pasujące
        
        return True
    
    def _clear_messages(self):
        """Czyści listę wiadomości"""
        for item in self.msg_tree.get_children():
            self.msg_tree.delete(item)
    
    # =========================================================================
    # Filtry
    # =========================================================================
    
    def _add_filter(self):
        """Dodaje nowy filtr"""
        try:
            name = self.filter_name_var.get()
            filter_type = self.filter_type_var.get()
            
            f = MessageFilter(name=name, filter_type=filter_type)
            
            if filter_type == "single":
                f.single_id = int(self.filter_single_id_var.get(), 16)
                params = f"ID: 0x{f.single_id:X}"
            elif filter_type == "range":
                f.id_from = int(self.filter_from_var.get(), 16)
                f.id_to = int(self.filter_to_var.get(), 16)
                params = f"0x{f.id_from:X} - 0x{f.id_to:X}"
            elif filter_type == "mask":
                f.base_id = int(self.filter_base_var.get(), 16)
                f.mask = int(self.filter_mask_var.get(), 16)
                params = f"Base: 0x{f.base_id:X}, Mask: 0x{f.mask:X}"
            
            self.filters.append(f)
            self.filter_tree.insert("", tk.END, values=(name, filter_type, params, "Tak"))
            
        except ValueError as e:
            messagebox.showerror("Błąd", f"Nieprawidłowe wartości: {e}")
    
    def _toggle_filter(self):
        """Włącza/wyłącza wybrany filtr"""
        selection = self.filter_tree.selection()
        if not selection:
            return
        
        idx = self.filter_tree.index(selection[0])
        if 0 <= idx < len(self.filters):
            self.filters[idx].enabled = not self.filters[idx].enabled
            enabled_str = "Tak" if self.filters[idx].enabled else "Nie"
            values = list(self.filter_tree.item(selection[0])["values"])
            values[3] = enabled_str
            self.filter_tree.item(selection[0], values=values)
    
    def _remove_filter(self):
        """Usuwa wybrany filtr"""
        selection = self.filter_tree.selection()
        if not selection:
            return
        
        idx = self.filter_tree.index(selection[0])
        if 0 <= idx < len(self.filters):
            del self.filters[idx]
            self.filter_tree.delete(selection[0])
    
    # =========================================================================
    # Wiadomości periodyczne
    # =========================================================================
    
    def _add_periodic(self):
        """Dodaje wiadomość periodyczną"""
        try:
            msg_id = int(self.periodic_id_var.get(), 16)
            interval = int(self.periodic_interval_var.get())
            count = int(self.periodic_count_var.get())
            
            data_str = self.periodic_data_var.get().strip()
            data = bytes.fromhex(data_str.replace(" ", ""))
            
            pm = PeriodicMessage(
                msg_id=msg_id,
                data=data,
                interval_ms=interval,
                extended=self.periodic_extended_var.get(),
                fd=self.periodic_fd_var.get(),
                brs=self.periodic_brs_var.get(),
                count=count
            )
            
            self.periodic_messages.append(pm)
            
            id_str = f"0x{msg_id:08X}" if pm.extended else f"0x{msg_id:03X}"
            data_str = " ".join(f"{b:02X}" for b in data)
            count_str = str(count) if count > 0 else "∞"
            
            self.periodic_tree.insert("", tk.END, 
                                      values=(id_str, interval, data_str, count_str, 0, "Tak"))
            
        except ValueError as e:
            messagebox.showerror("Błąd", f"Nieprawidłowe wartości: {e}")
    
    def _toggle_periodic(self):
        """Przełącza wysyłanie periodyczne"""
        if self.periodic_running:
            self.periodic_running = False
            self.periodic_start_btn.config(text="▶ Start wysyłania")
        else:
            if not self.connected:
                messagebox.showwarning("Uwaga", "Najpierw połącz się z urządzeniem")
                return
            
            if not self.periodic_messages:
                messagebox.showwarning("Uwaga", "Dodaj najpierw wiadomości periodyczne")
                return
            
            self.periodic_running = True
            self.periodic_start_btn.config(text="⏹ Stop wysyłania")
            
            self.periodic_thread = threading.Thread(target=self._periodic_loop, daemon=True)
            self.periodic_thread.start()
    
    def _periodic_loop(self):
        """Pętla wysyłania periodycznego"""
        while self.periodic_running and self.can:
            current_time = time.time() * 1000  # ms
            
            for i, pm in enumerate(self.periodic_messages):
                if not pm.enabled:
                    continue
                
                # Sprawdź limit
                if pm.count > 0 and pm.sent_count >= pm.count:
                    continue
                
                # Sprawdź czy czas wysłać
                if current_time - pm.last_sent >= pm.interval_ms:
                    try:
                        if pm.fd:
                            success = self.can.send_fd(pm.msg_id, pm.data, 
                                                       extended=pm.extended, brs=pm.brs)
                        else:
                            success = self.can.send(pm.msg_id, pm.data, extended=pm.extended)
                        
                        if success:
                            pm.last_sent = current_time
                            pm.sent_count += 1
                            self.tx_count += 1
                            
                            # Aktualizacja GUI (przez kolejkę)
                            self.msg_queue.put(("periodic_update", i, pm.sent_count))
                        else:
                            self.error_count += 1
                            
                    except Exception as e:
                        self.error_count += 1
            
            # Krótkie oczekiwanie żeby nie obciążać CPU
            time.sleep(0.001)  # 1ms
    
    def _toggle_periodic_msg(self):
        """Włącza/wyłącza wybraną wiadomość periodyczną"""
        selection = self.periodic_tree.selection()
        if not selection:
            return
        
        idx = self.periodic_tree.index(selection[0])
        if 0 <= idx < len(self.periodic_messages):
            self.periodic_messages[idx].enabled = not self.periodic_messages[idx].enabled
            enabled_str = "Tak" if self.periodic_messages[idx].enabled else "Nie"
            values = list(self.periodic_tree.item(selection[0])["values"])
            values[5] = enabled_str
            self.periodic_tree.item(selection[0], values=values)
    
    def _remove_periodic(self):
        """Usuwa wybraną wiadomość periodyczną"""
        selection = self.periodic_tree.selection()
        if not selection:
            return
        
        idx = self.periodic_tree.index(selection[0])
        if 0 <= idx < len(self.periodic_messages):
            del self.periodic_messages[idx]
            self.periodic_tree.delete(selection[0])
    
    def _reset_periodic_counters(self):
        """Resetuje liczniki wysyłań"""
        for pm in self.periodic_messages:
            pm.sent_count = 0
            pm.last_sent = 0
        self._refresh_periodic_tree()
    
    def _refresh_periodic_tree(self):
        """Odświeża drzewo wiadomości periodycznych"""
        for i, item in enumerate(self.periodic_tree.get_children()):
            if i < len(self.periodic_messages):
                pm = self.periodic_messages[i]
                values = list(self.periodic_tree.item(item)["values"])
                values[4] = pm.sent_count
                self.periodic_tree.item(item, values=values)
    
    # =========================================================================
    # Timing
    # =========================================================================
    
    def _apply_timing(self):
        """Zastosowuje ustawienia timingu"""
        try:
            self.min_frame_gap_ms = float(self.frame_gap_var.get())
            messagebox.showinfo("Info", f"Ustawiono minimalną przerwę: {self.min_frame_gap_ms} ms")
        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowa wartość")
    
    # =========================================================================
    # Aktualizacja GUI
    # =========================================================================
    
    def _update_gui(self):
        """Aktualizuje GUI (wywoływane co 50ms)"""
        # Przetwórz wiadomości z kolejki
        try:
            while True:
                item = self.msg_queue.get_nowait()
                
                if isinstance(item, tuple) and item[0] == "periodic_update":
                    # Aktualizacja licznika periodycznego
                    _, idx, count = item
                    children = list(self.periodic_tree.get_children())
                    if idx < len(children):
                        values = list(self.periodic_tree.item(children[idx])["values"])
                        values[4] = count
                        self.periodic_tree.item(children[idx], values=values)
                elif isinstance(item, CANMsg):
                    # Wiadomość odebrana
                    self._add_message_to_tree("RX", item.id, item.data, 
                                             item.is_extended, item.is_fd, item.is_brs)
        except queue.Empty:
            pass
        
        # Aktualizacja statystyk
        self.stats_label.config(text=f"TX: {self.tx_count} | RX: {self.rx_count} | Err: {self.error_count}")
        
        # Zaplanuj kolejne wywołanie
        self.root.after(50, self._update_gui)
    
    def on_close(self):
        """Zamykanie aplikacji"""
        self._disconnect()
        self.root.destroy()


# =============================================================================
# Main
# =============================================================================

def main():
    root = tk.Tk()
    app = CANGui(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
