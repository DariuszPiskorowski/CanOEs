"""
CAN GUI - Graphical interface for VN1640A
Simple interface for sending/receiving CAN/CAN FD messages
with filters and timing control.

Usage:
    py can_gui.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import time
import queue
from datetime import datetime
from typing import List, Tuple, Optional, Set, Dict
from dataclasses import dataclass, field
from vn1640a_can import VN1640A, CANMsg, Baudrate

# =============================================================================
# Message Filters
# =============================================================================

@dataclass
class MessageFilter:
    """CAN message filter"""
    name: str
    filter_type: str  # 'single', 'range', 'mask'
    enabled: bool = True
    
    # For 'single' type
    single_id: int = 0
    
    # For 'range' type
    id_from: int = 0
    id_to: int = 0
    
    # For 'mask' type
    base_id: int = 0
    mask: int = 0x7FF
    
    # Whether filter accepts or rejects
    accept: bool = True  # True = show only matching, False = hide matching
    
    def matches(self, msg_id: int) -> bool:
        """Checks if ID matches the filter"""
        if self.filter_type == 'single':
            return msg_id == self.single_id
        elif self.filter_type == 'range':
            return self.id_from <= msg_id <= self.id_to
        elif self.filter_type == 'mask':
            return (msg_id & self.mask) == (self.base_id & self.mask)
        return False


@dataclass
class PeriodicMessage:
    """Periodically sent message"""
    msg_id: int
    data: bytes
    interval_ms: int  # Interval in milliseconds
    extended: bool = False
    fd: bool = False
    brs: bool = False
    enabled: bool = True
    last_sent: float = 0
    count: int = 0  # Number of sends (0 = infinite)
    sent_count: int = 0


# =============================================================================
# Dark Theme Colors
# =============================================================================

DARK_THEME = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
    "select_bg": "#094771",
    "select_fg": "#ffffff",
    "button_bg": "#3c3c3c",
    "entry_bg": "#2d2d2d",
    "frame_bg": "#252526",
    "treeview_bg": "#1e1e1e",
    "treeview_fg": "#d4d4d4",
    "heading_bg": "#3c3c3c",
}

LIGHT_THEME = {
    "bg": "#f0f0f0",
    "fg": "#000000",
    "select_bg": "#0078d7",
    "select_fg": "#ffffff",
    "button_bg": "#e1e1e1",
    "entry_bg": "#ffffff",
    "frame_bg": "#f5f5f5",
    "treeview_bg": "#ffffff",
    "treeview_fg": "#000000",
    "heading_bg": "#e1e1e1",
}


# =============================================================================
# Main GUI Class
# =============================================================================

class CANGui:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("VN1640A CAN Interface")
        self.root.geometry("1200x800")
        
        # Theme
        self.dark_mode = False
        self.current_theme = LIGHT_THEME
        
        # CAN interface
        self.can: Optional[VN1640A] = None
        self.connected = False
        self.receiving = False
        self.receive_thread: Optional[threading.Thread] = None
        
        # Message queue for display
        self.msg_queue: queue.Queue = queue.Queue()
        
        # Filters
        self.filters: List[MessageFilter] = []
        self.filter_mode = "pass_all"  # 'pass_all', 'accept_list', 'reject_list'
        
        # Periodic messages
        self.periodic_messages: List[PeriodicMessage] = []
        self.periodic_thread: Optional[threading.Thread] = None
        self.periodic_running = False
        
        # Timing
        self.min_frame_gap_ms = 0  # Minimum delay between frames
        self.last_send_time = 0
        
        # Statistics
        self.tx_count = 0
        self.rx_count = 0
        self.error_count = 0
        
        # ID Comments (user-defined descriptions for known CAN IDs)
        self.id_comments: Dict[int, str] = {
            0x744: "Diagnostic Request (ECU)",
            0x74C: "Diagnostic Response (ECU)",
            0x7DF: "OBD-II Broadcast Request",
            0x7E0: "OBD-II ECU Request",
            0x7E8: "OBD-II ECU Response",
            0x700: "NMT Node 0",
            0x000: "NMT Master",
        }
        
        # Send history (list of recently sent messages)
        self.send_history: List[Dict] = []
        self.max_history = 20
        
        # Predefined messages
        self.predefined_messages: List[Dict] = [
            {"name": "OBD-II Request RPM", "id": 0x7DF, "data": "02 01 0C 00 00 00 00 00", "extended": False, "fd": False, "brs": False},
            {"name": "OBD-II Request Speed", "id": 0x7DF, "data": "02 01 0D 00 00 00 00 00", "extended": False, "fd": False, "brs": False},
            {"name": "OBD-II Request Coolant Temp", "id": 0x7DF, "data": "02 01 05 00 00 00 00 00", "extended": False, "fd": False, "brs": False},
            {"name": "Diag Session Control", "id": 0x744, "data": "02 10 01 00 00 00 00 00", "extended": False, "fd": False, "brs": False},
            {"name": "Diag Read DTC", "id": 0x744, "data": "03 19 02 FF 00 00 00 00", "extended": False, "fd": False, "brs": False},
            {"name": "Tester Present", "id": 0x744, "data": "02 3E 00 00 00 00 00 00", "extended": False, "fd": False, "brs": False},
        ]
        
        # Grouped messages by ID (for statistics)
        self.grouped_messages: Dict[int, Dict] = {}  # id -> {count, last_data, last_time, comment}
        
        # Message repetition tracking (for fading repeated messages)
        # id -> {"last_data": str, "repeat_count": int}
        self.message_repeat_tracker: Dict[int, Dict] = {}
        self.stale_threshold = 5  # After this many identical repeats, message fades
        
        # Create GUI
        self._create_gui()
        
        # Timer for GUI updates
        self._update_gui()
    
    def _create_gui(self):
        """Creates the main interface"""
        # Top toolbar with theme toggle
        top_bar = ttk.Frame(self.root)
        top_bar.pack(fill=tk.X, padx=5, pady=2)
        
        self.theme_btn = ttk.Button(top_bar, text="🌙 Dark Mode", command=self._toggle_theme)
        self.theme_btn.pack(side=tk.RIGHT, padx=5)
        
        # Notebook with tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Main tab
        self.main_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.main_frame, text="Main")
        
        # Grouped view tab
        self.grouped_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.grouped_frame, text="Grouped")
        
        # History tab
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="History")
        
        # Predefined tab
        self.predefined_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.predefined_frame, text="Predefined")
        
        # Filters tab
        self.filter_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.filter_frame, text="Filters")
        
        # Periodic messages tab
        self.periodic_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.periodic_frame, text="Periodic")
        
        # Settings tab
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings")
        
        self._create_main_tab()
        self._create_grouped_tab()
        self._create_history_tab()
        self._create_predefined_tab()
        self._create_filter_tab()
        self._create_periodic_tab()
        self._create_settings_tab()
        
        # Status bar
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = ttk.Label(self.status_bar, text="Disconnected")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Author credit (small font at bottom)
        author_label = ttk.Label(self.status_bar, text="© Dariusz Piskorowski | 7344219@gmail.com", 
                                  font=("Segoe UI", 7))
        author_label.pack(side=tk.LEFT, padx=20)
        
        self.stats_label = ttk.Label(self.status_bar, text="TX: 0 | RX: 0 | Err: 0")
        self.stats_label.pack(side=tk.RIGHT, padx=5)
    
    def _create_main_tab(self):
        """Creates the main tab"""
        # Connection panel
        conn_frame = ttk.LabelFrame(self.main_frame, text="Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(conn_frame, text="Channel:").pack(side=tk.LEFT, padx=5)
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
        
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self._toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, padx=10)
        
        # Send panel
        send_frame = ttk.LabelFrame(self.main_frame, text="Send")
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
        self.send_fd_var.trace_add("write", self._on_fd_mode_changed)
        ttk.Checkbutton(row1, text="FD", variable=self.send_fd_var).pack(side=tk.LEFT, padx=5)
        
        self.brs_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="BRS", variable=self.brs_var).pack(side=tk.LEFT, padx=5)
        
        row2 = ttk.Frame(send_frame)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="Data (hex):").pack(side=tk.LEFT, padx=5)
        self.send_data_var = tk.StringVar(value="01 02 03 04 05 06 07 08")
        self.send_data_var.trace_add("write", self._on_data_changed)
        self.send_data_entry = ttk.Entry(row2, textvariable=self.send_data_var, width=60)
        self.send_data_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Byte counter label
        self.byte_count_var = tk.StringVar(value="8/8 bytes")
        self.byte_count_label = ttk.Label(row2, textvariable=self.byte_count_var, width=12)
        self.byte_count_label.pack(side=tk.LEFT, padx=2)
        
        # Pad with zeros button (useful for CAN FD)
        self.pad_zeros_btn = ttk.Button(row2, text="Pad 00", command=self._pad_with_zeros, width=7)
        self.pad_zeros_btn.pack(side=tk.LEFT, padx=2)
        
        self.send_btn = ttk.Button(row2, text="Send", command=self._send_message)
        self.send_btn.pack(side=tk.LEFT, padx=10)
        
        # Receive panel
        recv_frame = ttk.LabelFrame(self.main_frame, text="Received Messages")
        recv_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Toolbar
        toolbar = ttk.Frame(recv_frame)
        toolbar.pack(fill=tk.X)
        
        self.receive_btn = ttk.Button(toolbar, text="▶ Start", command=self._toggle_receiving)
        self.receive_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(toolbar, text="Clear", command=self._clear_messages).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Export TXT", command=self._export_log).pack(side=tk.LEFT, padx=5)
        
        self.autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Auto-scroll", variable=self.autoscroll_var).pack(side=tk.LEFT, padx=5)
        
        self.show_time_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Show Time", variable=self.show_time_var).pack(side=tk.LEFT, padx=5)
        
        self.show_ascii_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="Show ASCII", variable=self.show_ascii_var).pack(side=tk.LEFT, padx=5)
        
        self.color_messages_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Color Messages", variable=self.color_messages_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(toolbar, text="Edit Comments", command=self._edit_comments).pack(side=tk.LEFT, padx=5)
        
        # Message list (Treeview)
        columns = ("time", "dir", "id", "dlc", "data", "ascii", "flags", "comment")
        self.msg_tree = ttk.Treeview(recv_frame, columns=columns, show="headings", height=15)
        
        self.msg_tree.heading("time", text="Time")
        self.msg_tree.heading("dir", text="Dir")
        self.msg_tree.heading("id", text="ID")
        self.msg_tree.heading("dlc", text="DLC")
        self.msg_tree.heading("data", text="Data")
        self.msg_tree.heading("ascii", text="ASCII")
        self.msg_tree.heading("flags", text="Flags")
        self.msg_tree.heading("comment", text="Comment")
        
        self.msg_tree.column("time", width=100)
        self.msg_tree.column("dir", width=40)
        self.msg_tree.column("id", width=80)
        self.msg_tree.column("dlc", width=40)
        self.msg_tree.column("data", width=250)
        self.msg_tree.column("ascii", width=80)
        self.msg_tree.column("flags", width=70)
        self.msg_tree.column("comment", width=150)
        
        # Configure tags for row coloring
        self.msg_tree.tag_configure("TX", foreground="#2ecc71")  # Green for TX
        self.msg_tree.tag_configure("RX", foreground="#3498db")  # Blue for RX
        self.msg_tree.tag_configure("ERR", foreground="#e74c3c")  # Red for errors
        self.msg_tree.tag_configure("DIAG", foreground="#f39c12")  # Orange for diagnostic IDs
        # Faded/stale tags for repeated messages without data changes
        self.msg_tree.tag_configure("TX_STALE", foreground="#7f9f7f")  # Faded green
        self.msg_tree.tag_configure("RX_STALE", foreground="#7f9faf")  # Faded blue
        self.msg_tree.tag_configure("DIAG_STALE", foreground="#9f8f6f")  # Faded orange
        
        scrollbar = ttk.Scrollbar(recv_frame, orient=tk.VERTICAL, command=self.msg_tree.yview)
        self.msg_tree.configure(yscrollcommand=scrollbar.set)
        
        self.msg_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _create_grouped_tab(self):
        """Creates the grouped view tab (messages grouped by ID)"""
        info_label = ttk.Label(self.grouped_frame, text="Messages grouped by ID (shows count, last data, and timing statistics):")
        info_label.pack(pady=5)
        
        # Toolbar
        toolbar = ttk.Frame(self.grouped_frame)
        toolbar.pack(fill=tk.X)
        
        ttk.Button(toolbar, text="Refresh", command=self._refresh_grouped).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Clear Statistics", command=self._clear_grouped).pack(side=tk.LEFT, padx=5)
        
        # Grouped list
        columns = ("id", "count", "last_data", "last_time", "comment")
        self.grouped_tree = ttk.Treeview(self.grouped_frame, columns=columns, show="headings", height=15)
        
        self.grouped_tree.heading("id", text="ID")
        self.grouped_tree.heading("count", text="Count")
        self.grouped_tree.heading("last_data", text="Last Data")
        self.grouped_tree.heading("last_time", text="Last Time")
        self.grouped_tree.heading("comment", text="Comment")
        
        self.grouped_tree.column("id", width=100)
        self.grouped_tree.column("count", width=80)
        self.grouped_tree.column("last_data", width=300)
        self.grouped_tree.column("last_time", width=100)
        self.grouped_tree.column("comment", width=200)
        
        # Configure tags for coloring
        self.grouped_tree.tag_configure("DIAG", foreground="#f39c12")
        
        scrollbar = ttk.Scrollbar(self.grouped_frame, orient=tk.VERTICAL, command=self.grouped_tree.yview)
        self.grouped_tree.configure(yscrollcommand=scrollbar.set)
        
        self.grouped_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
    
    def _create_history_tab(self):
        """Creates the history tab"""
        info_label = ttk.Label(self.history_frame, text="Recently sent messages (double-click to resend):")
        info_label.pack(pady=5)
        
        # History list
        columns = ("time", "id", "data", "flags")
        self.history_tree = ttk.Treeview(self.history_frame, columns=columns, show="headings", height=15)
        
        self.history_tree.heading("time", text="Time")
        self.history_tree.heading("id", text="ID")
        self.history_tree.heading("data", text="Data")
        self.history_tree.heading("flags", text="Flags")
        
        self.history_tree.column("time", width=100)
        self.history_tree.column("id", width=100)
        self.history_tree.column("data", width=400)
        self.history_tree.column("flags", width=100)
        
        scrollbar = ttk.Scrollbar(self.history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # Double-click to resend
        self.history_tree.bind("<Double-1>", self._resend_from_history)
        
        # Buttons
        btn_frame = ttk.Frame(self.history_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Resend Selected", command=self._resend_from_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear History", command=self._clear_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Load to Send", command=self._load_from_history).pack(side=tk.LEFT, padx=5)
    
    def _create_predefined_tab(self):
        """Creates the predefined messages tab"""
        info_label = ttk.Label(self.predefined_frame, text="Predefined diagnostic and test messages (double-click to send):")
        info_label.pack(pady=5)
        
        # Predefined list
        columns = ("name", "id", "data", "flags")
        self.predefined_tree = ttk.Treeview(self.predefined_frame, columns=columns, show="headings", height=10)
        
        self.predefined_tree.heading("name", text="Name")
        self.predefined_tree.heading("id", text="ID")
        self.predefined_tree.heading("data", text="Data")
        self.predefined_tree.heading("flags", text="Flags")
        
        self.predefined_tree.column("name", width=200)
        self.predefined_tree.column("id", width=100)
        self.predefined_tree.column("data", width=300)
        self.predefined_tree.column("flags", width=100)
        
        self.predefined_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Populate predefined messages
        for msg in self.predefined_messages:
            flags = []
            if msg.get("extended"):
                flags.append("EXT")
            if msg.get("fd"):
                flags.append("FD")
            if msg.get("brs"):
                flags.append("BRS")
            flags_str = " ".join(flags) if flags else "-"
            
            self.predefined_tree.insert("", tk.END, 
                values=(msg["name"], f"0x{msg['id']:03X}", msg["data"], flags_str))
        
        # Double-click to send
        self.predefined_tree.bind("<Double-1>", self._send_predefined)
        
        # Add new predefined message
        add_frame = ttk.LabelFrame(self.predefined_frame, text="Add Predefined Message")
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        row1 = ttk.Frame(add_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Name:").pack(side=tk.LEFT, padx=5)
        self.predef_name_var = tk.StringVar(value="My Message")
        ttk.Entry(row1, textvariable=self.predef_name_var, width=20).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="ID (hex):").pack(side=tk.LEFT, padx=5)
        self.predef_id_var = tk.StringVar(value="100")
        ttk.Entry(row1, textvariable=self.predef_id_var, width=10).pack(side=tk.LEFT, padx=5)
        
        row2 = ttk.Frame(add_frame)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="Data (hex):").pack(side=tk.LEFT, padx=5)
        self.predef_data_var = tk.StringVar(value="01 02 03 04 05 06 07 08")
        ttk.Entry(row2, textvariable=self.predef_data_var, width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(row2, text="Add", command=self._add_predefined).pack(side=tk.LEFT, padx=5)
        
        # Buttons
        btn_frame = ttk.Frame(self.predefined_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Send Selected", command=self._send_predefined).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove Selected", command=self._remove_predefined).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Load to Send", command=self._load_predefined).pack(side=tk.LEFT, padx=5)
    
    def _create_filter_tab(self):
        """Creates the filters tab"""
        # Filter mode
        mode_frame = ttk.LabelFrame(self.filter_frame, text="Filter Mode")
        mode_frame.pack(fill=tk.X, padx=5, pady=5)
        self.filter_mode_var = tk.StringVar(value="pass_all")
        ttk.Radiobutton(mode_frame, text="Pass All", 
                       variable=self.filter_mode_var, value="pass_all").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="Accept Only Matching (whitelist)", 
                       variable=self.filter_mode_var, value="accept_list").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="Reject Matching (blacklist)", 
                       variable=self.filter_mode_var, value="reject_list").pack(side=tk.LEFT, padx=10)
        
        # Add filter
        add_frame = ttk.LabelFrame(self.filter_frame, text="Add Filter")
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        row1 = ttk.Frame(add_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Name:").pack(side=tk.LEFT, padx=5)
        self.filter_name_var = tk.StringVar(value="Filter1")
        ttk.Entry(row1, textvariable=self.filter_name_var, width=15).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="Type:").pack(side=tk.LEFT, padx=5)
        self.filter_type_var = tk.StringVar(value="single")
        filter_type_combo = ttk.Combobox(row1, textvariable=self.filter_type_var,
                                         values=["single", "range", "mask"], width=10)
        filter_type_combo.pack(side=tk.LEFT, padx=5)
        filter_type_combo.bind("<<ComboboxSelected>>", self._on_filter_type_change)
        
        # Filter parameters
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
        ttk.Label(self.range_frame, text="From (hex):").pack(side=tk.LEFT, padx=5)
        self.filter_from_var = tk.StringVar(value="100")
        ttk.Entry(self.range_frame, textvariable=self.filter_from_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(self.range_frame, text="To (hex):").pack(side=tk.LEFT, padx=5)
        self.filter_to_var = tk.StringVar(value="200")
        ttk.Entry(self.range_frame, textvariable=self.filter_to_var, width=10).pack(side=tk.LEFT, padx=5)
        
        # Mask
        self.mask_frame = ttk.Frame(self.filter_params_frame)
        ttk.Label(self.mask_frame, text="Base ID (hex):").pack(side=tk.LEFT, padx=5)
        self.filter_base_var = tk.StringVar(value="100")
        ttk.Entry(self.mask_frame, textvariable=self.filter_base_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(self.mask_frame, text="Mask (hex):").pack(side=tk.LEFT, padx=5)
        self.filter_mask_var = tk.StringVar(value="7F0")
        ttk.Entry(self.mask_frame, textvariable=self.filter_mask_var, width=10).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(add_frame, text="Add Filter", command=self._add_filter).pack(pady=5)
        
        # Filter list
        list_frame = ttk.LabelFrame(self.filter_frame, text="Active Filters")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ("name", "type", "params", "enabled")
        self.filter_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        self.filter_tree.heading("name", text="Name")
        self.filter_tree.heading("type", text="Type")
        self.filter_tree.heading("params", text="Parameters")
        self.filter_tree.heading("enabled", text="Enabled")
        
        self.filter_tree.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="Enable/Disable", command=self._toggle_filter).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove", command=self._remove_filter).pack(side=tk.LEFT, padx=5)
    
    def _create_periodic_tab(self):
        """Creates the periodic messages tab"""
        # Add periodic message
        add_frame = ttk.LabelFrame(self.periodic_frame, text="Add Periodic Message")
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        row1 = ttk.Frame(add_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="ID (hex):").pack(side=tk.LEFT, padx=5)
        self.periodic_id_var = tk.StringVar(value="100")
        ttk.Entry(row1, textvariable=self.periodic_id_var, width=10).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="Interval (ms):").pack(side=tk.LEFT, padx=5)
        self.periodic_interval_var = tk.StringVar(value="100")
        ttk.Entry(row1, textvariable=self.periodic_interval_var, width=8).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="Count (0=∞):").pack(side=tk.LEFT, padx=5)
        self.periodic_count_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.periodic_count_var, width=6).pack(side=tk.LEFT, padx=5)
        
        row2 = ttk.Frame(add_frame)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="Data (hex):").pack(side=tk.LEFT, padx=5)
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
        
        ttk.Button(row3, text="Add", command=self._add_periodic).pack(side=tk.LEFT, padx=10)
        
        # List
        list_frame = ttk.LabelFrame(self.periodic_frame, text="Periodic Messages")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ("id", "interval", "data", "count", "sent", "enabled")
        self.periodic_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        self.periodic_tree.heading("id", text="ID")
        self.periodic_tree.heading("interval", text="Interval (ms)")
        self.periodic_tree.heading("data", text="Data")
        self.periodic_tree.heading("count", text="Limit")
        self.periodic_tree.heading("sent", text="Sent")
        self.periodic_tree.heading("enabled", text="Enabled")
        
        self.periodic_tree.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X)
        
        self.periodic_start_btn = ttk.Button(btn_frame, text="▶ Start Sending", 
                                             command=self._toggle_periodic)
        self.periodic_start_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Enable/Disable", command=self._toggle_periodic_msg).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove", command=self._remove_periodic).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Reset Counters", command=self._reset_periodic_counters).pack(side=tk.LEFT, padx=5)
    
    def _create_settings_tab(self):
        """Creates the settings tab"""
        timing_frame = ttk.LabelFrame(self.settings_frame, text="Timing")
        timing_frame.pack(fill=tk.X, padx=5, pady=5)
        
        row1 = ttk.Frame(timing_frame)
        row1.pack(fill=tk.X, pady=5)
        
        ttk.Label(row1, text="Min. gap between frames (ms):").pack(side=tk.LEFT, padx=5)
        self.frame_gap_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.frame_gap_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text="Apply", command=self._apply_timing).pack(side=tk.LEFT, padx=10)
        
        info_frame = ttk.LabelFrame(self.settings_frame, text="CAN Timing Information")
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        info_text = """
CAN Frame Timing:

1. Minimum Gap (Interframe Space - IFS):
   - CAN requires minimum 3 bits gap between frames
   - At 500 kbit/s: 3 * 2µs = 6µs
   - At 1 Mbit/s: 3 * 1µs = 3µs

2. Theoretical Throughput:
   - At 500 kbit/s with 8 bytes data (~100 bits/frame):
     Max ~5000 frames/s
   
3. Practical Delays:
   - Software overhead: 0.1-1 ms
   - USB latency: 1-5 ms
   - Recommended min. gap: 1-5 ms for stability

4. Sending Modes:
   - Immediate: no additional delay
   - With min. gap: delay between frames
   - Periodic: fixed time interval
        """
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(padx=5, pady=5)
    
    def _on_filter_type_change(self, event=None):
        """Filter type change handler"""
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
    # Connection Handling
    # =========================================================================
    
    def _toggle_connection(self):
        """Toggles connection"""
        if self.connected:
            self._disconnect()
        else:
            self._connect()
    
    def _connect(self):
        """Connects to device"""
        try:
            channel = int(self.channel_var.get())
            baudrate_str = self.baudrate_var.get()
            use_fd = self.fd_var.get()
            
            # Baudrate mapping
            baudrate_map = {
                "125k": Baudrate.BAUD_125K,
                "250k": Baudrate.BAUD_250K,
                "500k": Baudrate.BAUD_500K,
                "1M": Baudrate.BAUD_1M
            }
            baudrate = baudrate_map.get(baudrate_str, Baudrate.BAUD_500K)
            
            # Create VN1640A instance with baudrate
            from vn1640a_can import BaudrateFD
            self.can = VN1640A(baudrate=baudrate, baudrate_fd=BaudrateFD.BAUD_2M)
            
            # Open driver
            if not self.can.open():
                messagebox.showerror("Error", "Failed to open Vector driver")
                self.can = None
                return
            
            # Start channel
            if use_fd:
                success = self.can.start_fd(channel=channel)
            else:
                success = self.can.start(channel=channel)
            
            if success:
                self.connected = True
                self.connect_btn.config(text="Disconnect")
                self.status_label.config(text=f"Connected: Channel {channel}, {baudrate_str}")
                self.channel_combo.config(state="disabled")
                self.baudrate_combo.config(state="disabled")
            else:
                messagebox.showerror("Error", "Failed to connect to device")
                self.can = None
                
        except Exception as e:
            messagebox.showerror("Error", f"Connection error: {e}")
            self.can = None
    
    def _disconnect(self):
        """Disconnects from device"""
        if self.receiving:
            self._toggle_receiving()
        
        if self.periodic_running:
            self._toggle_periodic()
        
        if self.can:
            self.can.stop()
            self.can.close()
            self.can = None
        
        self.connected = False
        self.connect_btn.config(text="Connect")
        self.status_label.config(text="Disconnected")
        self.channel_combo.config(state="normal")
        self.baudrate_combo.config(state="normal")
    
    # =========================================================================
    # Message Sending
    # =========================================================================
    
    def _send_message(self):
        """Sends a message"""
        if not self.connected:
            messagebox.showwarning("Warning", "Connect to device first")
            return
        
        try:
            # Parse ID
            msg_id = int(self.send_id_var.get(), 16)
            extended = self.extended_var.get()
            use_fd = self.send_fd_var.get()
            brs = self.brs_var.get()
            
            # Parse data
            data_str = self.send_data_var.get().strip()
            data_bytes = bytes.fromhex(data_str.replace(" ", ""))
            
            # Validate data length
            max_bytes = 64 if use_fd else 8
            if len(data_bytes) > max_bytes:
                mode = "CAN FD" if use_fd else "CAN"
                messagebox.showerror("Error", f"Data too long for {mode}!\nMax: {max_bytes} bytes, got: {len(data_bytes)} bytes")
                return
            
            print(f"[GUI DEBUG] Sending: ID=0x{msg_id:X}, data={data_bytes.hex()}, extended={extended}, fd={use_fd}, brs={brs}")
            print(f"[GUI DEBUG] self.can = {self.can}")
            print(f"[GUI DEBUG] self.can.is_on_bus = {self.can.is_on_bus if self.can else 'N/A'}")
            
            # Check timing
            if self.min_frame_gap_ms > 0:
                elapsed = (time.time() - self.last_send_time) * 1000
                if elapsed < self.min_frame_gap_ms:
                    time.sleep((self.min_frame_gap_ms - elapsed) / 1000)
            
            # Send
            if use_fd:
                print("[GUI DEBUG] Calling send_fd()...")
                success = self.can.send_fd(msg_id, data_bytes, extended=extended, brs=brs)
            else:
                print("[GUI DEBUG] Calling send()...")
                success = self.can.send(msg_id, data_bytes, extended=extended)
            
            print(f"[GUI DEBUG] Send result: {success}")
            
            self.last_send_time = time.time()
            
            if success:
                self.tx_count += 1
                # Add to list
                self._add_message_to_tree("TX", msg_id, data_bytes, extended, use_fd, brs)
                # Add to history
                self._add_to_history(msg_id, data_str, extended, use_fd, brs)
            else:
                self.error_count += 1
                messagebox.showerror("Error", "Failed to send message")
                
        except Exception as e:
            print(f"[GUI DEBUG] Exception: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Error: {e}")
    
    def _on_data_changed(self, *args):
        """Called when data entry changes - validates length"""
        try:
            data_str = self.send_data_var.get().strip()
            if data_str:
                data_bytes = bytes.fromhex(data_str.replace(" ", ""))
                byte_count = len(data_bytes)
            else:
                byte_count = 0
            
            # Max length depends on FD mode
            max_bytes = 64 if self.send_fd_var.get() else 8
            
            # Update label with color indication
            if byte_count > max_bytes:
                self.byte_count_var.set(f"{byte_count}/{max_bytes} ⚠")
                self.byte_count_label.configure(foreground="red")
            else:
                self.byte_count_var.set(f"{byte_count}/{max_bytes} bytes")
                self.byte_count_label.configure(foreground="")
        except ValueError:
            self.byte_count_var.set("Invalid!")
            self.byte_count_label.configure(foreground="red")
    
    def _on_fd_mode_changed(self, *args):
        """Called when FD checkbox changes - updates byte counter"""
        self._on_data_changed()
    
    def _pad_with_zeros(self):
        """Pads data with zeros to 8 bytes (CAN) or 64 bytes (CAN FD)"""
        try:
            data_str = self.send_data_var.get().strip()
            if data_str:
                data_bytes = bytes.fromhex(data_str.replace(" ", ""))
            else:
                data_bytes = b""
            
            current_len = len(data_bytes)
            
            if self.send_fd_var.get():
                # CAN FD - always pad to 64 bytes
                target_len = 64
            else:
                # Classic CAN - always 8 bytes
                target_len = 8
            
            # Pad with zeros
            if current_len < target_len:
                padded = data_bytes + bytes(target_len - current_len)
                # Format as hex string with spaces
                hex_str = " ".join(f"{b:02X}" for b in padded)
                self.send_data_var.set(hex_str)
            
        except ValueError:
            messagebox.showwarning("Warning", "Invalid hex data")
    
    def _add_to_history(self, msg_id: int, data_str: str, extended: bool, fd: bool, brs: bool):
        """Adds message to send history"""
        flags = []
        if extended:
            flags.append("EXT")
        if fd:
            flags.append("FD")
        if brs:
            flags.append("BRS")
        flags_str = " ".join(flags) if flags else "-"
        
        time_str = datetime.now().strftime("%H:%M:%S")
        id_str = f"0x{msg_id:08X}" if extended else f"0x{msg_id:03X}"
        
        # Add to history list
        history_entry = {
            "time": time_str,
            "id": msg_id,
            "data": data_str,
            "extended": extended,
            "fd": fd,
            "brs": brs
        }
        self.send_history.insert(0, history_entry)
        
        # Limit history size
        if len(self.send_history) > self.max_history:
            self.send_history = self.send_history[:self.max_history]
        
        # Update history tree
        self.history_tree.insert("", 0, values=(time_str, id_str, data_str, flags_str))
        
        # Limit displayed history
        children = self.history_tree.get_children()
        if len(children) > self.max_history:
            self.history_tree.delete(children[-1])
    
    def _add_message_to_tree(self, direction: str, msg_id: int, data: bytes, 
                            extended: bool = False, fd: bool = False, brs: bool = False):
        """Adds message to the tree"""
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
        
        # ASCII representation
        ascii_str = ""
        if self.show_ascii_var.get():
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
        
        flags = []
        if extended:
            flags.append("EXT")
        if fd:
            flags.append("FD")
        if brs:
            flags.append("BRS")
        flags_str = " ".join(flags)
        
        # Get comment for this ID
        comment = self.id_comments.get(msg_id, "")
        
        # Update grouped messages statistics
        time_now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        if msg_id not in self.grouped_messages:
            self.grouped_messages[msg_id] = {
                "count": 0,
                "last_data": "",
                "last_time": "",
                "comment": comment
            }
        self.grouped_messages[msg_id]["count"] += 1
        self.grouped_messages[msg_id]["last_data"] = data_str
        self.grouped_messages[msg_id]["last_time"] = time_now
        if comment:
            self.grouped_messages[msg_id]["comment"] = comment
        
        # Track message repetitions for fading
        is_stale = False
        if msg_id in self.message_repeat_tracker:
            tracker = self.message_repeat_tracker[msg_id]
            if tracker["last_data"] == data_str:
                # Same data - increment repeat count
                tracker["repeat_count"] += 1
                if tracker["repeat_count"] >= self.stale_threshold:
                    is_stale = True
            else:
                # Data changed - reset counter
                tracker["last_data"] = data_str
                tracker["repeat_count"] = 1
        else:
            # First time seeing this ID
            self.message_repeat_tracker[msg_id] = {
                "last_data": data_str,
                "repeat_count": 1
            }
        
        # Determine tag for coloring (only if coloring is enabled)
        tag = ()
        if self.color_messages_var.get():
            tag = direction  # TX or RX
            # Check for diagnostic IDs (common diagnostic CAN IDs)
            if msg_id in self.id_comments or msg_id in [0x744, 0x74C, 0x7DF, 0x7E0, 0x7E8, 0x700, 0x701, 0x702, 0x703]:
                tag = "DIAG"
            
            # Apply stale suffix if message is repeated without changes
            if is_stale:
                tag = f"{tag}_STALE"
            
            tag = (tag,)
        
        self.msg_tree.insert("", tk.END, 
                            values=(time_str, direction, id_str, dlc, data_str, ascii_str, flags_str, comment),
                            tags=tag)
        
        if self.autoscroll_var.get():
            self.msg_tree.yview_moveto(1)
        
        # Limit messages (to avoid memory issues)
        children = self.msg_tree.get_children()
        if len(children) > 1000:
            self.msg_tree.delete(children[0])
    
    def _refresh_grouped(self):
        """Refreshes the grouped view"""
        # Clear existing items
        for item in self.grouped_tree.get_children():
            self.grouped_tree.delete(item)
        
        # Add all grouped messages sorted by ID
        for msg_id in sorted(self.grouped_messages.keys()):
            data = self.grouped_messages[msg_id]
            id_str = f"0x{msg_id:03X}"
            
            # Determine tag
            tag = ()
            if msg_id in self.id_comments or msg_id in [0x744, 0x74C, 0x7DF, 0x7E0, 0x7E8, 0x700, 0x701, 0x702, 0x703]:
                tag = ("DIAG",)
            
            self.grouped_tree.insert("", tk.END, 
                values=(id_str, data["count"], data["last_data"], data["last_time"], data["comment"]),
                tags=tag)
    
    def _clear_grouped(self):
        """Clears grouped statistics"""
        self.grouped_messages.clear()
        for item in self.grouped_tree.get_children():
            self.grouped_tree.delete(item)
    
    # =========================================================================
    # Message Receiving
    # =========================================================================
    
    def _toggle_receiving(self):
        """Toggles receiving"""
        if self.receiving:
            self.receiving = False
            self.receive_btn.config(text="▶ Start")
        else:
            if not self.connected:
                messagebox.showwarning("Warning", "Connect to device first")
                return
            
            self.receiving = True
            self.receive_btn.config(text="⏹ Stop")
            
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
    
    def _receive_loop(self):
        """Receive loop"""
        print("[GUI] Starting receive...")
        while self.receiving and self.can:
            try:
                msg = self.can.receive(timeout_ms=100)
                if msg:
                    print(f"[GUI] Received: ID=0x{msg.id:X}, DLC={msg.dlc}")
                    # Check filters
                    if self._should_show_message(msg.id):
                        self.msg_queue.put(msg)
                        self.rx_count += 1
            except Exception as e:
                print(f"[GUI] Receive error: {e}")
                self.error_count += 1
        print("[GUI] Stopped receiving")
    
    def _should_show_message(self, msg_id: int) -> bool:
        """Checks if message should be displayed (based on filters)"""
        mode = self.filter_mode_var.get()
        
        if mode == "pass_all":
            return True
        
        # Check if any active filter matches
        any_match = False
        for f in self.filters:
            if f.enabled and f.matches(msg_id):
                any_match = True
                break
        
        if mode == "accept_list":
            return any_match  # Show only matching
        elif mode == "reject_list":
            return not any_match  # Hide matching
        
        return True
    
    def _clear_messages(self):
        """Clears message list"""
        for item in self.msg_tree.get_children():
            self.msg_tree.delete(item)
    
    def _export_log(self):
        """Exports message log to TXT file"""
        children = self.msg_tree.get_children()
        if not children:
            messagebox.showwarning("Warning", "No messages to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Log"
        )
        
        if not filename:
            return
        
        try:
            with open(filename, "w", encoding="utf-8") as f:
                # Write header
                f.write("=" * 80 + "\n")
                f.write(f"CAN Log Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total messages: {len(children)}\n")
                f.write("=" * 80 + "\n\n")
                
                # Write column headers
                f.write(f"{'Time':<15} {'Dir':<5} {'ID':<12} {'DLC':<5} {'Data':<30} {'ASCII':<12} {'Flags':<10}\n")
                f.write("-" * 80 + "\n")
                
                # Write each message
                for item in children:
                    values = self.msg_tree.item(item)["values"]
                    time_str = str(values[0]) if values[0] else ""
                    direction = str(values[1])
                    msg_id = str(values[2])
                    dlc = str(values[3])
                    data = str(values[4])
                    ascii_data = str(values[5]) if len(values) > 5 else ""
                    flags = str(values[6]) if len(values) > 6 else ""
                    
                    f.write(f"{time_str:<15} {direction:<5} {msg_id:<12} {dlc:<5} {data:<30} {ascii_data:<12} {flags:<10}\n")
                
                f.write("\n" + "=" * 80 + "\n")
                f.write("End of log\n")
            
            messagebox.showinfo("Success", f"Log exported to:\n{filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
    
    def _edit_comments(self):
        """Opens dialog to edit ID comments"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit ID Comments")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Instructions
        ttk.Label(dialog, text="Define comments for known CAN IDs:").pack(pady=5)
        
        # Frame for list
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview for comments
        columns = ("id", "comment")
        comment_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        comment_tree.heading("id", text="ID (hex)")
        comment_tree.heading("comment", text="Comment")
        comment_tree.column("id", width=100)
        comment_tree.column("comment", width=350)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=comment_tree.yview)
        comment_tree.configure(yscrollcommand=scrollbar.set)
        
        comment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate with existing comments
        for msg_id, comment in sorted(self.id_comments.items()):
            comment_tree.insert("", tk.END, values=(f"0x{msg_id:03X}", comment))
        
        # Add/Edit frame
        edit_frame = ttk.LabelFrame(dialog, text="Add/Edit Comment")
        edit_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(edit_frame, text="ID (hex):").grid(row=0, column=0, padx=5, pady=2)
        id_var = tk.StringVar(value="100")
        id_entry = ttk.Entry(edit_frame, textvariable=id_var, width=10)
        id_entry.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(edit_frame, text="Comment:").grid(row=0, column=2, padx=5, pady=2)
        comment_var = tk.StringVar()
        comment_entry = ttk.Entry(edit_frame, textvariable=comment_var, width=30)
        comment_entry.grid(row=0, column=3, padx=5, pady=2)
        
        def add_comment():
            try:
                msg_id = int(id_var.get(), 16)
                comment = comment_var.get().strip()
                if comment:
                    self.id_comments[msg_id] = comment
                    # Refresh tree
                    for item in comment_tree.get_children():
                        comment_tree.delete(item)
                    for mid, com in sorted(self.id_comments.items()):
                        comment_tree.insert("", tk.END, values=(f"0x{mid:03X}", com))
            except ValueError:
                messagebox.showerror("Error", "Invalid ID format")
        
        def remove_comment():
            selection = comment_tree.selection()
            if selection:
                values = comment_tree.item(selection[0])["values"]
                msg_id = int(str(values[0]), 16)
                if msg_id in self.id_comments:
                    del self.id_comments[msg_id]
                    comment_tree.delete(selection[0])
        
        def on_select(event):
            selection = comment_tree.selection()
            if selection:
                values = comment_tree.item(selection[0])["values"]
                id_var.set(str(values[0]))
                comment_var.set(str(values[1]))
        
        comment_tree.bind("<<TreeviewSelect>>", on_select)
        
        btn_frame = ttk.Frame(edit_frame)
        btn_frame.grid(row=1, column=0, columnspan=4, pady=5)
        
        ttk.Button(btn_frame, text="Add/Update", command=add_comment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove", command=remove_comment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    # =========================================================================
    # History
    # =========================================================================
    
    def _resend_from_history(self, event=None):
        """Resends selected message from history"""
        if not self.connected:
            messagebox.showwarning("Warning", "Connect to device first")
            return
        
        selection = self.history_tree.selection()
        if not selection:
            return
        
        idx = self.history_tree.index(selection[0])
        if idx < len(self.send_history):
            entry = self.send_history[idx]
            
            # Set values and send
            self.send_id_var.set(f"{entry['id']:X}")
            self.send_data_var.set(entry['data'])
            self.extended_var.set(entry['extended'])
            self.send_fd_var.set(entry['fd'])
            self.brs_var.set(entry['brs'])
            
            self._send_message()
    
    def _clear_history(self):
        """Clears send history"""
        self.send_history.clear()
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
    
    def _load_from_history(self):
        """Loads selected message to send fields"""
        selection = self.history_tree.selection()
        if not selection:
            return
        
        idx = self.history_tree.index(selection[0])
        if idx < len(self.send_history):
            entry = self.send_history[idx]
            
            self.send_id_var.set(f"{entry['id']:X}")
            self.send_data_var.set(entry['data'])
            self.extended_var.set(entry['extended'])
            self.send_fd_var.set(entry['fd'])
            self.brs_var.set(entry['brs'])
            
            # Switch to main tab
            self.notebook.select(0)
    
    # =========================================================================
    # Predefined Messages
    # =========================================================================
    
    def _send_predefined(self, event=None):
        """Sends selected predefined message"""
        if not self.connected:
            messagebox.showwarning("Warning", "Connect to device first")
            return
        
        selection = self.predefined_tree.selection()
        if not selection:
            return
        
        idx = self.predefined_tree.index(selection[0])
        if idx < len(self.predefined_messages):
            msg = self.predefined_messages[idx]
            
            # Set values and send
            self.send_id_var.set(f"{msg['id']:X}")
            self.send_data_var.set(msg['data'])
            self.extended_var.set(msg.get('extended', False))
            self.send_fd_var.set(msg.get('fd', False))
            self.brs_var.set(msg.get('brs', False))
            
            self._send_message()
    
    def _add_predefined(self):
        """Adds a new predefined message"""
        try:
            name = self.predef_name_var.get().strip()
            msg_id = int(self.predef_id_var.get(), 16)
            data = self.predef_data_var.get().strip()
            
            if not name:
                messagebox.showerror("Error", "Name is required")
                return
            
            msg = {
                "name": name,
                "id": msg_id,
                "data": data,
                "extended": False,
                "fd": False,
                "brs": False
            }
            
            self.predefined_messages.append(msg)
            self.predefined_tree.insert("", tk.END, 
                values=(name, f"0x{msg_id:03X}", data, "-"))
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid values: {e}")
    
    def _remove_predefined(self):
        """Removes selected predefined message"""
        selection = self.predefined_tree.selection()
        if not selection:
            return
        
        idx = self.predefined_tree.index(selection[0])
        if idx < len(self.predefined_messages):
            del self.predefined_messages[idx]
            self.predefined_tree.delete(selection[0])
    
    def _load_predefined(self):
        """Loads selected predefined message to send fields"""
        selection = self.predefined_tree.selection()
        if not selection:
            return
        
        idx = self.predefined_tree.index(selection[0])
        if idx < len(self.predefined_messages):
            msg = self.predefined_messages[idx]
            
            self.send_id_var.set(f"{msg['id']:X}")
            self.send_data_var.set(msg['data'])
            self.extended_var.set(msg.get('extended', False))
            self.send_fd_var.set(msg.get('fd', False))
            self.brs_var.set(msg.get('brs', False))
            
            # Switch to main tab
            self.notebook.select(0)
    
    # =========================================================================
    # Filters
    # =========================================================================
    
    def _add_filter(self):
        """Adds a new filter"""
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
            self.filter_tree.insert("", tk.END, values=(name, filter_type, params, "Yes"))
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid values: {e}")
    
    def _toggle_filter(self):
        """Enables/disables selected filter"""
        selection = self.filter_tree.selection()
        if not selection:
            return
        
        idx = self.filter_tree.index(selection[0])
        if 0 <= idx < len(self.filters):
            self.filters[idx].enabled = not self.filters[idx].enabled
            enabled_str = "Yes" if self.filters[idx].enabled else "No"
            values = list(self.filter_tree.item(selection[0])["values"])
            values[3] = enabled_str
            self.filter_tree.item(selection[0], values=values)
    
    def _remove_filter(self):
        """Removes selected filter"""
        selection = self.filter_tree.selection()
        if not selection:
            return
        
        idx = self.filter_tree.index(selection[0])
        if 0 <= idx < len(self.filters):
            del self.filters[idx]
            self.filter_tree.delete(selection[0])
    
    # =========================================================================
    # Periodic Messages
    # =========================================================================
    
    def _add_periodic(self):
        """Adds a periodic message"""
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
                                      values=(id_str, interval, data_str, count_str, 0, "Yes"))
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid values: {e}")
    
    def _toggle_periodic(self):
        """Toggles periodic sending"""
        if self.periodic_running:
            self.periodic_running = False
            self.periodic_start_btn.config(text="▶ Start Sending")
        else:
            if not self.connected:
                messagebox.showwarning("Warning", "Connect to device first")
                return
            
            if not self.periodic_messages:
                messagebox.showwarning("Warning", "Add periodic messages first")
                return
            
            self.periodic_running = True
            self.periodic_start_btn.config(text="⏹ Stop Sending")
            
            self.periodic_thread = threading.Thread(target=self._periodic_loop, daemon=True)
            self.periodic_thread.start()
    
    def _periodic_loop(self):
        """Periodic sending loop"""
        while self.periodic_running and self.can:
            current_time = time.time() * 1000  # ms
            
            for i, pm in enumerate(self.periodic_messages):
                if not pm.enabled:
                    continue
                
                # Check limit
                if pm.count > 0 and pm.sent_count >= pm.count:
                    continue
                
                # Check if time to send
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
                            
                            # Update GUI (via queue)
                            self.msg_queue.put(("periodic_update", i, pm.sent_count))
                        else:
                            self.error_count += 1
                            
                    except Exception as e:
                        self.error_count += 1
            
            # Short wait to avoid CPU overload
            time.sleep(0.001)  # 1ms
    
    def _toggle_periodic_msg(self):
        """Enables/disables selected periodic message"""
        selection = self.periodic_tree.selection()
        if not selection:
            return
        
        idx = self.periodic_tree.index(selection[0])
        if 0 <= idx < len(self.periodic_messages):
            self.periodic_messages[idx].enabled = not self.periodic_messages[idx].enabled
            enabled_str = "Yes" if self.periodic_messages[idx].enabled else "No"
            values = list(self.periodic_tree.item(selection[0])["values"])
            values[5] = enabled_str
            self.periodic_tree.item(selection[0], values=values)
    
    def _remove_periodic(self):
        """Removes selected periodic message"""
        selection = self.periodic_tree.selection()
        if not selection:
            return
        
        idx = self.periodic_tree.index(selection[0])
        if 0 <= idx < len(self.periodic_messages):
            del self.periodic_messages[idx]
            self.periodic_tree.delete(selection[0])
    
    def _reset_periodic_counters(self):
        """Resets send counters"""
        for pm in self.periodic_messages:
            pm.sent_count = 0
            pm.last_sent = 0
        self._refresh_periodic_tree()
    
    def _refresh_periodic_tree(self):
        """Refreshes periodic message tree"""
        for i, item in enumerate(self.periodic_tree.get_children()):
            if i < len(self.periodic_messages):
                pm = self.periodic_messages[i]
                values = list(self.periodic_tree.item(item)["values"])
                values[4] = pm.sent_count
                self.periodic_tree.item(item, values=values)
    
    # =========================================================================
    # Theme
    # =========================================================================
    
    def _toggle_theme(self):
        """Toggles between dark and light theme"""
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.current_theme = DARK_THEME
            self.theme_btn.config(text="☀️ Light Mode")
        else:
            self.current_theme = LIGHT_THEME
            self.theme_btn.config(text="🌙 Dark Mode")
        self._apply_theme()
    
    def _apply_theme(self):
        """Applies the current theme to all widgets"""
        theme = self.current_theme
        
        # Configure root window
        self.root.configure(bg=theme["bg"])
        
        # Configure ttk styles
        style = ttk.Style()
        
        # Frame style
        style.configure("TFrame", background=theme["frame_bg"])
        style.configure("TLabelframe", background=theme["frame_bg"])
        style.configure("TLabelframe.Label", background=theme["frame_bg"], foreground=theme["fg"])
        
        # Label style
        style.configure("TLabel", background=theme["frame_bg"], foreground=theme["fg"])
        
        # Button style
        style.configure("TButton", background=theme["button_bg"], foreground=theme["fg"])
        
        # Entry style
        style.configure("TEntry", fieldbackground=theme["entry_bg"], foreground=theme["fg"])
        
        # Combobox style
        style.configure("TCombobox", fieldbackground=theme["entry_bg"], foreground=theme["fg"])
        
        # Checkbutton style
        style.configure("TCheckbutton", background=theme["frame_bg"], foreground=theme["fg"])
        
        # Radiobutton style
        style.configure("TRadiobutton", background=theme["frame_bg"], foreground=theme["fg"])
        
        # Notebook style
        style.configure("TNotebook", background=theme["frame_bg"])
        style.configure("TNotebook.Tab", background=theme["button_bg"], foreground=theme["fg"])
        
        # Treeview style
        style.configure("Treeview",
                       background=theme["treeview_bg"],
                       foreground=theme["treeview_fg"],
                       fieldbackground=theme["treeview_bg"])
        style.configure("Treeview.Heading",
                       background=theme["heading_bg"],
                       foreground=theme["fg"])
        style.map("Treeview",
                 background=[("selected", theme["select_bg"])],
                 foreground=[("selected", theme["select_fg"])])

    # =========================================================================
    # Timing
    # =========================================================================
    
    def _apply_timing(self):
        """Applies timing settings"""
        try:
            self.min_frame_gap_ms = float(self.frame_gap_var.get())
            messagebox.showinfo("Info", f"Set minimum gap: {self.min_frame_gap_ms} ms")
        except ValueError:
            messagebox.showerror("Error", "Invalid value")
    
    # =========================================================================
    # GUI Update
    # =========================================================================
    
    def _update_gui(self):
        """Updates GUI (called every 50ms)"""
        # Process messages from queue
        try:
            while True:
                item = self.msg_queue.get_nowait()
                
                if isinstance(item, tuple) and item[0] == "periodic_update":
                    # Periodic counter update
                    _, idx, count = item
                    children = list(self.periodic_tree.get_children())
                    if idx < len(children):
                        values = list(self.periodic_tree.item(children[idx])["values"])
                        values[4] = count
                        self.periodic_tree.item(children[idx], values=values)
                elif isinstance(item, CANMsg):
                    # Received message
                    self._add_message_to_tree("RX", item.id, item.data, 
                                             item.is_extended, item.is_fd, item.is_brs)
        except queue.Empty:
            pass
        
        # Update statistics
        self.stats_label.config(text=f"TX: {self.tx_count} | RX: {self.rx_count} | Err: {self.error_count}")
        
        # Schedule next call
        self.root.after(50, self._update_gui)
    
    def on_close(self):
        """Application close handler"""
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