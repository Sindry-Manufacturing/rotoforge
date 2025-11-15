
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "AF-RB Playground – G-code Generator (with Bed Preheat + Overhang Tests)"

# ---------- Helpers ----------
def parse_csv_floats(s):
    try:
        parts = [p.strip() for p in str(s).split(",") if p.strip() != ""]
        return [float(p) for p in parts] if parts else []
    except Exception:
        return []

def gcode_header(params):
    """
    Common header with optional bed preheat & wait:
      - M140 S{bed_temp}, optional M190 S{bed_temp}, optional dwell after ready
      - then homing, fan, spindle, spin-up dwell
    Expects keys: fan, feed_travel, spindle, bed_temp, wait_bed, bed_dwell_ms
    """
    lines = []
    L = lines.append
    L("G90"); L("G21"); L("M83"); L("T0"); L("G92 E0")
    # Bed heating (optional)
    bed = float(params.get('bed_temp', 0) or 0)
    wait_bed = bool(params.get('wait_bed', False))
    bed_dwell_ms = int(float(params.get('bed_dwell_ms', 0) or 0))
    if bed > 0:
        L(f"M140 S{int(bed)}")
        if wait_bed:
            L(f"M190 S{int(bed)}")   # wait for bed to reach temp
            if bed_dwell_ms > 0:
                L(f"G4 P{bed_dwell_ms}")
    # Safety
    L("M104 S0"); L("M140 S0") if bed <= 0 else None  # keep bed set if heating
    L("M302 S0")  # allow 'cold' extrusion (wire feed)
    L("G28")
    # Environment
    L(f"M106 S{int(params.get('fan', 0))}")
    L(f"G0 Z{float(params.get('travel_z', 10)):.3f} F{int(params.get('feed_travel', 6000))}")
    L(f"M3 S{int(params.get('spindle', 30000))}")
    L("G4 P2000")
    return lines

def gcode_footer(params):
    return ["M5", "M107", f"G0 Z{float(params.get('travel_z',10)):.3f} F{int(params.get('feed_travel',6000))}"]

def compute_e_per_mm(e_mode, bead_width, layer_height, wire_diam):
    if e_mode == "x":
        return 1.0
    # volume match
    wire_area = math.pi * (wire_diam/2.0)**2 if wire_diam > 0 else 0
    bead_area = bead_width * layer_height
    return bead_area / wire_area if wire_area > 0 else 1.0

# ---------- Generators ----------
def gen_straight_multitrack(P):
    x_start = P['x_start']; y_start = P['y_start']; length_x = P['length_x']
    z_first = P['z_first']; z_step = P['z_step']; z_final = P['z_final']
    feed_dep = P['feed_dep']; feed_z = P['feed_z']; feed_travel = P['feed_travel']
    dwell_ms = P['dwell_ms']; fan = P['fan']; spindle = P['spindle']
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

    z = z_first; layer_idx = 0
    while z <= z_final + 1e-9:
        y_list = y_tracks_up if (layer_idx % 2 == 0 or not serpentine_y) else list(reversed(y_tracks_up))
        for y in y_list:
            lines.append(f"G0 X{x_lead_in_start:.3f} Y{y:.3f} Z{P['travel_z']:.3f} F{int(feed_travel)}")
            lines.append(f"G1 Z{z:.3f} F{int(feed_z)}")
            if dwell_ms > 0: lines.append(f"G4 P{int(dwell_ms)}")
            if lead_in > 0: lines.append(f"G1 X{x_start:.3f} F{int(feed_dep)}")
            E = e_per_mm * (x_start - x_end)
            lines.append(f"G1 X{x_end:.3f} E{E:.3f} F{int(feed_dep)}")
            if runout > 0: lines.append(f"G1 X{x_end_runout:.3f} F{int(feed_dep)}")
            if use_z_dive_cut and z_dive_amount > 0:
                lines += ["G91", f"G1 Z{-abs(z_dive_amount):.3f} F{int(feed_z)}", "G90"]
            if retract != 0: lines.append(f"G1 E{-abs(retract):.3f} F600")
            lines.append(f"G0 Z{P['travel_z']:.3f} F{int(feed_travel)}")
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
    z = z_first
    while z <= z_final + 1e-9:
        lines.append(f"G0 X{x:.3f} Y{y:.3f} Z{P['travel_z']:.3f} F{int(feed_travel)}")
        lines.append(f"G1 Z{z:.3f} F{int(feed_z)}")
        if dwell_ms > 0: lines.append(f"G4 P{int(dwell_ms)}")
        lines.append(f"G1 E{e_pulse:.3f} F{int(feed_dep)}")
        if e_retract != 0: lines.append(f"G1 E{-abs(e_retract):.3f} F600")
        lines.append(f"G0 Z{P['travel_z']:.3f} F{int(feed_travel)}")
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
    z = z_first
    while z <= z_final + 1e-9:
        y = y0
        for _ in range(n_tracks):
            lines.append(f"G0 X{x_start:.3f} Y{y:.3f} Z{P['travel_z']:.3f} F{int(feed_travel)}")
            lines.append(f"G1 Z{z:.3f} F{int(feed_z)}")
            if dwell_ms > 0: lines.append(f"G4 P{int(dwell_ms)}")
            lines.append(f"G1 X{x_end:.3f} E{e_per:.3f} F{int(feed_dep)}")
            if runout > 0: lines.append(f"G1 X{x_end_runout:.3f} F{int(feed_dep)}")
            if retract != 0: lines.append(f"G1 E{-abs(retract):.3f} F600")
            lines.append(f"G0 Z{P['travel_z']:.3f} F{int(feed_travel)}")
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
    z = z_first
    while z <= z_final + 1e-9:
        lines.append(f"G0 X{x_start:.3f} Y{y_start:.3f} Z{P['travel_z']:.3f} F{int(feed_travel)}")
        lines.append(f"G1 Z{z:.3f} F{int(feed_z)}")
        if dwell_ms > 0: lines.append(f"G4 P{int(dwell_ms)}")
        x = x_start; y = y_start
        e_per_seg = compute_e_per_mm(e_mode, bead_width, z_step, wire_diam) * abs(dx)
        for _ in range(n_segments):
            x -= dx; y += dy
            lines.append(f"G1 X{x:.3f} Y{y:.3f} E{e_per_seg:.3f} F{int(feed_dep)}")
        if runout > 0: lines.append(f"G1 X{(x - runout):.3f} F{int(feed_dep)}")
        if retract != 0: lines.append(f"G1 E{-abs(retract):.3f} F600")
        lines.append(f"G0 Z{P['travel_z']:.3f} F{int(feed_travel)}")
        lines.append(f"G0 X{x_start:.3f} Y{y_start:.3f} F{int(feed_travel)}")
        lines.append("G92 E0")
        z += z_step
    lines += gcode_footer(P)
    return "\n".join(lines)

def gen_overhang_tests(P):
    """
    Generate overhang test lines: one -X pass per specified Z layer, each with a Y offset from base.
    Params:
      x_start, y_base, length_x
      z_first, z_offsets_csv (CSV of offsets added to z_first)
      y_offsets_csv (CSV) OR y_step (single float step applied per index)
      e_mode ('x' or 'volume'), bead_width, layer_height(for volume), wire_diam
      feed_dep, feed_z, feed_travel, dwell_ms, runout, retract
      travel_z, fan, spindle, bed_temp, wait_bed, bed_dwell_ms
    """
    x_start = P['x_start']; y_base = P['y_base']; length_x = P['length_x']
    z_first = P['z_first']; z_offsets = parse_csv_floats(P['z_offsets_csv'])
    if not z_offsets:
        z_offsets = [0.10, 0.20, 0.30, 0.40, 0.50]
    y_list = parse_csv_floats(P['y_offsets_csv'])
    if not y_list:
        step = float(P['y_step'])
        y_list = [i * step for i in range(len(z_offsets))]
    # Align lengths
    n = min(len(z_offsets), len(y_list))
    z_offsets = z_offsets[:n]; y_list = y_list[:n]

    x_end = x_start - length_x
    e_per_mm = compute_e_per_mm(P['e_mode'], P['bead_width'], P['layer_height'], P['wire_diam'])
    feed_dep = P['feed_dep']; feed_z = P['feed_z']; feed_travel = P['feed_travel']
    dwell_ms = P['dwell_ms']; runout = P['runout']; retract = P['retract']

    lines = []; lines += gcode_header(P)
    for i in range(n):
        z = z_first + z_offsets[i]
        y = y_base + y_list[i]
        lines.append(f"G0 X{x_start:.3f} Y{y:.3f} Z{P['travel_z']:.3f} F{int(feed_travel)}")
        lines.append(f"G1 Z{z:.3f} F{int(feed_z)}")
        if dwell_ms > 0: lines.append(f"G4 P{int(dwell_ms)}")
        E = e_per_mm * (x_start - x_end)
        lines.append(f"G1 X{x_end:.3f} E{E:.3f} F{int(feed_dep)}")
        if runout > 0: lines.append(f"G1 X{(x_end - runout):.3f} F{int(feed_dep)}")
        if retract != 0: lines.append(f"G1 E{-abs(retract):.3f} F600")
        lines.append(f"G0 Z{P['travel_z']:.3f} F{int(feed_travel)}")
        lines.append("G92 E0")
    lines += gcode_footer(P)
    return "\n".join(lines)

# ---------- GUI ----------
class Playground(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x920")
        self.resizable(True, True)
        self.common = {}
        self._build_topbar()
        self._build_tabs()
        self.apply_material_preset("Aluminum 1100-O (Ø0.50 mm)")

    # ---- UI builders
    def _build_topbar(self):
        pad = {'padx': 8, 'pady': 6}
        f = ttk.Frame(self); f.pack(fill="x")

        ttk.Label(f, text="Material Preset").pack(side="left", **pad)
        self.common['material'] = tk.StringVar(value="Aluminum 1100-O (Ø0.50 mm)")
        self.preset_combo = ttk.Combobox(f, textvariable=self.common['material'],
                                         values=["Aluminum 1100-O (Ø0.50 mm)","Steel 1008 (Ø0.356 mm)"],
                                         state="readonly", width=28)
        self.preset_combo.pack(side="left", **pad)
        self.preset_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_material_preset(self.common['material'].get()))
        ttk.Button(f, text="Toggle Steel/Aluminum", command=self.toggle_material).pack(side="left", padx=6)

        # Bed preheat controls
        ttk.Separator(f, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(f, text="Bed °C").pack(side="left"); self.bed_temp = tk.StringVar(value="0")
        ttk.Entry(f, textvariable=self.bed_temp, width=6).pack(side="left")
        self.wait_bed = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Wait (M190)", variable=self.wait_bed).pack(side="left")
        ttk.Label(f, text="Dwell ms").pack(side="left"); self.bed_dwell = tk.StringVar(value="2000")
        ttk.Entry(f, textvariable=self.bed_dwell, width=8).pack(side="left")

    def _build_tabs(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True)

        # Straight / Multitrack
        self.tab_straight = ttk.Frame(nb); nb.add(self.tab_straight, text="Straight / Multitrack")
        self._build_tab_straight(self.tab_straight)

        # Dot Stack
        self.tab_dots = ttk.Frame(nb); nb.add(self.tab_dots, text="Dot Stack")
        self._build_tab_dots(self.tab_dots)

        # Sideways Micro-Raster
        self.tab_raster = ttk.Frame(nb); nb.add(self.tab_raster, text="Sideways Micro-Raster")
        self._build_tab_raster(self.tab_raster)

        # Diagonal Drift
        self.tab_drift = ttk.Frame(nb); nb.add(self.tab_drift, text="Diagonal Drift")
        self._build_tab_drift(self.tab_drift)

        # Overhang Tests
        self.tab_overhang = ttk.Frame(nb); nb.add(self.tab_overhang, text="Overhang Tests")
        self._build_tab_overhang(self.tab_overhang)

    # ---- Common gatherer
    def _common_params(self):
        # Defaults
        defaults = {
            'feed_travel': 6000, 'feed_z': 300, 'feed_dep': 1000,
            'spindle': 30000, 'fan': 255, 'travel_z': 10.0,
            'dwell_ms': 200, 'runout': 2.0, 'retract': 2.0
        }
        P = dict(defaults)
        # Bed preheat
        P['bed_temp'] = float(self.bed_temp.get() or 0)
        P['wait_bed'] = bool(self.wait_bed.get())
        P['bed_dwell_ms'] = float(self.bed_dwell.get() or 0)
        return P

    # ---- Tab builders
    def _ent(self, parent, label, key, default, row, col_label=0, col_entry=1, width=12):
        ttk.Label(parent, text=label).grid(row=row, column=col_label, sticky="w", padx=6, pady=4)
        var = tk.StringVar(value=str(default))
        ttk.Entry(parent, textvariable=var, width=width).grid(row=row, column=col_entry, sticky="w", padx=6, pady=4)
        return var

    def _build_tab_straight(self, root):
        r = 0; self.st = {}
        self.st['x_start']   = self._ent(root, "X Start (mm)", "x_start", 130.0, r); r+=1
        self.st['y_start']   = self._ent(root, "Y Start (mm)", "y_start", 75.0,  r); r+=1
        self.st['length_x']  = self._ent(root, "Path Length X (mm)", "length_x", 60.0, r); r+=1
        self.st['z_first']   = self._ent(root, "First Z (mm)", "z_first", 0.8, r); r+=1
        self.st['z_step']    = self._ent(root, "Layer Height (mm)", "z_step", 0.10, r); r+=1
        self.st['z_final']   = self._ent(root, "Final Z (mm)", "z_final", 10.0, r); r+=1
        self.st['feed_dep']  = self._ent(root, "Deposition Feed F", "feed_dep", 1000, r); r+=1
        self.st['feed_z']    = self._ent(root, "Z Feed F", "feed_z", 300, r); r+=1
        self.st['feed_travel']= self._ent(root, "Travel Feed F", "feed_travel", 6000, r); r+=1
        self.st['dwell_ms']  = self._ent(root, "Dwell after engage (ms)", "dwell_ms", 200, r); r+=1
        self.st['fan']       = self._ent(root, "Fan (0–255)", "fan", 255, r); r+=1
        self.st['spindle']   = self._ent(root, "Spindle RPM", "spindle", 30000, r); r+=1
        # Extrusion & bead
        ttk.Label(root, text="Extrusion Mode").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.st['e_mode']    = tk.StringVar(value="x")
        ttk.Combobox(root, textvariable=self.st['e_mode'], values=["x","volume"], state="readonly", width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4); r+=1
        self.st['bead_width']= self._ent(root, "Bead width (mm)", "bead_width", 1.0, r); r+=1
        self.st['wire_diam'] = self._ent(root, "Wire diameter (mm)", "wire_diam", 0.50, r); r+=1
        # Pass controls
        self.st['lead_in']   = self._ent(root, "Lead-in (mm, dry)", "lead_in", 0.0, r); r+=1
        self.st['runout']    = self._ent(root, "Runout (mm, no E)", "runout", 2.0, r); r+=1
        self.st['retract']   = self._ent(root, "Retract at end (mm)", "retract", 2.0, r); r+=1
        self.st['use_z_dive_cut'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(root, text="Z-dive cut at end", variable=self.st['use_z_dive_cut']).grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.st['z_dive_amount'] = self._ent(root, "Z-dive amount (mm)", "z_dive_amount", 0.2, r, col_label=1, col_entry=2); r+=1
        # Multitrack
        ttk.Separator(root).grid(row=r, column=0, columnspan=3, sticky="we", padx=6, pady=6); r+=1
        self.st['multitrack'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(root, text="Enable multitrack", variable=self.st['multitrack']).grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.st['track_count']= self._ent(root, "Tracks per layer", "track_count", 5, r, col_label=1, col_entry=2); r+=1
        self.st['overlap_frac']= self._ent(root, "Overlap fraction (0..0.9)", "overlap_frac", 0.333, r); r+=1
        self.st['serpentine_y']= tk.BooleanVar(value=False)
        ttk.Checkbutton(root, text="Serpentine Y order", variable=self.st['serpentine_y']).grid(row=r, column=0, sticky="w", padx=6, pady=4); r+=1

        ttk.Button(root, text="Generate G-code…", command=self._gen_straight).grid(row=r, column=0, sticky="w", padx=6, pady=10)

    def _build_tab_dots(self, root):
        r = 0; self.dot = {}
        self.dot['x_start']   = self._ent(root, "X (fixed)", "x_start", 100.0, r); r+=1
        self.dot['y_start']   = self._ent(root, "Y (fixed)", "y_start", 50.0,  r); r+=1
        self.dot['z_first']   = self._ent(root, "First Z (mm)", "z_first", 0.8,   r); r+=1
        self.dot['z_step']    = self._ent(root, "Layer Height (mm)", "z_step", 0.125, r); r+=1
        self.dot['z_final']   = self._ent(root, "Final Z (mm)", "z_final", 10.0, r); r+=1
        self.dot['feed_dep']  = self._ent(root, "Deposition Feed F", "feed_dep", 1000, r); r+=1
        self.dot['feed_z']    = self._ent(root, "Z Feed F", "feed_z", 300, r); r+=1
        self.dot['feed_travel']= self._ent(root, "Travel Feed F", "feed_travel", 6000, r); r+=1
        self.dot['dwell_ms']  = self._ent(root, "Dwell after engage (ms)", "dwell_ms", 200, r); r+=1
        self.dot['fan']       = self._ent(root, "Fan (0–255)", "fan", 255, r); r+=1
        self.dot['spindle']   = self._ent(root, "Spindle RPM", "spindle", 30000, r); r+=1
        self.dot['e_pulse']   = self._ent(root, "E pulse per dot (+)", "e_pulse", 8.0, r); r+=1
        self.dot['e_retract'] = self._ent(root, "E retract per dot (−)", "e_retract", 1.0, r); r+=1
        ttk.Button(root, text="Generate G-code…", command=self._gen_dots).grid(row=r, column=0, sticky="w", padx=6, pady=10)

    def _build_tab_raster(self, root):
        r=0; self.rs = {}
        self.rs['x_start']    = self._ent(root, "Start X", "x_start", 130.0, r); r+=1
        self.rs['y_start']    = self._ent(root, "Start Y", "y_start", 120.0, r); r+=1
        self.rs['x_stroke']   = self._ent(root, "Stroke length in −X (mm)", "x_stroke", 5.0, r); r+=1
        self.rs['y_span']     = self._ent(root, "Total Y span (mm)", "y_span", 6.0, r); r+=1
        self.rs['dy_step']    = self._ent(root, "Y step per stroke (mm)", "dy_step", 0.33, r); r+=1
        self.rs['z_first']    = self._ent(root, "First Z (mm)", "z_first", 0.8,   r); r+=1
        self.rs['z_step']     = self._ent(root, "Layer Height (mm)", "z_step", 0.10, r); r+=1
        self.rs['z_final']    = self._ent(root, "Final Z (mm)", "z_final", 1.6,   r); r+=1
        self.rs['feed_dep']   = self._ent(root, "Deposition Feed F", "feed_dep", 1000, r); r+=1
        self.rs['feed_z']     = self._ent(root, "Z Feed F", "feed_z", 300, r); r+=1
        self.rs['feed_travel']= self._ent(root, "Travel Feed F", "feed_travel", 6000, r); r+=1
        self.rs['dwell_ms']   = self._ent(root, "Dwell after engage (ms)", "dwell_ms", 200, r); r+=1
        self.rs['fan']        = self._ent(root, "Fan (0–255)", "fan", 255, r); r+=1
        self.rs['spindle']    = self._ent(root, "Spindle RPM", "spindle", 30000, r); r+=1
        self.rs['e_mode']     = tk.StringVar(value="x")
        ttk.Label(root, text="Extrusion Mode").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(root, textvariable=self.rs['e_mode'], values=["x","volume"], state="readonly", width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4); r+=1
        self.rs['bead_width'] = self._ent(root, "Bead width (mm)", "bead_width", 1.0, r); r+=1
        self.rs['wire_diam']  = self._ent(root, "Wire diameter (mm)", "wire_diam", 0.50, r); r+=1
        self.rs['runout']     = self._ent(root, "Runout (mm, no E)", "runout", 1.0, r); r+=1
        self.rs['retract']    = self._ent(root, "Retract at end (mm)", "retract", 2.0, r); r+=1
        ttk.Button(root, text="Generate G-code…", command=self._gen_raster).grid(row=r, column=0, sticky="w", padx=6, pady=10)

    def _build_tab_drift(self, root):
        r=0; self.df = {}
        self.df['x_start']    = self._ent(root, "Start X", "x_start", 130.0, r); r+=1
        self.df['y_start']    = self._ent(root, "Start Y", "y_start", 120.0, r); r+=1
        self.df['x_total']    = self._ent(root, "Total distance in −X (mm)", "x_total", 60.0, r); r+=1
        self.df['y_drift']    = self._ent(root, "Total Y drift per pass (mm)", "y_drift", 6.0, r); r+=1
        self.df['seg_dx']     = self._ent(root, "Segment length dx (mm)", "seg_dx", 0.5, r); r+=1
        self.df['z_first']    = self._ent(root, "First Z (mm)", "z_first", 0.8,   r); r+=1
        self.df['z_step']     = self._ent(root, "Layer Height (mm)", "z_step", 0.10, r); r+=1
        self.df['z_final']    = self._ent(root, "Final Z (mm)", "z_final", 1.6,   r); r+=1
        self.df['feed_dep']   = self._ent(root, "Deposition Feed F", "feed_dep", 1000, r); r+=1
        self.df['feed_z']     = self._ent(root, "Z Feed F", "feed_z", 300, r); r+=1
        self.df['feed_travel']= self._ent(root, "Travel Feed F", "feed_travel", 6000, r); r+=1
        self.df['dwell_ms']   = self._ent(root, "Dwell after engage (ms)", "dwell_ms", 200, r); r+=1
        self.df['fan']        = self._ent(root, "Fan (0–255)", "fan", 255, r); r+=1
        self.df['spindle']    = self._ent(root, "Spindle RPM", "spindle", 30000, r); r+=1
        self.df['e_mode']     = tk.StringVar(value="x")
        ttk.Label(root, text="Extrusion Mode").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(root, textvariable=self.df['e_mode'], values=["x","volume"], state="readonly", width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4); r+=1
        self.df['bead_width'] = self._ent(root, "Bead width (mm)", "bead_width", 1.0, r); r+=1
        self.df['wire_diam']  = self._ent(root, "Wire diameter (mm)", "wire_diam", 0.50, r); r+=1
        self.df['runout']     = self._ent(root, "Runout (mm, no E)", "runout", 2.0, r); r+=1
        self.df['retract']    = self._ent(root, "Retract at end (mm)", "retract", 2.0, r); r+=1
        ttk.Button(root, text="Generate G-code…", command=self._gen_drift).grid(row=r, column=0, sticky="w", padx=6, pady=10)

    def _build_tab_overhang(self, root):
        r=0; self.oh = {}
        # Geometry
        self.oh['x_start']    = self._ent(root, "Start X (mm)", "x_start", 130.0, r); r+=1
        self.oh['y_base']     = self._ent(root, "Base Y (mm)", "y_base", 75.0, r); r+=1
        self.oh['length_x']   = self._ent(root, "Track length (−X) mm", "length_x", 40.0, r); r+=1
        # Z & layer set
        self.oh['z_first']    = self._ent(root, "First Z (mm)", "z_first", 0.8, r); r+=1
        self.oh['z_offsets_csv']= self._ent(root, "Z offsets from first Z (CSV mm)", "z_offsets_csv", "0.10,0.20,0.30,0.40,0.50", r); r+=1
        # Y offsets per layer
        self.oh['y_offsets_csv']= self._ent(root, "Y offsets per layer (CSV, mm; blank to use step)", "y_offsets_csv", "", r); r+=1
        self.oh['y_step']     = self._ent(root, "Y step per layer (mm, used if CSV blank)", "y_step", 0.25, r); r+=1
        # Extrusion
        ttk.Label(root, text="Extrusion Mode").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.oh['e_mode']     = tk.StringVar(value="x")
        ttk.Combobox(root, textvariable=self.oh['e_mode'], values=["x","volume"], state="readonly", width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4); r+=1
        self.oh['bead_width'] = self._ent(root, "Bead width (mm)", "bead_width", 1.0, r); r+=1
        self.oh['wire_diam']  = self._ent(root, "Wire diameter (mm)", "wire_diam", 0.50, r); r+=1
        self.oh['layer_height']= self._ent(root, "Layer height for volume mode (mm)", "layer_height", 0.10, r); r+=1
        # Process
        self.oh['feed_dep']   = self._ent(root, "Deposition Feed F", "feed_dep", 1000, r); r+=1
        self.oh['feed_z']     = self._ent(root, "Z Feed F", "feed_z", 300, r); r+=1
        self.oh['feed_travel']= self._ent(root, "Travel Feed F", "feed_travel", 6000, r); r+=1
        self.oh['dwell_ms']   = self._ent(root, "Dwell at engage (ms)", "dwell_ms", 200, r); r+=1
        self.oh['fan']        = self._ent(root, "Fan (0–255)", "fan", 255, r); r+=1
        self.oh['spindle']    = self._ent(root, "Spindle RPM", "spindle", 30000, r); r+=1
        self.oh['runout']     = self._ent(root, "Runout (mm, no E)", "runout", 2.0, r); r+=1
        self.oh['retract']    = self._ent(root, "Retract at end (mm)", "retract", 2.0, r); r+=1
        ttk.Button(root, text="Generate G-code…", command=self._gen_overhang).grid(row=r, column=0, sticky="w", padx=6, pady=10)

    # ---- Material presets
    def toggle_material(self):
        current = self.common.get('material').get()
        target = "Aluminum 1100-O (Ø0.50 mm)" if "Steel" in current else "Steel 1008 (Ø0.356 mm)"
        self.apply_material_preset(target)

    def apply_material_preset(self, name):
        # Only sets a few defaults; user can override per tab
        if "Aluminum" in name:
            defaults = {"feed_dep":"1000","fan":"255","spindle":"30000"}
            self.bed_temp.set("110")   # bed default enabled by you; set to 0 to disable
            self.bed_dwell.set("2000")
        else:
            defaults = {"feed_dep":"180","fan":"0","spindle":"30000"}
            self.bed_temp.set("80")
            self.bed_dwell.set("2000")
        # Apply to visible tabs
        for group in [getattr(self,"st",{}), getattr(self,"rs",{}), getattr(self,"df",{}), getattr(self,"dot",{}), getattr(self,"oh",{})]:
            for k,v in defaults.items():
                if k in group:
                    try: group[k].set(v)
                    except Exception: pass

    # ---- Generate handlers
    def _gen_straight(self):
        try:
            P = self._common_params()
            P.update({
                'x_start': float(self.st['x_start'].get()),
                'y_start': float(self.st['y_start'].get()),
                'length_x': float(self.st['length_x'].get()),
                'z_first': float(self.st['z_first'].get()),
                'z_step': float(self.st['z_step'].get()),
                'z_final': float(self.st['z_final'].get()),
                'feed_dep': float(self.st['feed_dep'].get()),
                'feed_z': float(self.st['feed_z'].get()),
                'feed_travel': float(self.st['feed_travel'].get()),
                'dwell_ms': float(self.st['dwell_ms'].get()),
                'fan': float(self.st['fan'].get()),
                'spindle': float(self.st['spindle'].get()),
                'e_mode': self.st['e_mode'].get(),
                'bead_width': float(self.st['bead_width'].get()),
                'wire_diam': float(self.st['wire_diam'].get()),
                'lead_in': float(self.st['lead_in'].get()),
                'runout': float(self.st['runout'].get()),
                'retract': float(self.st['retract'].get()),
                'use_z_dive_cut': bool(self.st['use_z_dive_cut'].get()),
                'z_dive_amount': float(self.st['z_dive_amount'].get()),
                'multitrack': bool(self.st['multitrack'].get()),
                'track_count': float(self.st['track_count'].get()),
                'overlap_frac': float(self.st['overlap_frac'].get()),
                'serpentine_y': bool(self.st['serpentine_y'].get()),
            })
            gc = gen_straight_multitrack(P); self._save_gcode(gc, "straight_multitrack.gcode")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _gen_dots(self):
        try:
            P = self._common_params()
            P.update({
                'x_start': float(self.dot['x_start'].get()),
                'y_start': float(self.dot['y_start'].get()),
                'z_first': float(self.dot['z_first'].get()),
                'z_step': float(self.dot['z_step'].get()),
                'z_final': float(self.dot['z_final'].get()),
                'feed_dep': float(self.dot['feed_dep'].get()),
                'feed_z': float(self.dot['feed_z'].get()),
                'feed_travel': float(self.dot['feed_travel'].get()),
                'dwell_ms': float(self.dot['dwell_ms'].get()),
                'fan': float(self.dot['fan'].get()),
                'spindle': float(self.dot['spindle'].get()),
                'e_pulse': float(self.dot['e_pulse'].get()),
                'e_retract': float(self.dot['e_retract'].get()),
            })
            gc = gen_dot_stack(P); self._save_gcode(gc, "dot_stack.gcode")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _gen_raster(self):
        try:
            P = self._common_params()
            P.update({
                'x_start': float(self.rs['x_start'].get()),
                'y_start': float(self.rs['y_start'].get()),
                'x_stroke': float(self.rs['x_stroke'].get()),
                'y_span': float(self.rs['y_span'].get()),
                'dy_step': float(self.rs['dy_step'].get()),
                'z_first': float(self.rs['z_first'].get()),
                'z_step': float(self.rs['z_step'].get()),
                'z_final': float(self.rs['z_final'].get()),
                'feed_dep': float(self.rs['feed_dep'].get()),
                'feed_z': float(self.rs['feed_z'].get()),
                'feed_travel': float(self.rs['feed_travel'].get()),
                'dwell_ms': float(self.rs['dwell_ms'].get()),
                'fan': float(self.rs['fan'].get()),
                'spindle': float(self.rs['spindle'].get()),
                'e_mode': self.rs['e_mode'].get(),
                'bead_width': float(self.rs['bead_width'].get()),
                'wire_diam': float(self.rs['wire_diam'].get()),
                'runout': float(self.rs['runout'].get()),
                'retract': float(self.rs['retract'].get()),
            })
            gc = gen_sideways_micro_raster(P); self._save_gcode(gc, "sideways_micro_raster.gcode")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _gen_drift(self):
        try:
            P = self._common_params()
            P.update({
                'x_start': float(self.df['x_start'].get()),
                'y_start': float(self.df['y_start'].get()),
                'x_total': float(self.df['x_total'].get()),
                'y_drift': float(self.df['y_drift'].get()),
                'seg_dx': float(self.df['seg_dx'].get()),
                'z_first': float(self.df['z_first'].get()),
                'z_step': float(self.df['z_step'].get()),
                'z_final': float(self.df['z_final'].get()),
                'feed_dep': float(self.df['feed_dep'].get()),
                'feed_z': float(self.df['feed_z'].get()),
                'feed_travel': float(self.df['feed_travel'].get()),
                'dwell_ms': float(self.df['dwell_ms'].get()),
                'fan': float(self.df['fan'].get()),
                'spindle': float(self.df['spindle'].get()),
                'e_mode': self.df['e_mode'].get(),
                'bead_width': float(self.df['bead_width'].get()),
                'wire_diam': float(self.df['wire_diam'].get()),
                'runout': float(self.df['runout'].get()),
                'retract': float(self.df['retract'].get()),
            })
            gc = gen_diagonal_drift(P); self._save_gcode(gc, "diagonal_drift.gcode")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _gen_overhang(self):
        try:
            P = self._common_params()
            P.update({
                'x_start': float(self.oh['x_start'].get()),
                'y_base': float(self.oh['y_base'].get()),
                'length_x': float(self.oh['length_x'].get()),
                'z_first': float(self.oh['z_first'].get()),
                'z_offsets_csv': self.oh['z_offsets_csv'].get(),
                'y_offsets_csv': self.oh['y_offsets_csv'].get(),
                'y_step': float(self.oh['y_step'].get()),
                'e_mode': self.oh['e_mode'].get(),
                'bead_width': float(self.oh['bead_width'].get()),
                'wire_diam': float(self.oh['wire_diam'].get()),
                'layer_height': float(self.oh['layer_height'].get()),
                'feed_dep': float(self.oh['feed_dep'].get()),
                'feed_z': float(self.oh['feed_z'].get()),
                'feed_travel': float(self.oh['feed_travel'].get()),
                'dwell_ms': float(self.oh['dwell_ms'].get()),
                'fan': float(self.oh['fan'].get()),
                'spindle': float(self.oh['spindle'].get()),
                'runout': float(self.oh['runout'].get()),
                'retract': float(self.oh['retract'].get()),
                'travel_z': float(10.0),
            })
            gc = gen_overhang_tests(P); self._save_gcode(gc, "overhang_tests.gcode")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _save_gcode(self, text, default_name):
        fpath = filedialog.asksaveasfilename(
            defaultextension=".gcode",
            initialfile=default_name,
            filetypes=[("G-code","*.gcode"),("All files","*.*")]
        )
        if not fpath: return
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(text)
        messagebox.showinfo("Saved", fpath)

if __name__ == "__main__":
    app = Playground()
    app.mainloop()
