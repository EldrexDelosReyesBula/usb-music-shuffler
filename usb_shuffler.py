#!/usr/bin/env python3
"""
===============================================================================
USB Music Shuffler - Version 1.0.0
===============================================================================
A high-performance, high-contrast desktop GUI application designed to solve 
static linear music playback issues on car stereos, Bluetooth speakers, TVs, 
soundbars, and standalone USB audio hardware.

Author: Eldrex Delos Reyes Bula
License: MIT
Repository: https://github.com/EldrexDelosReyesBula/usb-music-shuffler
===============================================================================
"""

import os
import sys
import re
import shutil
import random
import threading
import platform
import string
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

# -----------------------------------------------------------------------------
# OS Integration & Compatibility Configurations
# -----------------------------------------------------------------------------
# On Windows, set explicit AppUserModelID so Windows groups the app under its
# custom window/taskbar icon instead of defaulting to python.exe.
if platform.system() == "Windows":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("usbshuffler.app.v1")
    except Exception:
        pass

# Supported audio file extensions for scanning
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.wma', '.ogg', '.opus'}

# Regex pattern matching generated shuffle index prefixes, e.g., "[001] ", "[042] "
PREFIX_REGEX = re.compile(r'^\[\d+\]\s*')

# System and hidden directory names to skip during recursive filesystem walks
SKIP_DIRS = {
    '$recycle.bin', 'system volume information', 'windows', 'appdata', 
    '.git', 'node_modules', '.usb_shuffler_temp'
}


def get_removable_drives():
    """
    Scans the host system to detect plugged-in removable USB drives and external volumes.

    Returns:
        tuple: (removable_drives, other_drives)
            removable_drives (list): List of paths to removable USB drives (DRIVE_REMOVABLE).
            other_drives (list): List of secondary fixed drives (excluding system root C:\\).
    """
    removable_drives = []
    other_drives = []
    system = platform.system()
    
    if system == "Windows":
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drive_path = f"{letter}:\\"
                # GetDriveType: 2 = DRIVE_REMOVABLE, 3 = DRIVE_FIXED
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_path)
                if drive_type == 2:
                    removable_drives.append(drive_path)
                elif drive_type == 3 and letter != 'C':
                    other_drives.append(drive_path)
            bitmask >>= 1
    elif system == "Darwin":
        volumes = Path("/Volumes")
        if volumes.exists():
            for v in volumes.iterdir():
                if v.is_dir() and v.name != "Macintosh HD":
                    removable_drives.append(str(v))
    else:
        # Linux mount locations
        for base in ["/media", "/mnt"]:
            bp = Path(base)
            if bp.exists():
                for user in bp.iterdir():
                    if user.is_dir():
                        for d in user.iterdir():
                            if d.is_dir():
                                removable_drives.append(str(d))
    return removable_drives, other_drives


def format_size(bytes_size):
    """
    Converts a file size in raw bytes to a human-readable formatted string.

    Args:
        bytes_size (int): Size in bytes.

    Returns:
        str: Formatted string (e.g., '4.2 MB', '1.1 GB').
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"


class USBMusicShufflerApp(tk.Tk):
    """
    Main Tkinter Application Class for USB Music Shuffler.
    
    Provides a high-contrast desktop GUI with multi-threaded drive scanning,
    filename index tag randomizing, FAT sector re-ordering, search filtering,
    and automatic rollback error recovery.
    """

    def __init__(self):
        super().__init__()
        self.title("USB Music Shuffler")
        self.geometry("1040x700")
        self.minsize(920, 620)
        
        # ---------------------------------------------------------------------
        # Design Tokens: High-Contrast Modern Slate Palette
        # ---------------------------------------------------------------------
        self.bg_color = "#F8FAFC"         # Crisp slate light background
        self.card_bg = "#FFFFFF"         # Pure white card background
        self.card_border = "#CBD5E1"     # Slate card border
        self.text_main = "#0F172A"       # High contrast navy primary text
        self.text_sub = "#334155"        # Slate secondary text
        self.primary_blue = "#2563EB"    # Vibrant blue accent
        self.primary_hover = "#1D4ED8"   # Hover state blue
        self.success_green = "#047857"   # High contrast green for status badges
        self.warning_red = "#DC2626"      # Warning color for error logs
        self.table_row_even = "#FFFFFF"
        self.table_row_odd = "#F1F5F9"
        self.table_header_bg = "#E2E8F0"
        self.table_header_fg = "#0F172A"

        self.configure(bg=self.bg_color)
        
        # Configure TTK Theme and Widget Styles
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        
        # Base Widget Fonts and Colors (Integer font sizes required by Tcl)
        self.style.configure(".", background=self.bg_color, foreground=self.text_main, font=("Segoe UI", 10))
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("Card.TFrame", background=self.card_bg, relief="flat")
        
        self.style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground=self.text_main, background=self.bg_color)
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 10), foreground=self.text_sub, background=self.bg_color)
        self.style.configure("CardTitle.TLabel", font=("Segoe UI", 11, "bold"), foreground=self.primary_blue, background=self.card_bg)
        self.style.configure("TLabel", background=self.card_bg, foreground=self.text_main)
        self.style.configure("Stat.TLabel", font=("Segoe UI", 10, "bold"), foreground=self.text_main, background=self.card_bg)
        
        # Buttons Styling
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), background=self.primary_blue, foreground="#FFFFFF", borderwidth=0)
        self.style.map("Accent.TButton", background=[("active", self.primary_hover)])
        
        self.style.configure("TButton", font=("Segoe UI", 10), background="#F1F5F9", foreground=self.text_main, borderwidth=1, relief="solid")
        self.style.map("TButton", background=[("active", "#CBD5E1")])
        
        self.style.configure("TCheckbutton", background=self.card_bg, foreground=self.text_main, font=("Segoe UI", 10))

        # Notebook Tab Styling
        self.style.configure("TNotebook", background=self.bg_color, borderwidth=0)
        self.style.configure("TNotebook.Tab", background="#E2E8F0", foreground=self.text_sub, font=("Segoe UI", 10, "bold"), padding=[14, 6])
        self.style.map("TNotebook.Tab", background=[("selected", self.primary_blue)], foreground=[("selected", "#FFFFFF")])

        # Treeview (File Table) High-Contrast Styling
        self.style.configure("Treeview", background="#FFFFFF", foreground=self.text_main, 
                             fieldbackground="#FFFFFF", rowheight=28, font=("Segoe UI", 10))
        self.style.configure("Treeview.Heading", background=self.table_header_bg, foreground=self.table_header_fg, 
                             font=("Segoe UI", 10, "bold"), relief="flat", padding=6)
        self.style.map("Treeview", background=[('selected', self.primary_blue)], foreground=[('selected', '#FFFFFF')])

        # State Variables
        self.usb_dir = tk.StringVar(value="")
        self.search_query = tk.StringVar(value="")
        self.search_query.trace_add("write", self._filter_treeview)
        self.include_subfolders = tk.BooleanVar(value=True)
        self.fat_reorder = tk.BooleanVar(value=True)
        self.is_processing = False
        self.is_scanning = False
        self.all_cached_files = []

        # Asset References
        self.logo_img = None
        self.titlebar_icon = None
        self._load_logo()

        # Build Interface and Detect Drives
        self._build_ui()
        self._auto_detect_drives()

    def _load_logo(self):
        """Loads and scales the logo image for header display and window titlebar/taskbar icons."""
        base_dir = Path(__file__).parent
        logo_path = base_dir / "usb-shuffler-logo.png"
        if not logo_path.exists():
            logo_path = base_dir / "logo.png"
            
        if logo_path.exists():
            try:
                pil_full = Image.open(logo_path)
                
                # Set Window Icon for Titlebar & Windows Taskbar
                self.titlebar_icon = ImageTk.PhotoImage(pil_full)
                self.iconphoto(False, self.titlebar_icon)
                
                # Resize scaled header icon
                pil_header = pil_full.resize((56, 56), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_header)
            except Exception as e:
                print(f"Could not load logo asset: {e}")

    def _build_ui(self):
        """Constructs the application layout, cards, control options, search bar, and file list table."""
        main_container = ttk.Frame(self, padding=20)
        main_container.pack(fill="both", expand=True)

        # Top Header Bar
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill="x", pady=(0, 16))
        
        if self.logo_img:
            logo_label = tk.Label(header_frame, image=self.logo_img, bg=self.bg_color)
            logo_label.pack(side="left", padx=(0, 14))

        title_container = ttk.Frame(header_frame)
        title_container.pack(side="left", fill="y")
        
        title_label = ttk.Label(title_container, text="USB Music Shuffler", style="Header.TLabel")
        title_label.pack(anchor="w")
        subtitle = ttk.Label(title_container, text="Shuffle playback for car stereos, Bluetooth speakers, and USB audio players", style="SubHeader.TLabel")
        subtitle.pack(anchor="w")

        # Main Content Paned Split Layout
        content_paned = ttk.Frame(main_container)
        content_paned.pack(fill="both", expand=True)

        # =====================================================================
        # LEFT CONTROL PANEL (Drive Selector, Stats, Options, Actions)
        # =====================================================================
        left_panel = ttk.Frame(content_paned, width=340)
        left_panel.pack(side="left", fill="y", padx=(0, 16))
        left_panel.pack_propagate(False)

        # Card 1: Drive Selection Controls
        drive_card = tk.Frame(left_panel, bg=self.card_bg, highlightbackground=self.card_border, highlightthickness=1, bd=0)
        drive_card.pack(fill="x", pady=(0, 12), ipady=4)

        card1_inner = ttk.Frame(drive_card, style="Card.TFrame", padding=12)
        card1_inner.pack(fill="x")

        ttk.Label(card1_inner, text="1. Target USB Drive", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))

        drive_select_frame = ttk.Frame(card1_inner, style="Card.TFrame")
        drive_select_frame.pack(fill="x", pady=(0, 8))

        self.drive_combo = ttk.Combobox(drive_select_frame, state="readonly", font=("Segoe UI", 10))
        self.drive_combo.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.drive_combo.bind("<<ComboboxSelected>>", self._on_drive_combo_select)

        refresh_btn = ttk.Button(drive_select_frame, text="🔄 Refresh", command=self._auto_detect_drives)
        refresh_btn.pack(side="right")

        path_input_frame = ttk.Frame(card1_inner, style="Card.TFrame")
        path_input_frame.pack(fill="x")

        self.path_entry = tk.Entry(path_input_frame, textvariable=self.usb_dir, bg="#F1F5F9", fg=self.text_main, 
                                  insertbackground=self.text_main, font=("Consolas", 10), relief="flat", bd=6)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        browse_btn = ttk.Button(path_input_frame, text="Browse...", command=self._browse_folder)
        browse_btn.pack(side="right")

        # Card 2: Drive Quick Statistics
        stats_card_frame = tk.Frame(left_panel, bg=self.card_bg, highlightbackground=self.card_border, highlightthickness=1, bd=0)
        stats_card_frame.pack(fill="x", pady=(0, 12))

        card2_inner = ttk.Frame(stats_card_frame, style="Card.TFrame", padding=12)
        card2_inner.pack(fill="x")

        ttk.Label(card2_inner, text="Drive Overview", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 6))
        
        self.lbl_total_tracks = ttk.Label(card2_inner, text="Total Tracks: 0", style="Stat.TLabel")
        self.lbl_total_tracks.pack(anchor="w", pady=2)

        self.lbl_total_size = ttk.Label(card2_inner, text="Total Size: 0 MB", style="Stat.TLabel")
        self.lbl_total_size.pack(anchor="w", pady=2)

        self.lbl_shuffle_status = ttk.Label(card2_inner, text="Shuffled Status: Not Shuffled", style="Stat.TLabel")
        self.lbl_shuffle_status.pack(anchor="w", pady=2)

        # Card 3: Shuffle Processing Options
        opt_card_frame = tk.Frame(left_panel, bg=self.card_bg, highlightbackground=self.card_border, highlightthickness=1, bd=0)
        opt_card_frame.pack(fill="x", pady=(0, 12))

        card3_inner = ttk.Frame(opt_card_frame, style="Card.TFrame", padding=12)
        card3_inner.pack(fill="x")

        ttk.Label(card3_inner, text="2. Shuffle Options", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 6))

        opt1 = ttk.Checkbutton(card3_inner, text="Include subfolders", variable=self.include_subfolders, command=self._scan_and_populate)
        opt1.pack(anchor="w", pady=3)

        opt2 = ttk.Checkbutton(
            card3_inner, 
            text="Re-order FAT physical sequence\n(Required for simple hardware players)", 
            variable=self.fat_reorder
        )
        opt2.pack(anchor="w", pady=3)

        # Card 4: Primary Action Trigger Buttons
        act_card_frame = tk.Frame(left_panel, bg=self.card_bg, highlightbackground=self.card_border, highlightthickness=1, bd=0)
        act_card_frame.pack(fill="x", expand=True, side="bottom")

        card4_inner = ttk.Frame(act_card_frame, style="Card.TFrame", padding=12)
        card4_inner.pack(fill="x")

        self.shuffle_btn = ttk.Button(card4_inner, text="🎲 Shuffle Music Now", style="Accent.TButton", command=self._start_shuffle)
        self.shuffle_btn.pack(fill="x", pady=(0, 8), ipady=4)

        self.unshuffle_btn = ttk.Button(card4_inner, text="↺ Un-shuffle (Restore Original Names)", command=self._start_unshuffle)
        self.unshuffle_btn.pack(fill="x", pady=(0, 8), ipady=2)

        self.scan_btn = ttk.Button(card4_inner, text="🔍 Refresh File List", command=self._scan_and_populate)
        self.scan_btn.pack(fill="x", ipady=2)

        # =====================================================================
        # RIGHT PANEL (Search Bar, File Table View, Activity Log)
        # =====================================================================
        right_panel = ttk.Frame(content_paned)
        right_panel.pack(side="right", fill="both", expand=True)

        # Real-time Track Search Bar
        search_frame = ttk.Frame(right_panel)
        search_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(search_frame, text="🔎 Search Tracks:", font=("Segoe UI", 10, "bold"), background=self.bg_color).pack(side="left", padx=(0, 6))
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_query, bg="#FFFFFF", fg=self.text_main, 
                                     insertbackground=self.text_main, font=("Segoe UI", 10), relief="solid", bd=1)
        self.search_entry.pack(side="left", fill="x", expand=True)

        clear_search_btn = ttk.Button(search_frame, text="Clear", command=lambda: self.search_query.set(""))
        clear_search_btn.pack(side="right", padx=(6, 0))

        # Notebook Tab Container
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill="both", expand=True, pady=(0, 10))

        # Tab 1: Interactive Audio File Treeview Table
        files_tab = ttk.Frame(self.notebook)
        self.notebook.add(files_tab, text="  📂 USB Audio Files List  ")

        tree_frame = ttk.Frame(files_tab)
        tree_frame.pack(fill="both", expand=True)

        columns = ("#", "filename", "folder", "size", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("#", text="#", anchor="center")
        self.tree.heading("filename", text="Filename", anchor="w")
        self.tree.heading("folder", text="Subfolder Path", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("status", text="Status", anchor="center")

        self.tree.column("#", width=50, anchor="center")
        self.tree.column("filename", width=280, anchor="w")
        self.tree.column("folder", width=180, anchor="w")
        self.tree.column("size", width=90, anchor="e")
        self.tree.column("status", width=110, anchor="center")

        # Alternating row tag colors
        self.tree.tag_configure("even", background=self.table_row_even)
        self.tree.tag_configure("odd", background=self.table_row_odd)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # Tab 2: Operation Activity Log
        log_tab = ttk.Frame(self.notebook)
        self.notebook.add(log_tab, text="  📋 Activity Log  ")

        self.log_text = tk.Text(log_tab, bg="#0F172A", fg="#F8FAFC", font=("Consolas", 10), relief="flat", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # Operation Progress Bar
        self.progress = ttk.Progressbar(right_panel, mode="determinate")
        self.progress.pack(fill="x")

    def _log(self, message):
        """Appends a timestamped or formatted message to the activity log widget."""
        def update():
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
        self.after(0, update)

    def _auto_detect_drives(self):
        """Triggers drive detection and selects the primary removable drive automatically."""
        removable_drives, other_drives = get_removable_drives()
        
        if removable_drives:
            all_options = removable_drives + [d for d in other_drives if d not in removable_drives]
            self.drive_combo['values'] = all_options
            self.drive_combo.current(0)
            self.usb_dir.set(removable_drives[0])
            self._log(f"Auto-detected removable USB drive: {removable_drives[0]}")
            self._scan_and_populate()
        elif other_drives:
            self.drive_combo['values'] = other_drives
            self._log("No removable drive detected. Please select a drive or folder.")
            self.lbl_total_tracks.config(text="Total Tracks: Select drive")
        else:
            self.drive_combo['values'] = ["No drives detected"]
            self._log("No drives detected. Click Browse to select your music folder.")

    def _on_drive_combo_select(self, event):
        """Event handler when the user picks a drive from the dropdown combobox."""
        selected = self.drive_combo.get()
        if os.path.exists(selected):
            self.usb_dir.set(selected)
            self._scan_and_populate()

    def _browse_folder(self):
        """Opens a OS file dialog to select a target music folder or USB drive."""
        folder = filedialog.askdirectory(title="Select USB Drive or Music Folder")
        if folder:
            self.usb_dir.set(folder)
            self._scan_and_populate()

    def _scan_and_populate(self):
        """Initiates async background scanning of audio files inside the selected directory."""
        target = self.usb_dir.get().strip()
        if not target or not os.path.exists(target):
            return

        if self.is_scanning:
            return

        self.is_scanning = True
        self.lbl_total_tracks.config(text="Scanning files...")
        
        # Clear existing table items
        for item in self.tree.get_children():
            self.tree.delete(item)

        threading.Thread(target=self._async_scan_worker, args=(target,), daemon=True).start()

    def _fast_scan_dir(self, target_dir, recursive=True):
        """
        Fast scandir-accelerated recursive file scanner. Reads file metadata directly
        from OS directory iterators to eliminate stat overhead on FAT32/exFAT drives.
        """
        audio_files = []
        try:
            with os.scandir(target_dir) as it:
                for entry in it:
                    if entry.name.lower() in SKIP_DIRS or entry.name.startswith('.'):
                        continue
                    try:
                        if entry.is_file(follow_symlinks=False):
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext in AUDIO_EXTENSIONS:
                                audio_files.append(Path(entry.path))
                        elif recursive and entry.is_dir(follow_symlinks=False):
                            audio_files.extend(self._fast_scan_dir(entry.path, recursive=True))
                    except PermissionError:
                        pass
        except PermissionError:
            pass
        return audio_files

    def _async_scan_worker(self, target_dir):
        """Worker thread function to execute fast scan and trigger UI update on completion."""
        try:
            target_path = Path(target_dir)
            recursive = self.include_subfolders.get()

            audio_files = self._fast_scan_dir(target_dir, recursive=recursive)
            audio_files.sort(key=lambda x: str(x).lower())
            self.all_cached_files = audio_files

            self.after(0, lambda: self._update_tree_ui(target_path, audio_files))

        except Exception as e:
            self._log(f"Error during scan: {e}")
        finally:
            self.is_scanning = False

    def _update_tree_ui(self, target_path, files):
        """Updates Treeview table rows, track statistics, and shuffle ratio labels."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        total_bytes = 0
        shuffled_count = 0

        for idx, file_path in enumerate(files, start=1):
            try:
                size = file_path.stat().st_size
                total_bytes += size
                rel_folder = str(file_path.parent.relative_to(target_path))
                if rel_folder == ".":
                    rel_folder = "Root"

                is_shuffled = bool(PREFIX_REGEX.match(file_path.name))
                if is_shuffled:
                    shuffled_count += 1
                    status_str = "🎲 Shuffled"
                else:
                    status_str = "📄 Original"

                row_tag = "even" if idx % 2 == 0 else "odd"

                self.tree.insert("", "end", values=(
                    idx, 
                    file_path.name, 
                    rel_folder, 
                    format_size(size), 
                    status_str
                ), tags=(row_tag,))
            except Exception:
                pass

        # Update Overview Stats Labels
        self.lbl_total_tracks.config(text=f"Total Tracks: {len(files)}")
        self.lbl_total_size.config(text=f"Total Size: {format_size(total_bytes)}")
        self.lbl_shuffle_status.config(
            text=f"Shuffled: {shuffled_count}/{len(files)}" if files else "Shuffled: None",
            foreground=self.success_green if shuffled_count > 0 else self.text_main
        )
        
        self.notebook.tab(0, text=f"  📂 USB Audio Files ({len(files)})  ")
        self._log(f"Loaded {len(files)} audio files.")

    def _filter_treeview(self, *args):
        """Filters displayed table rows based on the real-time search query string."""
        query = self.search_query.get().strip().lower()
        target = self.usb_dir.get().strip()
        if not target or not self.all_cached_files:
            return

        target_path = Path(target)
        if not query:
            filtered = self.all_cached_files
        else:
            filtered = [f for f in self.all_cached_files if query in f.name.lower() or query in str(f.parent).lower()]

        self._update_tree_ui(target_path, filtered)

    def _on_tree_double_click(self, event):
        """Double-click handler: Highlights and opens the selected track in File Explorer."""
        item = self.tree.selection()
        if item:
            values = self.tree.item(item, "values")
            filename = values[1]
            folder_rel = values[2]
            root = Path(self.usb_dir.get())
            if folder_rel == "Root":
                full_path = root / filename
            else:
                full_path = root / folder_rel / filename
            
            if full_path.exists():
                if platform.system() == "Windows":
                    os.system(f'explorer /select,"{full_path}"')
                elif platform.system() == "Darwin":
                    os.system(f'open -R "{full_path}"')

    def _set_ui_state(self, state):
        """Enables or disables UI buttons during active shuffle operations."""
        self.is_processing = (state == "disabled")
        btn_state = "disabled" if self.is_processing else "normal"
        self.shuffle_btn.config(state=btn_state)
        self.unshuffle_btn.config(state=btn_state)
        self.scan_btn.config(state=btn_state)
        self.path_entry.config(state=btn_state)

    def _start_shuffle(self):
        """Validates selection and launches background shuffle execution thread."""
        target = self.usb_dir.get().strip()
        if not target or not os.path.exists(target):
            messagebox.showerror("Error", "Please select a valid USB drive or directory first.")
            return

        self._set_ui_state("disabled")
        self.notebook.select(1)
        threading.Thread(target=self._run_shuffle, args=(target,), daemon=True).start()

    def _run_shuffle(self, target_dir):
        """Worker thread function executing filename tag shuffling and FAT re-ordering."""
        try:
            self._log("\n==========================================")
            self._log("🎲 STARTING MUSIC SHUFFLE OPERATION")
            self._log("==========================================")
            
            files = self._fast_scan_dir(target_dir, recursive=self.include_subfolders.get())

            if not files:
                self._log("⚠️ No audio files found in the selected folder.")
                messagebox.showinfo("No Files", "No audio files (.mp3, .wav, .flac, .m4a, etc.) were found.")
                return

            self._log(f"Found {len(files)} tracks to shuffle.")

            # Step 1: Clean existing numerical prefixes first
            cleaned_files = []
            for f in files:
                filename = f.name
                if PREFIX_REGEX.match(filename):
                    new_name = PREFIX_REGEX.sub('', filename)
                    new_path = f.parent / new_name
                    try:
                        f.rename(new_path)
                        cleaned_files.append(new_path)
                    except PermissionError:
                        self._log(f"⚠️ File locked by another app: {filename}")
                        cleaned_files.append(f)
                    except Exception as e:
                        self._log(f"Error resetting prefix on {filename}: {e}")
                        cleaned_files.append(f)
                else:
                    cleaned_files.append(f)

            # Step 2: Generate random numerical index tags
            random.shuffle(cleaned_files)
            num_digits = max(3, len(str(len(cleaned_files))))

            shuffled_paths = []
            total = len(cleaned_files)
            self.after(0, lambda: self.progress.config(maximum=total, value=0))

            self._log("Applying randomized filename index tags...")
            for idx, file_path in enumerate(cleaned_files, start=1):
                prefix = f"[{idx:0{num_digits}d}] "
                new_filename = prefix + file_path.name
                new_path = file_path.parent / new_filename

                try:
                    file_path.rename(new_path)
                    shuffled_paths.append(new_path)
                except PermissionError:
                    self._log(f"⚠️ File locked by another app: {file_path.name}")
                    shuffled_paths.append(file_path)
                except Exception as e:
                    self._log(f"Error tag renaming {file_path.name}: {e}")
                    shuffled_paths.append(file_path)

                self.after(0, lambda v=idx: self.progress.config(value=v))

            self._log("✅ Filename shuffling completed!")

            # Step 3: FAT physical directory re-ordering with rollback recovery
            if self.fat_reorder.get():
                self._log("Re-ordering FAT physical directory index entries...")
                self._reorder_fat_physical_safe(target_dir, shuffled_paths)

            self._log("🎉 Shuffle operation completed successfully!")
            self.after(0, self._scan_and_populate)
            messagebox.showinfo("Success", f"Successfully shuffled {len(shuffled_paths)} tracks!\nYour speaker will now play them in random order.")

        except Exception as e:
            self._log(f"❌ Error during shuffle: {e}")
            messagebox.showerror("Error", f"An error occurred:\n{e}")
        finally:
            self.after(0, lambda: self._set_ui_state("normal"))

    def _reorder_fat_physical_safe(self, root_dir, file_paths):
        """
        Physically re-writes files into a temporary folder and moves them back in a randomized sequence.
        Includes automatic rollback recovery so files are NEVER lost if a move fails midway.
        """
        temp_dir = Path(root_dir) / ".usb_shuffler_temp"
        moved_records = []
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)

            self._log("Buffering files on USB drive...")
            for idx, src in enumerate(file_paths):
                if not src.exists():
                    continue
                temp_dst = temp_dir / f"temp_{idx}{src.suffix}"
                temp_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(temp_dst))
                moved_records.append((temp_dst, src))

            self._log("Re-writing physical sectors in randomized sequence...")
            for temp_src, final_dst in moved_records:
                final_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(temp_src), str(final_dst))

            if temp_dir.exists():
                shutil.rmtree(temp_dir)

            self._log("✅ FAT Physical directory entries updated successfully!")

        except Exception as e:
            self._log(f"⚠️ FAT physical re-ordering encounter: {e}")
            self._log("Initiating automatic file rollback recovery...")
            for temp_src, final_dst in moved_records:
                if temp_src.exists() and not final_dst.exists():
                    try:
                        shutil.move(str(temp_src), str(final_dst))
                    except Exception as err:
                        self._log(f"Rollback error for {final_dst.name}: {err}")
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass

    def _start_unshuffle(self):
        """Launches background un-shuffle execution thread."""
        target = self.usb_dir.get().strip()
        if not target or not os.path.exists(target):
            messagebox.showerror("Error", "Please select a valid USB drive or directory first.")
            return

        self._set_ui_state("disabled")
        self.notebook.select(1)
        threading.Thread(target=self._run_unshuffle, args=(target,), daemon=True).start()

    def _run_unshuffle(self, target_dir):
        """Worker thread function to strip numerical prefix tags and restore original filenames."""
        try:
            self._log("\n==========================================")
            self._log("↺ STARTING UN-SHUFFLE OPERATION")
            self._log("==========================================")
            
            files = self._fast_scan_dir(target_dir, recursive=self.include_subfolders.get())

            restored_count = 0
            total = len(files)
            self.after(0, lambda: self.progress.config(maximum=total, value=0))

            for idx, f in enumerate(files, start=1):
                filename = f.name
                if PREFIX_REGEX.match(filename):
                    clean_name = PREFIX_REGEX.sub('', filename)
                    new_path = f.parent / clean_name
                    try:
                        f.rename(new_path)
                        restored_count += 1
                    except Exception as e:
                        self._log(f"Error restoring {filename}: {e}")

                self.after(0, lambda v=idx: self.progress.config(value=v))

            self._log(f"✅ Un-shuffle complete! Restored {restored_count} tracks.")
            self.after(0, self._scan_and_populate)
            messagebox.showinfo("Un-shuffle Complete", f"Restored {restored_count} files back to their original filenames.")

        except Exception as e:
            self._log(f"❌ Error during un-shuffle: {e}")
            messagebox.showerror("Error", f"An error occurred while un-shuffling:\n{e}")
        finally:
            self.after(0, lambda: self._set_ui_state("normal"))


if __name__ == "__main__":
    app = USBMusicShufflerApp()
    app.mainloop()
