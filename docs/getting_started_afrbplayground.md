# afrb Playground — Operator & Developer Getting Started Guide
*(for RotoForge / additive friction roll bonding hardware)*

This GUI script generates simple, test‑friendly G‑code patterns (lines, dots, rasters, drifts, overhang tests) for wire‑fed friction roll bonding. It’s not a full slicer—think of it as a safe, inspectable pattern generator you can extend.

The script is in development and very quick and dirty. you have been warned.
---

## Part A — New users (operators)

### What the tool does
- Builds G‑code with a standard header (units, homing, optional bed preheat & wait, fan, spindle spin‑up) and a matching footer (stop spindle/fan, safe Z). It then prints one of five pattern types from a tab.
- Defaults are provided per material (Al 1100‑O Ø0.50 mm, Steel 1008 Ø0.356 mm). You can override everything.

**Units:** distances in mm, feeds **F** in mm/min, temperature in °C, time in ms. Extrusion **E** is *relative* (M83), and the script frequently resets E (G92 E0).

---

### Quick start: first bonded wall (Aluminum, single track)
1. **Preset:** **Aluminum 1100‑O (Ø0.50 mm)** (typical: Deposition F≈1000, Fan=255, Spindle=30000, Bed≈110 °C, Dwell=2000 ms).
2. **(Optional) Bed preheat:** Set **Bed °C**, keep **Wait (M190)** checked, and **Dwell ms ~2000**.
3. **Straight / Multitrack** tab: 60 mm line, **Z 0.8 → 10.0**, **Layer 0.10** in −X. Use **Extrusion Mode = “x”** to start, or **“volume”** for area‑matched feed.
4. **Generate G‑code…** Save, transfer to the controller, set safe zeros, and run. (For a dry run, set **Spindle=0** and **Bed=0**.)

   I have had best results using pronterface. but other g-code senders should work as well. It is not generally neccessary to heat the bed but this can reduce forces and make thicker layerheights possible. 
   You will also need to reset the starting Z based on your particular printer and print bed height / leveling /homing setup. I have not included provisions for automatic bed leveling probes consciously. 

---

### UI map

**Top bar**
- **Material Preset / Toggle** — aluminum or steel presets (also set bed defaults).
- **Bed °C / Wait (M190) / Dwell ms** — optional preheat+wait+dwell; Bed 0 disables heat.

**Tabs (pattern types)**
1) **Straight / Multitrack** — straight beads with optional multitrack(lines side by side to make thicker walls/perimeters) & overlap.  
2) **Dot Stack** — “pulsed” dots stacked in Z at fixed XY.  
3) **Sideways Micro‑Raster** — short −X strokes stepped in Y to fill a patch.  
4) **Diagonal Drift** — segmented −X line that drifts in +Y.  
5) **Overhang Tests** — −X lines at varying Z/Y offsets.

---

### Parameter quick‑reference

**Common**: `feed_travel`, `feed_z`, `feed_dep`, `spindle`, `fan`, `travel_z`, `dwell_ms`, `runout`, `retract`, `bed_temp`, `wait_bed`, `bed_dwell_ms`.

**Extrusion**:
- `x` → 1 E/mm (simple).
- `volume` → `(bead_width × layer_height) / wire_area`, `wire_area = π (wire_diam/2)^2`.

**Straight / Multitrack**: Start X/Y; **Path Length X (−X)**; Z start/step/final; `e_mode`, `bead_width`, `wire_diam`; `lead_in`, `runout`, `retract`, optional `Z‑dive cut`; Multitrack: `track_count`, `overlap_frac`, `serpentine_y`.

**Dot Stack**: X/Y fixed; Z start/step/final; `e_pulse`, `e_retract`.

**Sideways Micro‑Raster**: Start X/Y; `x_stroke` (−X), `y_span`, `dy_step`; Z start/step/final; `e_mode`, `bead_width`, `wire_diam`; `runout`, `retract`.

**Diagonal Drift**: Start X/Y; `x_total` (−X), `y_drift`, `seg_dx`; Z start/step/final; `e_mode`, `bead_width`, `wire_diam`; `runout`, `retract`.

**Overhang Tests**: Start X, Base Y; `length_x` (−X); `z_first`; `z_offsets_csv`; `y_offsets_csv` or `y_step`; `e_mode`, `bead_width`, `layer_height`, `wire_diam`; feeds; `runout`, `retract`.

---

### Two simple recipes
- **Tall straight wall:** `track_count=1`, `z_step=0.10`, `z_final≈10`, `e_mode="x"`, `runout=2`, `retract=2`.  
- **Small filled patch:** `x_stroke=5`, `y_span=6`, `dy_step≈0.33`, 2–4 layers, `runout=1`, `retract=2`.

---

## Part B — Developers

### Code layout
- Helpers: `parse_csv_floats`, `compute_e_per_mm`, `gcode_header`, `gcode_footer`.
- Patterns: `gen_straight_multitrack`, `gen_dot_stack`, `gen_sideways_micro_raster`, `gen_diagonal_drift`, `gen_overhang_tests`.
- GUI: `Playground` builds the top bar and five tabs; `_common_params()` centralizes shared defaults; `_ent(...)` makes labeled entries; `_gen_*` handlers gather → generate → save.

### Add a new pattern
```python
def gen_my_pattern(P):
    lines = []
    lines += gcode_header(P)
    # ... your moves here ...
    lines += gcode_footer(P)
    return "\n".join(lines)
