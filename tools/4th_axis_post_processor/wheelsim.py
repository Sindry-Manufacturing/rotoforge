

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
import time
from scipy.interpolate import splprep, splev
import argparse, sys, os
import csv
try:
    from gcode_parser import collect_sparse_points
except Exception:
    collect_sparse_points = None

# -------------------------
# CONFIGURATION
# -------------------------
offset = 10.       # wheel axis offset from contact point
line_length = 2   # length of tangent line representing wheel
smoothness = 0.0001   # spline smoothness (lower = more accurate)


points = []
path_ready = False


# -------------------------
# FILE LOADING
# -------------------------
def load_points_from_csv(csvfile):
    pts = []
    extrude = []
    with open(csvfile, 'r', newline='') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                x = float(row[0])
                y = float(row[1])
                if len(row) > 2:
                    e = int(float(row[2]))
                else:
                    e = None
                pts.append([x, y])
                extrude.append(e)
            except Exception:
                continue
    if all(e is None for e in extrude):
        return pts, None
    return pts, extrude


# CLI arg for display mode
import argparse as _argparse
_parser = _argparse.ArgumentParser()
_parser.add_argument('infile', help='Input CSV or G-code')
_parser.add_argument('--show', choices=['all', 'extrude', 'hop'], default='all', help='Show all, only extruding, or only hop moves')
_parser.add_argument('--raw', action='store_true', default=True, help='Use raw mode: no downsampling, strict G-code order (for .gcode input) [default]')
_parser.add_argument('--angle-threshold', type=float, default=30.0, help='Angle in degrees to detect corners (lower = more sensitive)')
_parser.add_argument('--corner-density', type=int, default=6, help='Number of extra points to add at corners')
_parser.add_argument('--straight-sample-dist', type=float, default=0.5, help='Distance between points on straight segments')
_parser.add_argument('--angle-smooth-window', type=int, default=5, help='Window size for smoothing wheel orientation (larger = smoother, odd recommended)')
_args = _parser.parse_args()

infile = _args.infile
show_mode = _args.show
raw_mode = True  # Always use raw mode for G-code
angle_threshold_deg = _args.angle_threshold
corner_density = _args.corner_density
straight_sample_dist = _args.straight_sample_dist
ext = os.path.splitext(infile)[1].lower()
loaded = False
extrude = None
if ext == '.csv':
    try:
        pts, extrude = load_points_from_csv(infile)
        if len(pts) > 5:
            points = pts
            path_ready = True
            loaded = True
            print(f"Loaded {len(points)} points from {infile}")
        else:
            print(f"Not enough points found in {infile}")
    except Exception as e:
        print(f"Failed to load CSV: {e}")
elif ext in ['.gcode', '.nc', '.tap', '.txt'] or True:
    if collect_sparse_points is not None:
        try:
            if _args.raw:
                result = collect_sparse_points(infile, raw=True)
                if len(result) == 4:
                    x_g, y_g, z_g, extrude = result
                    print(f"[RAW MODE] Loaded {len(x_g)} points from {infile}")
                    points = list(zip(x_g.tolist(), y_g.tolist(), z_g.tolist()))
                    z_path_loaded = z_g.tolist()
                else:
                    # Fallback for legacy: no Z
                    x_g, y_g, extrude = result
                    print(f"[RAW MODE] Loaded {len(x_g)} points from {infile} (no Z)")
                    points = list(zip(x_g.tolist(), y_g.tolist()))
                    z_path_loaded = None
            else:
                result = collect_sparse_points(
                    infile,
                    raw=False,
                    angle_threshold_deg=angle_threshold_deg,
                    corner_density=corner_density,
                    straight_sample_dist=straight_sample_dist
                )
                # Non-raw mode: may not have Z
                if len(result) == 4:
                    x_g, y_g, z_g, extrude = result
                    print(f"[SPARSE MODE] Loaded {len(x_g)} points from {infile} (with Z)")
                    points = list(zip(x_g.tolist(), y_g.tolist(), z_g.tolist()))
                    z_path_loaded = z_g.tolist()
                else:
                    x_g, y_g, extrude = result
                    print(f"[SPARSE MODE] Loaded {len(x_g)} points from {infile} (no Z)")
                    points = list(zip(x_g.tolist(), y_g.tolist()))
                    z_path_loaded = None
            if len(points) > 5:
                path_ready = True
                loaded = True
            else:
                print(f"Not enough points found in {infile}")
        except Exception as e:
            print(f"Failed to load gcode: {e}")
    else:
        print("G-code parser not available.")
if not loaded:
    print("No valid path points loaded. Exiting.")
    sys.exit(1)


# -------------------------
# PLOT SETUP
# -------------------------
fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.18)  # Make space for slider
ax.set_aspect('equal')
ax.set_title("Wheel Path Animation")

# Slider for animation speed
slider_ax = plt.axes([0.15, 0.05, 0.7, 0.05])
speed_slider = Slider(slider_ax, 'Speed', 0.1, 5.0, valinit=1.0, valstep=0.01)

# Plot objects for animation
wheel_center_point, = ax.plot([], [], 'ro')
wheel_arrow = None  # Will hold the matplotlib arrow object

# We'll draw path segments manually for extrude/hop coloring
path_line, = ax.plot([], [], lw=1, color='orange')

# -------------------------
# ANIMATION SETUP

# -------------------------
# ANIMATION SETUP
# -------------------------
def animate_path(x_path, y_path, extrude_mask=None, angle_smooth_window=5):
    frames = len(x_path)
    delay = [0.016]  # default ~60 FPS

    def on_speed_change(val):
        delay[0] = max(0.001, 0.5 / val)
    speed_slider.on_changed(on_speed_change)

    # Plot raw points for comparison (only once, before animation loop)
    if hasattr(animate_path, 'raw_points') and animate_path.raw_points is not None:
        raw_x, raw_y = animate_path.raw_points
        # Plot as blue dots and a faint blue line
        ax.plot(raw_x, raw_y, 'o', color='blue', markersize=3, alpha=0.5, label='Raw Points')
        ax.plot(raw_x, raw_y, '-', color='blue', lw=0.5, alpha=0.3, zorder=0)
        animate_path.raw_points = None  # Only plot once

    # Precompute robust per-point angles (tangents) to handle sharp corners reliably
    pts = np.column_stack((x_path, y_path))
    n_points = len(x_path)
    if n_points >= 2:
        segs = np.diff(pts, axis=0)
        seg_lens = np.linalg.norm(segs, axis=1)
        u = np.zeros_like(segs)
        nz = seg_lens > 1e-12
        u[nz] = segs[nz] / seg_lens[nz, None]
        tangents = np.zeros((n_points, 2))
        for idx in range(n_points):
            if idx == 0:
                tangents[idx] = u[0]
            elif idx == n_points - 1:
                tangents[idx] = u[-1]
            else:
                u_in = u[idx-1]
                u_out = u[idx]
                s = u_in + u_out
                norm_s = np.linalg.norm(s)
                if norm_s < 1e-8:
                    # near reversal; prefer longer adjacent segment
                    if seg_lens[idx-1] >= seg_lens[idx]:
                        tangents[idx] = u_in
                    else:
                        tangents[idx] = u_out
                else:
                    tangents[idx] = s / norm_s
        thetas = np.arctan2(tangents[:,1], tangents[:,0])
        thetas = np.unwrap(thetas)
        if angle_smooth_window > 1:
            kernel = np.ones(angle_smooth_window) / angle_smooth_window
            thetas = np.convolve(thetas, kernel, mode='same')
    else:
        thetas = np.array([0.0]*n_points)

    i = 0
    batch_size = 1000  # Number of points to draw at a time
    # Track absolute wheel orientation relative to start
    if not hasattr(animate_path, 'info_text') or animate_path.info_text is None:
        animate_path.info_text = ax.text(0.02, 0.98, '', transform=ax.transAxes, fontsize=10, va='top', ha='left', color='red', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    min_frames = 4
    max_frames = 24
    global wheel_arrow
    prev_theta = None
    paused = [False]
    step_back = [False]
    step_forward = [False]
    # For export
    export_data = []  # Each row: [frame, center_x, center_y, center_z, angle_deg]
    frame_counter = 0
    batch_size_csv = 100
    csv_filename = 'wheel_centers.csv'
    # Write header at start
    import csv
    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['frame', 'center_x', 'center_y', 'center_z', 'angle_deg'])

    def on_key(event):
        if event.key == ' ':
            paused[0] = not paused[0]
        elif event.key == 'left':
            step_back[0] = True
        elif event.key == 'right':
            step_forward[0] = True

    fig.canvas.mpl_connect('key_press_event', on_key)

    # If Z is available, use it
    z_path = None
    if hasattr(animate_path, 'z_path') and animate_path.z_path is not None:
        z_path = animate_path.z_path
    i = 0
    while i < n_points:
        end_idx = min(i+1, n_points)
        start_idx = max(0, end_idx - batch_size)
        x0 = x_path[i-1] if i > 0 else x_path[i]
        y0 = y_path[i-1] if i > 0 else y_path[i]
        x1 = x_path[i]
        y1 = y_path[i]
        z0 = z_path[i-1] if (z_path is not None and i > 0) else (z_path[i] if z_path is not None else 0.0)
        z1 = z_path[i] if z_path is not None else 0.0
        theta = thetas[i]
        if prev_theta is None:
            prev_theta = theta
        dtheta = theta - prev_theta
        if abs(dtheta) > np.pi:
            if dtheta > 0:
                interp_start = prev_theta
                interp_end = prev_theta - (2 * np.pi - dtheta)
            else:
                interp_start = prev_theta
                interp_end = prev_theta + (2 * np.pi + dtheta)
            abs_dtheta = abs(interp_end - interp_start)
        else:
            interp_start = prev_theta
            interp_end = theta
            abs_dtheta = abs(interp_end - interp_start)
        # Map abs_dtheta (0 to pi) to min_frames to max_frames
        interp_frames = int(min_frames + (max_frames - min_frames) * (abs_dtheta / np.pi))
        interp_frames = max(min_frames, min(max_frames, interp_frames))
        for f in range(1, interp_frames+1):
            t = f / interp_frames
            interp_x = x0 + (x1 - x0) * t
            interp_y = y0 + (y1 - y0) * t
            interp_z = z0 + (z1 - z0) * t if z_path is not None else 0.0
            interp_theta = interp_start + (interp_end - interp_start) * t
            interp_theta = ((interp_theta + np.pi) % (2*np.pi)) - np.pi
            nx = -np.sin(interp_theta)
            ny =  np.cos(interp_theta)
            wheel_cx = interp_x + offset * nx
            wheel_cy = interp_y + offset * ny
            # Record for export
            export_data.append([frame_counter, wheel_cx, wheel_cy, interp_z, np.degrees(interp_theta)])
            frame_counter += 1
            # Write in batches
            if len(export_data) >= batch_size_csv:
                with open(csv_filename, 'a', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerows(export_data)
                export_data.clear()
            if wheel_arrow is not None:
                try:
                    wheel_arrow.remove()
                except Exception:
                    pass
            dx = line_length * np.cos(interp_theta)
            dy = line_length * np.sin(interp_theta)
            wheel_arrow = ax.arrow(
                interp_x, interp_y, dx, dy,
                head_width=line_length*0.5, head_length=line_length*0.7, fc='r', ec='r', lw=2, length_includes_head=True, zorder=3
            )
            wheel_center_point.set_data([wheel_cx], [wheel_cy])
            # Show Z in info overlay if available
            if z_path is not None:
                animate_path.info_text.set_text(f"Center: ({wheel_cx:.2f}, {wheel_cy:.2f}, {interp_z:.2f})\nAngle: {np.degrees(interp_theta):.1f}°\nZ: {interp_z:.2f}")
            else:
                animate_path.info_text.set_text(f"Center: ({wheel_cx:.2f}, {wheel_cy:.2f})\nAngle: {np.degrees(interp_theta):.1f}°")
            for l in ax.lines[:]:
                if l is not wheel_center_point:
                    l.remove()
            if extrude_mask is not None:
                for j in range(max(1, start_idx), end_idx):
                    color = 'black' if extrude_mask[j] == 1 else 'gray'
                    lw = 2 if extrude_mask[j] == 1 else 1
                    ls = '-' if extrude_mask[j] == 1 else '--'
                    ax.plot([x_path[j-1], x_path[j]], [y_path[j-1], y_path[j]], color=color, lw=lw, ls=ls, alpha=0.8, zorder=1)
            else:
                ax.plot(x_path[start_idx:end_idx], y_path[start_idx:end_idx], color='orange', lw=1)
            fig.canvas.draw_idle()
            # Pause/play/rewind logic
            while paused[0] or step_back[0] or step_forward[0]:
                plt.pause(0.05)
                if step_back[0]:
                    # Step back one move
                    i = max(i - 2, 0)
                    prev_theta = None
                    step_back[0] = False
                    break
                if step_forward[0]:
                    # Step forward one move
                    step_forward[0] = False
                    break
            else:
                plt.pause(delay[0])
        prev_theta = theta
        i = (i + 1) % n_points

    # Write any remaining data after animation
    if export_data:
        with open(csv_filename, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(export_data)


# -------------------------
# MAIN LOOP
# -------------------------
plt.ion()
plt.show(block=False)
anim = None
path_ready = True
while True:
    plt.pause(0.01)
    if path_ready:
        path_ready = False
        try:
            P = np.array(points, dtype=float)
            if P.ndim < 2 or P.shape[0] < 2 or P.shape[1] < 2:
                print("Error: Input points are not a valid 2D array with shape (N,2) or (N,3). Aborting.")
                break
            N = 200  # Number of points to display (for debug, not used in raw mode)
            if P.shape[0] > N:
                print(f"[DEBUG] Displaying only the first {N} points out of {P.shape[0]} total.")
            else:
                print(f"[DEBUG] Displaying all {P.shape[0]} points.")
            x = P[:,0]
            y = P[:,1]
            z = P[:,2] if P.shape[1] > 2 else None
            # Draw path segments by extrude/hop (polyline, not spline)
            for l in ax.lines[:]:
                if l is not wheel_center_point:
                    l.remove()
            if extrude is not None and len(extrude) == len(points):
                extrude_arr = np.array(extrude)
                x_arr = np.array([p[0] for p in points])
                y_arr = np.array([p[1] for p in points])
                # Mask for display mode
                if show_mode == 'extrude':
                    mask = extrude_arr == 1
                elif show_mode == 'hop':
                    mask = extrude_arr == 0
                else:
                    mask = np.ones_like(extrude_arr, dtype=bool)
                # Draw segments
                for i in range(1, len(points)):
                    if not (mask[i-1] and mask[i]):
                        continue
                    color = 'black' if extrude_arr[i] == 1 else 'gray'
                    lw = 2 if extrude_arr[i] == 1 else 1
                    ls = '-' if extrude_arr[i] == 1 else '--'
                    ax.plot([x_arr[i-1], x_arr[i]], [y_arr[i-1], y_arr[i]], color=color, lw=lw, ls=ls, alpha=0.8, zorder=1)
            else:
                path_line.set_data(x, y)
            # Print min/max for debug
            print(f"[DEBUG] X range: {x.min()} to {x.max()}")
            print(f"[DEBUG] Y range: {y.min()} to {y.max()}")
            # Auto-scale plot limits with margin
            margin = 0.05
            x_span = x.max() - x.min()
            y_span = y.max() - y.min()
            ax.set_xlim(x.min() - margin*x_span, x.max() + margin*x_span)
            ax.set_ylim(y.min() - margin*y_span, y.max() + margin*y_span)
            # Pass extrude mask for incremental drawing
            animate_path.raw_points = (x, y)
            # Set z_path for animation
            if 'z_path_loaded' in locals() and z_path_loaded is not None:
                animate_path.z_path = z_path_loaded
            else:
                animate_path.z_path = None
            if extrude is not None and len(extrude) == len(points):
                animate_path(x, y, extrude, angle_smooth_window=_args.angle_smooth_window)
            else:
                animate_path(x, y, None, angle_smooth_window=_args.angle_smooth_window)
            fig.canvas.draw_idle()
        except Exception as e:
            print(f"Error processing points for polyline: {e}")
            break


# If a CSV or G-code file is provided as a CLI argument, load points accordingly.

import argparse, sys, os
import csv
try:
    from gcode_parser import collect_sparse_points
except Exception:
    collect_sparse_points = None

def load_points_from_csv(csvfile):
    pts = []
    with open(csvfile, 'r', newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                x = float(row[0])
                y = float(row[1])
                pts.append([x, y])
            except Exception:
                # skip header or malformed rows
                continue
    return pts

if len(sys.argv) > 1:
    infile = sys.argv[1]
    ext = os.path.splitext(infile)[1].lower()
    loaded = False
    if ext == '.csv':
        try:
            pts = load_points_from_csv(infile)
            if len(pts) > 5:
                points = pts
                path_ready = True
                loaded = True
                print(f"Loaded {len(points)} points from {infile}")
            else:
                print(f"Not enough points found in {infile}")
        except Exception as e:
            print(f"Failed to load CSV: {e}")
    elif ext in ['.gcode', '.nc', '.tap', '.txt'] or True:
        # Try to parse as G-code if not CSV
        if collect_sparse_points is not None:
            try:
                x_g, y_g = collect_sparse_points(infile, max_points=2000, batch_size=1000, angle_threshold_deg=30.0, corner_density=6)
                if len(x_g) > 5:
                    points = list(zip(x_g.tolist(), y_g.tolist()))
                    path_ready = True
                    loaded = True
                    print(f"Loaded {len(points)} points from {infile}")
                else:
                    print(f"Not enough points found in {infile}")
            except Exception as e:
                print(f"Failed to load gcode: {e}")
        else:
            print("G-code parser not available.")
    if not loaded:
        print("No valid path points loaded. You can still draw with the mouse.")

while True:
    plt.pause(0.01)

    if path_ready:
        path_ready = False

        # Extract drawings
        try:
            P = np.array(points, dtype=float)
            if P.ndim != 2 or P.shape[0] < 2 or P.shape[1] != 2:
                print("Error: Input points are not a valid 2D array with shape (N,2). Aborting.")
                continue
            x = P[:,0]
            y = P[:,1]

            # Fit spline for smooth toolpath
            tck, _ = splprep([x, y], s=smoothness)
            u_fine = np.linspace(0, 1, 800)
            x_smooth, y_smooth = splev(u_fine, tck)

            path_line.set_data(x_smooth, y_smooth)

            # Run animation
            anim = animate_path(x_smooth, y_smooth, None, angle_smooth_window=_args.angle_smooth_window)

            fig.canvas.draw_idle()
        except Exception as e:
            print(f"Error processing points for spline: {e}")
            continue
