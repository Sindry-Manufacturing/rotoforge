import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import serial
import serial.tools.list_ports
import threading
import time
import csv
import datetime
import os

APP_TITLE = "AF-RB Control Center: Slicer + Monitor"

# ==========================================
# PART 1: SLICER HELPERS & GENERATORS (Preserved 100%)
# ==========================================

def parse_csv_floats(s):
    try:
        parts = [p.strip() for p in str(s).split(",") if p.strip() != ""]
        return [float(p) for p in parts] if parts else []
    except Exception:
        return []

def _is_fixture(P):
    return P.get('mode', 'bed') == 'fixture'

def _absZ(P, z):
    if _is_fixture(P) and P.get('fixture_apply_to_layers', False):
        return float(P.get('fixture_base_z', 0.0)) + float(z)
    return float(z)

def _approachZ(P):
    if _is_fixture(P):
        return float(P.get('fixture_base_z', 0.0)) + float(P.get('fixture_approach_z', 0.8))
    return _travelZ(P)

def _travelZ(P):
    tz = float(P.get('travel_z', 10.0))
    if _is_fixture(P) and P.get('fixture_apply_to_layers', False):
        return float(P.get('fixture_base_z', 0.0)) + tz
    return tz

def compute_e_per_mm(e_mode, bead_width, layer_height, wire_diam):
    if e_mode == "x":
        return 1.0
    wire_area = math.pi * (wire_diam/2.0)**2 if wire_diam > 0 else 0
    bead_area = bead_width * layer_height
    return bead_area / wire_area if wire_area > 0 else 1.0

def gcode_header(params):
    lines = []
    L = lines.append
    L("G90"); L("G21"); L("M83"); L("T0"); L("G92 E0")

    # Bed preheat
    bed = float(params.get('bed_temp', 0) or 0)
    wait_bed = bool(params.get('wait_bed', False))
    bed_dwell_ms = int(float(params.get('bed_dwell_ms', 0) or 0))
    if bed > 0:
        L(f"M140 S{int(bed)}")
        if wait_bed:
            L(f"M190 S{int(bed)}")
            if bed_dwell_ms > 0: L(f"G4 P{bed_dwell_ms}")
    else:
        L("M140 S0")

    # Hotend preheat
    hotend = max(0, min(280, int(float(params.get('hotend_temp', 0) or 0))))
    wait_he = bool(params.get('wait_hotend', False))
    he_dwell_ms = int(float(params.get('hotend_dwell_ms', 0) or 0))
    if hotend > 0:
        L(f"M104 S{hotend}")
        if wait_he:
            L(f"M109 S{hotend}")
            if he_dwell_ms > 0: L(f"G4 P{he_dwell_ms}")
    else:
        L("M104 S0")

    # Cold extrusion
    if bool(params.get('allow_cold_extrude', True)):
        L("M302 S0")
    else:
        min_e_temp = max(0, min(280, int(float(params.get('min_e_temp', 0) or 0))))
        if min_e_temp <= 0 and hotend > 0:
            min_e_temp = max(0, hotend - 20)
        L(f"M302 S{min_e_temp}")

    # Homing & environment
    L("G28")
    L(f"M106 S{int(params.get('fan', 0))}")
    L(f"M3 S{int(params.get('spindle', 30000))}")
    L("G4 P2000")

    # Mode-aware initial height
    if _is_fixture(params):
        L(f"G0 Z{_approachZ(params):.3f} F{int(params.get('feed_travel', 6000))}")
    else:
        L(f"G0 Z{_travelZ(params):.3f} F{int(params.get('feed_travel', 6000))}")
    return lines

def gcode_footer(params):
    return ["M5", "M107", f"G0 Z{_travelZ(params):.3f} F{int(params.get('feed_travel',6000))}"]

# --- GENERATORS (Copied Verbatim) ---

def gen_straight_multitrack(P):
    x_start = P['x_start']; y_start = P['y_start']; length_x = P['length_x']
    z_first = P['z_first']; z_step = P['z_step']; z_final = P['z_final']
    feed_dep = P['feed_dep']; feed_z = P['feed_z']; feed_travel = P['feed_travel']
    dwell_ms = P['dwell_ms']
    e_mode = P['e_mode']; bead_width = P['bead_width']; wire_diam = P['wire_diam']
    lead_in = P['lead_in']; runout = P['runout']; retract = P['retract']
    use_z_dive_cut = P['use_z_dive_cut']; z_dive_amount = P['z_dive_amount']
    multitrack = P['multitrack']; track_count = max(1, int(P['track_count'])); overlap_frac = max(0.0, min(0.9, P['overlap_frac']))
    serpentine_y = P['serpentine_y']

    x_end = x_start - length_x
    x_lead_in_start = x_start + max(0.0, lead_in)
    x_end_runout = x_end - max(0.0, runout)

    e_per_mm = compute_e_per_mm(e_mode, bead_width, z_step, wire_diam)
    spacing = bead_width * (1.0 - overlap_frac)
    y_tracks_up = [y_start + i * spacing for i in range(track_count)]

    lines = []
    lines += gcode_header(P)

    first_move_done = False
    z = z_first; layer_idx = 0
    while z <= z_final + 1e-9:
        z_abs = _absZ(P, z)
        y_list = y_tracks_up if (layer_idx % 2 == 0 or not serpentine_y) else list(reversed(y_tracks_up))
        for y in y_list:
            z_move = _approachZ(P) if (not first_move_done and P.get('fixture_first_move_at_approach', True) and _is_fixture(P)) else _travelZ(P)
            lines.append(f"G0 X{x_lead_in_start:.3f} Y{y:.3f} Z{z_move:.3f} F{int(feed_travel)}")
            first_move_done = True
            lines.append(f"G1 Z{z_abs:.3f} F{int(feed_z)}")
            if dwell_ms > 0: lines.append(f"G4 P{int(dwell_ms)}")
            if lead_in > 0: lines.append(f"G1 X{x_start:.3f} F{int(feed_dep)}")
            E = e_per_mm * (x_start - x_end)
            lines.append(f"G1 X{x_end:.3f} E{E:.3f} F{int(feed_dep)}")
            if runout > 0: lines.append(f"G1 X{x_end_runout:.3f} F{int(feed_dep)}")
            if use_z_dive_cut and z_dive_amount > 0:
                lines += ["G91", f"G1 Z{-abs(z_dive_amount):.3f} F{int(feed_z)}", "G90"]
            if retract != 0: lines.append(f"G1 E{-abs(retract):.3f} F600")
            lines.append(f"G0 Z{_travelZ(P):.3f} F{int(feed_travel)}")
            lines.append("G92 E0")
        z += z_step; layer_idx += 1

    lines += gcode_footer(P)
    return "\n".join(lines)

def gen_dot_stack(P):
    x = P['x_start']; y = P['y_start']
    z_first = P['z_first']; z_step = P['z_step']; z_final = P['z_final']
    feed_dep = P['feed_dep']; feed_z = P['feed_z']; feed_travel = P['feed_travel']
    dwell_ms = P['dwell_ms']; e_pulse = P['e_pulse']; e_retract = P['e_retract']

    lines = []; lines += gcode_header(P)
    first_move_done = False

    z = z_first
    while z <= z_final + 1e-9:
        z_abs = _absZ(P, z)
        z_move = _approachZ(P) if (not first_move_done and P.get('fixture_first_move_at_approach', True) and _is_fixture(P)) else _travelZ(P)
        lines.append(f"G0 X{x:.3f} Y{y:.3f} Z{z_move:.3f} F{int(feed_travel)}")
        first_move_done = True
        lines.append(f"G1 Z{z_abs:.3f} F{int(feed_z)}")
        if dwell_ms > 0: lines.append(f"G4 P{int(dwell_ms)}")
        lines.append(f"G1 E{e_pulse:.3f} F{int(feed_dep)}")
        if e_retract != 0: lines.append(f"G1 E{-abs(e_retract):.3f} F600")
        lines.append(f"G0 Z{_travelZ(P):.3f} F{int(feed_travel)}")
        lines.append("G92 E0")
        z += z_step
    lines += gcode_footer(P)
    return "\n".join(lines)

def gen_sideways_micro_raster(P):
    x_start = P['x_start']; y0 = P['y_start']; x_stroke = P['x_stroke']
    y_span = P['y_span']; dy = max(0.01, P['dy_step'])
    z_first = P['z_first']; z_step = P['z_step']; z_final = P['z_final']
    feed_dep = P['feed_dep']; feed_z = P['feed_z']; feed_travel = P['feed_travel']
    dwell_ms = P['dwell_ms']; runout = P['runout']; retract = P['retract']
    e_mode = P['e_mode']; bead_width = P['bead_width']; wire_diam = P['wire_diam']

    x_end = x_start - x_stroke
    x_end_runout = x_end - max(0.0, runout)
    e_per = compute_e_per_mm(e_mode, bead_width, z_step, wire_diam) * x_stroke
    n_tracks = max(1, int(math.ceil(y_span / dy)))

    lines = []; lines += gcode_header(P)
    first_move_done = False

    z = z_first
    while z <= z_final + 1e-9:
        z_abs = _absZ(P, z)
        y = y0
        for _ in range(n_tracks):
            z_move = _approachZ(P) if (not first_move_done and P.get('fixture_first_move_at_approach', True) and _is_fixture(P)) else _travelZ(P)
            lines.append(f"G0 X{x_start:.3f} Y{y:.3f} Z{z_move:.3f} F{int(feed_travel)}")
            first_move_done = True
            lines.append(f"G1 Z{z_abs:.3f} F{int(feed_z)}")
            if dwell_ms > 0: lines.append(f"G4 P{int(dwell_ms)}")
            lines.append(f"G1 X{x_end:.3f} E{e_per:.3f} F{int(feed_dep)}")
            if runout > 0: lines.append(f"G1 X{x_end_runout:.3f} F{int(feed_dep)}")
            if retract != 0: lines.append(f"G1 E{-abs(retract):.3f} F600")
            lines.append(f"G0 Z{_travelZ(P):.3f} F{int(feed_travel)}")
            lines.append("G92 E0")
            y += dy
        z += z_step
    lines += gcode_footer(P)
    return "\n".join(lines)

def gen_diagonal_drift(P):
    x_start = P['x_start']; y_start = P['y_start']; x_total = P['x_total']
    y_drift = P['y_drift']; seg_dx = max(0.01, P['seg_dx'])
    z_first = P['z_first']; z_step = P['z_step']; z_final = P['z_final']
    feed_dep = P['feed_dep']; feed_z = P['feed_z']; feed_travel = P['feed_travel']
    dwell_ms = P['dwell_ms']; runout = P['runout']; retract = P['retract']
    e_mode = P['e_mode']; bead_width = P['bead_width']; wire_diam = P['wire_diam']

    n_segments = max(1, int(round(x_total / seg_dx)))
    dx = x_total / n_segments; dy = y_drift / n_segments

    lines = []; lines += gcode_header(P)
    first_move_done = False

    z = z_first
    while z <= z_final + 1e-9:
        z_abs = _absZ(P, z)
        z_move = _approachZ(P) if (not first_move_done and P.get('fixture_first_move_at_approach', True) and _is_fixture(P)) else _travelZ(P)
        lines.append(f"G0 X{x_start:.3f} Y{y_start:.3f} Z{z_move:.3f} F{int(feed_travel)}")
        first_move_done = True
        lines.append(f"G1 Z{z_abs:.3f} F{int(feed_z)}")
        if dwell_ms > 0: lines.append(f"G4 P{int(dwell_ms)}")
        x = x_start; y = y_start
        e_per_seg = compute_e_per_mm(e_mode, bead_width, z_step, wire_diam) * abs(dx)
        for _ in range(n_segments):
            x -= dx; y += dy
            if dx >= 0:  # must be negative X
                continue
            lines.append(f"G1 X{x:.3f} Y{y:.3f} E{e_per_seg:.3f} F{int(feed_dep)}")
        if runout > 0: lines.append(f"G1 X{(x - runout):.3f} F{int(feed_dep)}")
        if retract != 0: lines.append(f"G1 E{-abs(retract):.3f} F600")
        lines.append(f"G0 Z{_travelZ(P):.3f} F{int(feed_travel)}")
        lines.append(f"G0 X{x_start:.3f} Y{y_start:.3f} F{int(feed_travel)}")
        lines.append("G92 E0")
        z += z_step
    lines += gcode_footer(P)
    return "\n".join(lines)

def gen_overhang_tests(P):
    x_start = P['x_start']; y_base = P['y_base']; length_x = P['length_x']
    z_first = P['z_first']; z_offsets = parse_csv_floats(P['z_offsets_csv']) or [0.10,0.20,0.30,0.40,0.50]
    y_list = parse_csv_floats(P['y_offsets_csv'])
    if not y_list:
        step = float(P['y_step'])
        y_list = [i * step for i in range(len(z_offsets))]

    n = min(len(z_offsets), len(y_list))
    z_offsets = z_offsets[:n]; y_list = y_list[:n]
    x_end = x_start - length_x
    e_per_mm = compute_e_per_mm(P['e_mode'], P['bead_width'], P['layer_height'], P['wire_diam'])
    feed_dep = P['feed_dep']; feed_z = P['feed_z']; feed_travel = P['feed_travel']
    dwell_ms = P['dwell_ms']; runout = P['runout']; retract = P['retract']

    lines = []; lines += gcode_header(P)
    first_move_done = False

    for i in range(n):
        z = z_first + z_offsets[i]
        z_abs = _absZ(P, z)
        y = y_base + y_list[i]
        z_move = _approachZ(P) if (not first_move_done and P.get('fixture_first_move_at_approach', True) and _is_fixture(P)) else _travelZ(P)
        lines.append(f"G0 X{x_start:.3f} Y{y:.3f} Z{z_move:.3f} F{int(feed_travel)}")
        first_move_done = True
        lines.append(f"G1 Z{z_abs:.3f} F{int(feed_z)}")
        if dwell_ms > 0: lines.append(f"G4 P{int(dwell_ms)}")
        E = e_per_mm * (x_start - x_end)
        lines.append(f"G1 X{x_end:.3f} E{E:.3f} F{int(feed_dep)}")
        if runout > 0: lines.append(f"G1 X{(x_end - runout):.3f} F{int(feed_dep)}")
        if retract != 0: lines.append(f"G1 E{-abs(retract):.3f} F600")
        lines.append(f"G0 Z{_travelZ(P):.3f} F{int(feed_travel)}")
        lines.append("G92 E0")
    lines += gcode_footer(P)
    return "\n".join(lines)

# ==========================================
# PART 2: NEW MONITOR GAUGE
# ==========================================

class SpeedometerGauge(tk.Canvas):
    def __init__(self, parent, width=300, height=180, max_value=30000, **kwargs):
        super().__init__(parent, width=width, height=height, **kwargs)
        self.width = width
        self.height = height
        self.max_value = max_value
        self.center_x = width / 2
        self.center_y = height - 20 
        self.radius = min(width/2, height) - 20
        self.draw_background()
        self.needle = self.create_line(self.center_x, self.center_y, self.center_x, self.center_y - self.radius, fill="red", width=4, arrow=tk.LAST)
        self.value_text = self.create_text(self.center_x, self.center_y - 40, text="0 RPM", font=("Arial", 14, "bold"), fill="#333")

    def draw_background(self):
        # Zones: Green (0-20k), Yellow (20k-25k), Red (25k-30k)
        self.create_arc(20, 20+self.height-self.radius, self.width-20, self.center_y + self.radius, start=0, extent=30, style=tk.ARC, outline="red", width=20)
        self.create_arc(20, 20+self.height-self.radius, self.width-20, self.center_y + self.radius, start=30, extent=30, style=tk.ARC, outline="gold", width=20)
        self.create_arc(20, 20+self.height-self.radius, self.width-20, self.center_y + self.radius, start=60, extent=120, style=tk.ARC, outline="#4CAF50", width=20)
        
        # Ticks
        for i in range(0, 31, 5):
            angle = 180 - (i * 1000 / self.max_value) * 180
            rad = math.radians(angle)
            r1 = self.radius - 10; r2 = self.radius + 5
            x1 = self.center_x + r1 * math.cos(rad); y1 = self.center_y - r1 * math.sin(rad)
            x2 = self.center_x + r2 * math.cos(rad); y2 = self.center_y - r2 * math.sin(rad)
            self.create_line(x1, y1, x2, y2, fill="#333", width=2)
            
            # Text
            tr = self.radius - 25
            tx = self.center_x + tr * math.cos(rad); ty = self.center_y - tr * math.sin(rad)
            self.create_text(tx, ty, text=str(i), font=("Arial", 8))

    def set_value(self, rpm):
        rpm = max(0, min(rpm, self.max_value))
        angle = 180 - (rpm / self.max_value) * 180
        rad = math.radians(angle)
        nr = self.radius - 15
        nx = self.center_x + nr * math.cos(rad)
        ny = self.center_y - nr * math.sin(rad)
        self.coords(self.needle, self.center_x, self.center_y, nx, ny)
        self.itemconfigure(self.value_text, text=f"{int(rpm)} RPM")

# ==========================================
# PART 3: MAIN APP (INTEGRATED)
# ==========================================

class AFRBControlCenter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1300x950")
        
        # State containers
        self.common = {}
        self.st = {} # Straight
        self.dot = {} # Dots
        self.rs = {} # Raster
        self.df = {} # Drift
        self.oh = {} # Overhang
        
        # Monitor State
        self.serial_port = None
        self.is_logging = False
        self.stop_thread = False
        self.csv_file = None
        self.csv_writer = None
        self.var_port = tk.StringVar(value="COM4")
        self.var_log_path = tk.StringVar(value=os.path.join(os.getcwd(), "motor_log.csv"))
        self.var_status = tk.StringVar(value="Monitor Disconnected")
        self.var_volt = tk.StringVar(value="0.00 V")
        self.var_time = tk.StringVar(value="--:--:--")

        self.create_layout()
        self.apply_material_preset("Aluminum 1100-O (Ø0.50 mm)")

    def create_layout(self):
        tab_control = ttk.Notebook(self)
        
        # Tab 1: Slicer (Wraps the original Playground logic)
        self.tab_slicer = ttk.Frame(tab_control)
        tab_control.add(self.tab_slicer, text="G-Code Slicer")
        self.build_slicer_tab(self.tab_slicer)

        # Tab 2: Monitor (New ESP32 Gauge)
        self.tab_monitor = ttk.Frame(tab_control)
        tab_control.add(self.tab_monitor, text="Data Monitor")
        self.build_monitor_tab(self.tab_monitor)

        tab_control.pack(expand=1, fill="both")

    # -------------------------------------------------------------
    # SLICER UI BUILDER (Refactored from original Playground class)
    # -------------------------------------------------------------
    def build_slicer_tab(self, parent):
        # 1. Top Bar (Mode, Material, Preheat)
        self._build_topbar(parent)
        
        # 2. Slicer Sub-Tabs
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, padx=5, pady=5)

        # Straight / Multitrack
        t1 = ttk.Frame(nb); nb.add(t1, text="Straight / Multitrack")
        self._build_tab_straight(t1)

        # Dot Stack
        t2 = ttk.Frame(nb); nb.add(t2, text="Dot Stack")
        self._build_tab_dots(t2)

        # Sideways Micro-Raster
        t3 = ttk.Frame(nb); nb.add(t3, text="Sideways Micro-Raster")
        self._build_tab_raster(t3)

        # Diagonal Drift
        t4 = ttk.Frame(nb); nb.add(t4, text="Diagonal Drift")
        self._build_tab_drift(t4)

        # Overhang Tests
        t5 = ttk.Frame(nb); nb.add(t5, text="Overhang Tests")
        self._build_tab_overhang(t5)

    def _build_topbar(self, parent):
        pad = {'padx': 8, 'pady': 6}
        f = ttk.Frame(parent); f.pack(fill="x")

        # Mode switch
        ttk.Label(f, text="Mode:").pack(side="left", **pad)
        self.mode = tk.StringVar(value="bed")
        ttk.Radiobutton(f, text="Standard Bed", variable=self.mode, value="bed", command=self._on_mode_change).pack(side="left")
        ttk.Radiobutton(f, text="Fixture (Scale)", variable=self.mode, value="fixture", command=self._on_mode_change).pack(side="left")

        # Material presets
        ttk.Separator(f, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(f, text="Material Preset").pack(side="left", **pad)
        self.common['material'] = tk.StringVar(value="Aluminum 1100-O (Ø0.50 mm)")
        self.preset_combo = ttk.Combobox(f, textvariable=self.common['material'],
                                         values=["Aluminum 1100-O (Ø0.50 mm)","Steel 1008 (Ø0.356 mm)"],
                                         state="readonly", width=28)
        self.preset_combo.pack(side="left", **pad)
        self.preset_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_material_preset(self.common['material'].get()))
        ttk.Button(f, text="Toggle Steel/Aluminum", command=self.toggle_material).pack(side="left", padx=6)

        # Bed preheat
        ttk.Separator(f, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(f, text="Bed °C").pack(side="left"); self.bed_temp = tk.StringVar(value="110")
        ttk.Entry(f, textvariable=self.bed_temp, width=6).pack(side="left")
        self.wait_bed = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Wait (M190)", variable=self.wait_bed).pack(side="left")
        ttk.Label(f, text="Bed dwell ms").pack(side="left"); self.bed_dwell = tk.StringVar(value="2000")
        ttk.Entry(f, textvariable=self.bed_dwell, width=8).pack(side="left")

        # Hotend preheat
        ttk.Separator(f, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(f, text="Hotend °C").pack(side="left"); self.hotend_temp = tk.StringVar(value="0")
        ttk.Entry(f, textvariable=self.hotend_temp, width=6).pack(side="left")
        self.wait_hotend = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Wait (M109)", variable=self.wait_hotend).pack(side="left")
        ttk.Label(f, text="Hotend dwell ms").pack(side="left"); self.hotend_dwell = tk.StringVar(value="0")
        ttk.Entry(f, textvariable=self.hotend_dwell, width=8).pack(side="left")
        self.allow_cold_extrude = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Allow cold E (M302 S0)", variable=self.allow_cold_extrude).pack(side="left")
        ttk.Label(f, text="Min E temp").pack(side="left"); self.min_e_temp = tk.StringVar(value="50")
        ttk.Entry(f, textvariable=self.min_e_temp, width=6).pack(side="left")

        # Fixture frame
        self.fixture_frame = ttk.Frame(parent)
        self._build_fixture_row(self.fixture_frame)
        self.fixture_frame.pack_forget() # Default hidden

    def _build_fixture_row(self, frame):
        pad = {'padx': 8, 'pady': 6}
        f = ttk.Frame(frame); f.pack(fill="x")
        ttk.Separator(f, orient="horizontal").pack(fill="x", padx=8, pady=6)
        ttk.Label(f, text="Fixture (Scale) Controls").pack(side="left", padx=8)
        self.fixture_base_z = tk.StringVar(value="62.15")
        self.fixture_approach_z = tk.StringVar(value="0.8")
        self.fixture_apply_to_layers = tk.BooleanVar(value=True)
        self.fixture_first_move_at_approach = tk.BooleanVar(value=True)
        ttk.Label(f, text="Fixture base Z").pack(side="left"); ttk.Entry(f, textvariable=self.fixture_base_z, width=8).pack(side="left")
        ttk.Label(f, text="Approach +Z").pack(side="left"); ttk.Entry(f, textvariable=self.fixture_approach_z, width=6).pack(side="left")
        ttk.Checkbutton(f, text="Apply base to layer Z", variable=self.fixture_apply_to_layers).pack(side="left")
        ttk.Checkbutton(f, text="First XY travel at approach Z", variable=self.fixture_first_move_at_approach).pack(side="left")

    def _on_mode_change(self):
        if self.mode.get() == "fixture":
            self.fixture_frame.pack(fill="x")
        else:
            self.fixture_frame.pack_forget()

    # -- Slicer Tab Content Builders (Copied logic) --
    def _ent(self, parent, label, default, row, col_label=0, col_entry=1, width=12):
        ttk.Label(parent, text=label).grid(row=row, column=col_label, sticky="w", padx=6, pady=4)
        var = tk.StringVar(value=str(default))
        ttk.Entry(parent, textvariable=var, width=width).grid(row=row, column=col_entry, sticky="w", padx=6, pady=4)
        return var

    def _build_tab_straight(self, root):
        r = 0; self.st['x_start'] = self._ent(root, "X Start (mm)", 130.0, r); r+=1
        self.st['y_start'] = self._ent(root, "Y Start (mm)", 75.0,  r); r+=1
        self.st['length_x'] = self._ent(root, "Path Length X (mm)", 60.0, r); r+=1
        self.st['z_first'] = self._ent(root, "First Z (mm)", 0.8, r); r+=1
        self.st['z_step'] = self._ent(root, "Layer Height (mm)", 0.10, r); r+=1
        self.st['z_final'] = self._ent(root, "Final Z (mm)", 10.0, r); r+=1
        self.st['feed_dep'] = self._ent(root, "Deposition Feed F", 1000, r); r+=1
        self.st['feed_z'] = self._ent(root, "Z Feed F", 300, r); r+=1
        self.st['feed_travel']= self._ent(root, "Travel Feed F", 6000, r); r+=1
        self.st['dwell_ms'] = self._ent(root, "Dwell after engage (ms)", 200, r); r+=1
        self.st['fan'] = self._ent(root, "Fan (0–255)", 255, r); r+=1
        self.st['spindle'] = self._ent(root, "Spindle RPM", 30000, r); r+=1
        
        ttk.Label(root, text="Extrusion Mode").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.st['e_mode'] = tk.StringVar(value="x")
        ttk.Combobox(root, textvariable=self.st['e_mode'], values=["x","volume"], state="readonly", width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4); r+=1
        
        self.st['bead_width']= self._ent(root, "Bead width (mm)", 1.0, r); r+=1
        self.st['wire_diam'] = self._ent(root, "Wire diameter (mm)", 0.50, r); r+=1
        self.st['lead_in']   = self._ent(root, "Lead-in (mm, dry)", 0.0, r); r+=1
        self.st['runout']    = self._ent(root, "Runout (mm, no E)", 2.0, r); r+=1
        self.st['retract']   = self._ent(root, "Retract at end (mm)", 2.0, r); r+=1
        self.st['use_z_dive_cut'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(root, text="Z-dive cut at end", variable=self.st['use_z_dive_cut']).grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.st['z_dive_amount'] = self._ent(root, "Z-dive amount (mm)", 0.2, r, col_label=1, col_entry=2); r+=1
        
        ttk.Separator(root).grid(row=r, column=0, columnspan=3, sticky="we", padx=6, pady=6); r+=1
        self.st['multitrack'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(root, text="Enable multitrack", variable=self.st['multitrack']).grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.st['track_count']= self._ent(root, "Tracks per layer", 5, r, col_label=1, col_entry=2); r+=1
        self.st['overlap_frac']= self._ent(root, "Overlap fraction", 0.333, r); r+=1
        self.st['serpentine_y']= tk.BooleanVar(value=False)
        ttk.Checkbutton(root, text="Serpentine Y order", variable=self.st['serpentine_y']).grid(row=r, column=0, sticky="w", padx=6, pady=4); r+=1
        ttk.Button(root, text="Generate G-code…", command=self._gen_straight).grid(row=r, column=0, sticky="w", padx=6, pady=10)

    def _build_tab_dots(self, root):
        r = 0; self.dot['x_start'] = self._ent(root, "X (fixed)", 100.0, r); r+=1
        self.dot['y_start'] = self._ent(root, "Y (fixed)", 50.0,  r); r+=1
        self.dot['z_first'] = self._ent(root, "First Z (mm)", 0.8,   r); r+=1
        self.dot['z_step'] = self._ent(root, "Layer Height (mm)", 0.125, r); r+=1
        self.dot['z_final'] = self._ent(root, "Final Z (mm)", 10.0, r); r+=1
        self.dot['feed_dep'] = self._ent(root, "Deposition Feed F", 1000, r); r+=1
        self.dot['feed_z'] = self._ent(root, "Z Feed F", 300, r); r+=1
        self.dot['feed_travel']= self._ent(root, "Travel Feed F", 6000, r); r+=1
        self.dot['dwell_ms'] = self._ent(root, "Dwell after engage (ms)", 200, r); r+=1
        self.dot['fan'] = self._ent(root, "Fan (0–255)", 255, r); r+=1
        self.dot['spindle'] = self._ent(root, "Spindle RPM", 30000, r); r+=1
        self.dot['e_pulse'] = self._ent(root, "E pulse per dot (+)", 8.0, r); r+=1
        self.dot['e_retract'] = self._ent(root, "E retract per dot (−)", 1.0, r); r+=1
        ttk.Button(root, text="Generate G-code…", command=self._gen_dots).grid(row=r, column=0, sticky="w", padx=6, pady=10)

    def _build_tab_raster(self, root):
        r=0; self.rs['x_start'] = self._ent(root, "Start X", 130.0, r); r+=1
        self.rs['y_start'] = self._ent(root, "Start Y", 120.0, r); r+=1
        self.rs['x_stroke'] = self._ent(root, "Stroke length in −X", 5.0, r); r+=1
        self.rs['y_span'] = self._ent(root, "Total Y span", 6.0, r); r+=1
        self.rs['dy_step'] = self._ent(root, "Y step per stroke", 0.33, r); r+=1
        self.rs['z_first'] = self._ent(root, "First Z", 0.8, r); r+=1
        self.rs['z_step'] = self._ent(root, "Layer Height", 0.10, r); r+=1
        self.rs['z_final'] = self._ent(root, "Final Z", 1.6, r); r+=1
        self.rs['feed_dep'] = self._ent(root, "Deposition Feed F", 1000, r); r+=1
        self.rs['feed_z'] = self._ent(root, "Z Feed F", 300, r); r+=1
        self.rs['feed_travel'] = self._ent(root, "Travel Feed F", 6000, r); r+=1
        self.rs['dwell_ms'] = self._ent(root, "Dwell at engage (ms)", 200, r); r+=1
        self.rs['fan'] = self._ent(root, "Fan (0–255)", 255, r); r+=1
        self.rs['spindle'] = self._ent(root, "Spindle RPM", 30000, r); r+=1
        self.rs['e_mode'] = tk.StringVar(value="x")
        ttk.Label(root, text="Extrusion Mode").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(root, textvariable=self.rs['e_mode'], values=["x","volume"], state="readonly", width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4); r+=1
        self.rs['bead_width'] = self._ent(root, "Bead width", 1.0, r); r+=1
        self.rs['wire_diam'] = self._ent(root, "Wire diameter", 0.50, r); r+=1
        self.rs['runout'] = self._ent(root, "Runout", 1.0, r); r+=1
        self.rs['retract'] = self._ent(root, "Retract", 2.0, r); r+=1
        ttk.Button(root, text="Generate G-code…", command=self._gen_raster).grid(row=r, column=0, sticky="w", padx=6, pady=10)

    def _build_tab_drift(self, root):
        r=0; self.df['x_start'] = self._ent(root, "Start X", 130.0, r); r+=1
        self.df['y_start'] = self._ent(root, "Start Y", 120.0, r); r+=1
        self.df['x_total'] = self._ent(root, "Total distance in −X", 60.0, r); r+=1
        self.df['y_drift'] = self._ent(root, "Total Y drift", 6.0, r); r+=1
        self.df['seg_dx'] = self._ent(root, "Segment length dx", 0.5, r); r+=1
        self.df['z_first'] = self._ent(root, "First Z", 0.8, r); r+=1
        self.df['z_step'] = self._ent(root, "Layer Height", 0.10, r); r+=1
        self.df['z_final'] = self._ent(root, "Final Z", 1.6, r); r+=1
        self.df['feed_dep'] = self._ent(root, "Deposition Feed F", 1000, r); r+=1
        self.df['feed_z'] = self._ent(root, "Z Feed F", 300, r); r+=1
        self.df['feed_travel']= self._ent(root, "Travel Feed F", 6000, r); r+=1
        self.df['dwell_ms'] = self._ent(root, "Dwell at engage (ms)", 200, r); r+=1
        self.df['fan'] = self._ent(root, "Fan (0–255)", 255, r); r+=1
        self.df['spindle'] = self._ent(root, "Spindle RPM", 30000, r); r+=1
        self.df['e_mode'] = tk.StringVar(value="x")
        ttk.Label(root, text="Extrusion Mode").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(root, textvariable=self.df['e_mode'], values=["x","volume"], state="readonly", width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4); r+=1
        self.df['bead_width'] = self._ent(root, "Bead width", 1.0, r); r+=1
        self.df['wire_diam'] = self._ent(root, "Wire diameter", 0.50, r); r+=1
        self.df['runout'] = self._ent(root, "Runout", 2.0, r); r+=1
        self.df['retract'] = self._ent(root, "Retract", 2.0, r); r+=1
        ttk.Button(root, text="Generate G-code…", command=self._gen_drift).grid(row=r, column=0, sticky="w", padx=6, pady=10)

    def _build_tab_overhang(self, root):
        r=0; self.oh['x_start'] = self._ent(root, "Start X", 130.0, r); r+=1
        self.oh['y_base'] = self._ent(root, "Base Y", 75.0, r); r+=1
        self.oh['length_x'] = self._ent(root, "Track length (−X)", 40.0, r); r+=1
        self.oh['z_first'] = self._ent(root, "First Z", 0.8, r); r+=1
        self.oh['z_offsets_csv']= self._ent(root, "Z offsets (CSV)", "0.10,0.20,0.30,0.40,0.50", r); r+=1
        self.oh['y_offsets_csv']= self._ent(root, "Y offsets (CSV)", "", r); r+=1
        self.oh['y_step'] = self._ent(root, "Y step (if CSV blank)", 0.25, r); r+=1
        self.oh['e_mode'] = tk.StringVar(value="x")
        ttk.Label(root, text="Extrusion Mode").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(root, textvariable=self.oh['e_mode'], values=["x","volume"], state="readonly", width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4); r+=1
        self.oh['bead_width'] = self._ent(root, "Bead width", 1.0, r); r+=1
        self.oh['wire_diam'] = self._ent(root, "Wire diameter", 0.50, r); r+=1
        self.oh['layer_height']= self._ent(root, "Layer height for volume", 0.10, r); r+=1
        self.oh['feed_dep'] = self._ent(root, "Deposition Feed F", 1000, r); r+=1
        self.oh['feed_z'] = self._ent(root, "Z Feed F", 300, r); r+=1
        self.oh['feed_travel']= self._ent(root, "Travel Feed F", 6000, r); r+=1
        self.oh['dwell_ms'] = self._ent(root, "Dwell at engage (ms)", 200, r); r+=1
        self.oh['fan'] = self._ent(root, "Fan (0–255)", 255, r); r+=1
        self.oh['spindle'] = self._ent(root, "Spindle RPM", 30000, r); r+=1
        self.oh['runout'] = self._ent(root, "Runout", 2.0, r); r+=1
        self.oh['retract'] = self._ent(root, "Retract", 2.0, r); r+=1
        ttk.Button(root, text="Generate G-code…", command=self._gen_overhang).grid(row=r, column=0, sticky="w", padx=6, pady=10)

    # -- Material Logic (Copied) --
    def toggle_material(self):
        current = self.common.get('material').get()
        target = "Aluminum 1100-O (Ø0.50 mm)" if "Steel" in current else "Steel 1008 (Ø0.356 mm)"
        self.apply_material_preset(target)

    def apply_material_preset(self, name):
        self.common['material'].set(name) # Update combo
        if "Aluminum" in name:
            defaults = {"feed_dep":"1000","fan":"255","spindle":"30000"}
            self.bed_temp.set("110"); self.bed_dwell.set("2000")
            self.hotend_temp.set("0"); self.wait_hotend.set(False); self.hotend_dwell.set("0")
            self.allow_cold_extrude.set(True); self.min_e_temp.set("50")
            if hasattr(self, 'fixture_base_z'): self.fixture_base_z.set("62.15")
            if hasattr(self, 'fixture_approach_z'): self.fixture_approach_z.set("0.8")
            if hasattr(self, 'fixture_apply_to_layers'): self.fixture_apply_to_layers.set(True)
            if hasattr(self, 'fixture_first_move_at_approach'): self.fixture_first_move_at_approach.set(True)
        else:
            defaults = {"feed_dep":"180","fan":"0","spindle":"30000"}
            self.bed_temp.set("80"); self.bed_dwell.set("2000")
            self.hotend_temp.set("0"); self.wait_hotend.set(False); self.hotend_dwell.set("0")
            self.allow_cold_extrude.set(True); self.min_e_temp.set("50")
        for group in [self.st, self.rs, self.df, self.dot, self.oh]:
            for k,v in defaults.items():
                if k in group:
                    try: group[k].set(v)
                    except Exception: pass

    # -- Slicer Generator Callbacks (Copied logic) --
    def _common_params(self):
        P = {
            'mode': self.mode.get(),
            'feed_travel': 6000, 'feed_z': 300, 'feed_dep': 1000,
            'spindle': 30000, 'fan': 255, 'travel_z': 10.0,
            'dwell_ms': 200, 'runout': 2.0, 'retract': 2.0
        }
        P['bed_temp'] = float(self.bed_temp.get() or 0)
        P['wait_bed'] = bool(self.wait_bed.get())
        P['bed_dwell_ms'] = float(self.bed_dwell.get() or 0)
        ht = int(float(self.hotend_temp.get() or 0))
        P['hotend_temp'] = max(0, min(280, ht))
        P['wait_hotend'] = bool(self.wait_hotend.get())
        P['hotend_dwell_ms'] = float(self.hotend_dwell.get() or 0)
        P['allow_cold_extrude'] = bool(self.allow_cold_extrude.get())
        P['min_e_temp'] = float(self.min_e_temp.get() or 0)
        P['fixture_base_z'] = float(self.fixture_base_z.get() or 0.0)
        P['fixture_approach_z'] = float(self.fixture_approach_z.get() or 0.8)
        P['fixture_apply_to_layers'] = bool(self.fixture_apply_to_layers.get())
        P['fixture_first_move_at_approach'] = bool(self.fixture_first_move_at_approach.get())
        return P

    def _save_gcode(self, text, default_name):
        mode = self.mode.get().upper()
        default_name = default_name.replace("MODE", mode)
        fpath = filedialog.asksaveasfilename(defaultextension=".gcode", initialfile=default_name)
        if fpath:
            with open(fpath, "w", encoding="utf-8") as f: f.write(text)
            messagebox.showinfo("Saved", fpath)

    def _gen_straight(self):
        try:
            P = self._common_params()
            P.update({
                'x_start': float(self.st['x_start'].get()), 'y_start': float(self.st['y_start'].get()),
                'length_x': float(self.st['length_x'].get()), 'z_first': float(self.st['z_first'].get()),
                'z_step': float(self.st['z_step'].get()), 'z_final': float(self.st['z_final'].get()),
                'feed_dep': float(self.st['feed_dep'].get()), 'feed_z': float(self.st['feed_z'].get()),
                'feed_travel': float(self.st['feed_travel'].get()), 'dwell_ms': float(self.st['dwell_ms'].get()),
                'fan': float(self.st['fan'].get()), 'spindle': float(self.st['spindle'].get()),
                'e_mode': self.st['e_mode'].get(), 'bead_width': float(self.st['bead_width'].get()),
                'wire_diam': float(self.st['wire_diam'].get()), 'lead_in': float(self.st['lead_in'].get()),
                'runout': float(self.st['runout'].get()), 'retract': float(self.st['retract'].get()),
                'use_z_dive_cut': bool(self.st['use_z_dive_cut'].get()), 'z_dive_amount': float(self.st['z_dive_amount'].get()),
                'multitrack': bool(self.st['multitrack'].get()), 'track_count': float(self.st['track_count'].get()),
                'overlap_frac': float(self.st['overlap_frac'].get()), 'serpentine_y': bool(self.st['serpentine_y'].get()),
            })
            gc = gen_straight_multitrack(P); self._save_gcode(gc, "straight_multitrack_MODE.gcode")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _gen_dots(self):
        try:
            P = self._common_params()
            P.update({
                'x_start': float(self.dot['x_start'].get()), 'y_start': float(self.dot['y_start'].get()),
                'z_first': float(self.dot['z_first'].get()), 'z_step': float(self.dot['z_step'].get()),
                'z_final': float(self.dot['z_final'].get()), 'feed_dep': float(self.dot['feed_dep'].get()),
                'feed_z': float(self.dot['feed_z'].get()), 'feed_travel': float(self.dot['feed_travel'].get()),
                'dwell_ms': float(self.dot['dwell_ms'].get()), 'fan': float(self.dot['fan'].get()),
                'spindle': float(self.dot['spindle'].get()), 'e_pulse': float(self.dot['e_pulse'].get()),
                'e_retract': float(self.dot['e_retract'].get()),
            })
            gc = gen_dot_stack(P); self._save_gcode(gc, "dot_stack_MODE.gcode")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _gen_raster(self):
        try:
            P = self._common_params()
            P.update({
                'x_start': float(self.rs['x_start'].get()), 'y_start': float(self.rs['y_start'].get()),
                'x_stroke': float(self.rs['x_stroke'].get()), 'y_span': float(self.rs['y_span'].get()),
                'dy_step': float(self.rs['dy_step'].get()), 'z_first': float(self.rs['z_first'].get()),
                'z_step': float(self.rs['z_step'].get()), 'z_final': float(self.rs['z_final'].get()),
                'feed_dep': float(self.rs['feed_dep'].get()), 'feed_z': float(self.rs['feed_z'].get()),
                'feed_travel': float(self.rs['feed_travel'].get()), 'dwell_ms': float(self.rs['dwell_ms'].get()),
                'fan': float(self.rs['fan'].get()), 'spindle': float(self.rs['spindle'].get()),
                'e_mode': self.rs['e_mode'].get(), 'bead_width': float(self.rs['bead_width'].get()),
                'wire_diam': float(self.rs['wire_diam'].get()), 'runout': float(self.rs['runout'].get()),
                'retract': float(self.rs['retract'].get()),
            })
            gc = gen_sideways_micro_raster(P); self._save_gcode(gc, "sideways_micro_raster_MODE.gcode")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _gen_drift(self):
        try:
            P = self._common_params()
            P.update({
                'x_start': float(self.df['x_start'].get()), 'y_start': float(self.df['y_start'].get()),
                'x_total': float(self.df['x_total'].get()), 'y_drift': float(self.df['y_drift'].get()),
                'seg_dx': float(self.df['seg_dx'].get()), 'z_first': float(self.df['z_first'].get()),
                'z_step': float(self.df['z_step'].get()), 'z_final': float(self.df['z_final'].get()),
                'feed_dep': float(self.df['feed_dep'].get()), 'feed_z': float(self.df['feed_z'].get()),
                'feed_travel': float(self.df['feed_travel'].get()), 'dwell_ms': float(self.df['dwell_ms'].get()),
                'fan': float(self.df['fan'].get()), 'spindle': float(self.df['spindle'].get()),
                'e_mode': self.df['e_mode'].get(), 'bead_width': float(self.df['bead_width'].get()),
                'wire_diam': float(self.df['wire_diam'].get()), 'runout': float(self.df['runout'].get()),
                'retract': float(self.df['retract'].get()),
            })
            gc = gen_diagonal_drift(P); self._save_gcode(gc, "diagonal_drift_MODE.gcode")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _gen_overhang(self):
        try:
            P = self._common_params()
            P.update({
                'x_start': float(self.oh['x_start'].get()), 'y_base': float(self.oh['y_base'].get()),
                'length_x': float(self.oh['length_x'].get()), 'z_first': float(self.oh['z_first'].get()),
                'z_offsets_csv': self.oh['z_offsets_csv'].get(), 'y_offsets_csv': self.oh['y_offsets_csv'].get(),
                'y_step': float(self.oh['y_step'].get()), 'e_mode': self.oh['e_mode'].get(),
                'bead_width': float(self.oh['bead_width'].get()), 'wire_diam': float(self.oh['wire_diam'].get()),
                'layer_height': float(self.oh['layer_height'].get()), 'feed_dep': float(self.oh['feed_dep'].get()),
                'feed_z': float(self.oh['feed_z'].get()), 'feed_travel': float(self.oh['feed_travel'].get()),
                'dwell_ms': float(self.oh['dwell_ms'].get()), 'fan': float(self.oh['fan'].get()),
                'spindle': float(self.oh['spindle'].get()), 'runout': float(self.oh['runout'].get()),
                'retract': float(self.oh['retract'].get()),
            })
            gc = gen_overhang_tests(P); self._save_gcode(gc, "overhang_tests_MODE.gcode")
        except Exception as e: messagebox.showerror("Error", str(e))

    # -------------------------------------------------------------
    # MONITOR UI BUILDER (New Functionality)
    # -------------------------------------------------------------
    def build_monitor_tab(self, parent):
        # Config
        f_conf = ttk.LabelFrame(parent, text="Connection & Logging")
        f_conf.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(f_conf, text="Port:").pack(side="left", padx=5)
        ttk.Entry(f_conf, textvariable=self.var_port, width=8).pack(side="left")
        
        ttk.Label(f_conf, text="File:").pack(side="left", padx=(20, 5))
        ttk.Entry(f_conf, textvariable=self.var_log_path, width=40).pack(side="left", fill="x", expand=True)
        ttk.Button(f_conf, text="Browse", command=self.browse_log_file).pack(side="left", padx=5)

        # Controls
        f_btns = ttk.Frame(parent)
        f_btns.pack(fill="x", padx=20, pady=10)
        self.btn_start = tk.Button(f_btns, text="START MONITORING", bg="#d9ffdb", font=("Arial", 12, "bold"), command=self.start_monitor)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_stop = tk.Button(f_btns, text="STOP", bg="#ffd9d9", font=("Arial", 12, "bold"), state="disabled", command=self.stop_monitor)
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=5)

        # Dashboard
        f_dash = tk.Frame(parent, bg="#f5f5f5", relief="sunken", bd=1)
        f_dash.pack(fill="both", expand=True, padx=20, pady=10)

        # Gauge
        self.gauge = SpeedometerGauge(f_dash, width=500, height=300, bg="#f5f5f5", highlightthickness=0)
        self.gauge.pack(pady=20)

        # Digital Readouts
        f_digi = tk.Frame(f_dash, bg="#f5f5f5")
        f_digi.pack(pady=10)
        tk.Label(f_digi, text="Control Voltage:", bg="#f5f5f5", font=("Arial", 12)).grid(row=0, column=0, padx=20)
        tk.Label(f_digi, textvariable=self.var_volt, bg="#f5f5f5", fg="green", font=("Arial", 24, "bold")).grid(row=1, column=0, padx=20)
        tk.Label(f_digi, text="Last Update:", bg="#f5f5f5", font=("Arial", 12)).grid(row=0, column=1, padx=20)
        tk.Label(f_digi, textvariable=self.var_time, bg="#f5f5f5", font=("Consolas", 18)).grid(row=1, column=1, padx=20)

        # Status Bar
        tk.Label(parent, textvariable=self.var_status, relief="sunken", anchor="w").pack(side="bottom", fill="x")

    def browse_log_file(self):
        f = filedialog.asksaveasfilename(initialfile="motor_log.csv", defaultextension=".csv")
        if f: self.var_log_path.set(f)

    def start_monitor(self):
        port = self.var_port.get()
        path = self.var_log_path.get()
        
        try:
            self.serial_port = serial.Serial(port, 115200, timeout=1)
            self.serial_port.dtr = False; self.serial_port.rts = False
            
            self.csv_file = open(path, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(["Timestamp_PC", "ESP_Millis", "Voltage_V", "RPM"])
            
            self.is_logging = True
            self.stop_thread = False
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")
            self.var_status.set(f"Logging to {os.path.basename(path)}")
            
            self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.thread.start()
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def stop_monitor(self):
        self.stop_thread = True
        self.var_status.set("Stopping...")

    def monitor_loop(self):
        time.sleep(2)
        if self.serial_port: self.serial_port.reset_input_buffer()
        while not self.stop_thread:
            try:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if not line or "START" in line: continue
                    parts = line.split(',')
                    if len(parts) == 3:
                        now = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        v_str = parts[1].strip()
                        rpm = int(parts[2].strip())
                        if self.csv_file:
                            self.csv_writer.writerow([now, parts[0], v_str, rpm])
                            self.csv_file.flush()
                        self.after(0, self.update_dashboard, v_str, rpm, now)
                else:
                    time.sleep(0.01)
            except: break
        self.cleanup_monitor()

    def update_dashboard(self, v, r, t):
        self.var_volt.set(f"{v} V")
        self.var_time.set(t)
        self.gauge.set_value(r)

    def cleanup_monitor(self):
        if self.serial_port: self.serial_port.close()
        if self.csv_file: self.csv_file.close()
        self.is_logging = False
        self.after(0, lambda: [
            self.btn_start.config(state="normal"),
            self.btn_stop.config(state="disabled"),
            self.var_status.set("Monitor Stopped")
        ])

if __name__ == "__main__":
    app = AFRBControlCenter()
    app.mainloop()