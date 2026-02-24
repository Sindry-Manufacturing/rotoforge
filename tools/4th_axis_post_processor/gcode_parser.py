def parse_gcode_points(file_path: str) -> 'Generator[Tuple[float, float], None, None]':
    """Yield (x,y) points for G0/G1 moves and G2/G3 arcs (no extrusion info)."""
    mode_absolute = True
    cur_x = 0.0
    cur_y = 0.0
    with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            line = _strip_comments(raw)
            if not line:
                continue
            if line.startswith("G90"):
                mode_absolute = True
            elif line.startswith("G91"):
                mode_absolute = False
            if MOVE_CMD_RE.search(line):
                coords = _parse_coords(line)
                x_found = "X" in coords
                y_found = "Y" in coords
                if x_found:
                    cur_x = coords["X"]
                if y_found:
                    cur_y = coords["Y"]
                if x_found or y_found:
                    yield (cur_x, cur_y)
            # (arcs not handled)
"""
gcode_parser.py

Streaming G-code parser to produce point arrays suitable for spline fitting.
- Streams file line-by-line to minimize memory usage
- Detects sharp corners (by angle) and increases sample density around them
- Decimates straight segments to keep point count low
- Yields batches of points for downstream processing

Public functions:
- batch_points_for_spline(file_path, batch_size=1000, angle_threshold_deg=30, corner_density=6, straight_sample_dist=0.5)
    Generator yielding lists of (x, y) tuples.

- collect_sparse_points(file_path, max_points=5000, **kwargs)
    Collects a reduced set of points for fitting a spline (still memory efficient).

This module intentionally keeps dependencies light (std lib + numpy).
"""

from typing import Generator, List, Tuple, Optional
import math
import re
import numpy as np

MOVE_CMD_RE = re.compile(r"^(?:G0|G1|G00|G01)\b")
ARC_CMD_RE = re.compile(r"^(?:G2|G3|G02|G03)\b")
COMMENT_RE = re.compile(r"\(.*?\)|;.*$")
COORD_RE = re.compile(r"([XYEIJRZ])([-+]?[0-9]*\.?[0-9]+)", re.IGNORECASE)


def _strip_comments(line: str) -> str:
    return COMMENT_RE.sub("", line).strip()


def _parse_coords(line: str) -> dict:
    coords = {}
    for m in COORD_RE.finditer(line):
        coords[m.group(1).upper()] = float(m.group(2))
    return coords


def _angle_between(a: np.ndarray, b: np.ndarray) -> float:
    """Return angle in radians between vectors a and b."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    c = np.dot(a, b) / (na * nb)
    c = max(-1.0, min(1.0, c))
    return math.acos(c)


def _lin_interpolate(p0: Tuple[float, float], p1: Tuple[float, float], n: int) -> List[Tuple[float, float]]:
    """Return n points (excluding p0, including p1) linearly between p0 and p1."""
    if n <= 1:
        return [p1]
    xs = np.linspace(p0[0], p1[0], n + 1)[1:]
    ys = np.linspace(p0[1], p1[1], n + 1)[1:]
    return list(zip(xs.tolist(), ys.tolist()))


def _arc_to_points(center_x, center_y, start_x, start_y, end_x, end_y, clockwise, max_seg_angle=math.radians(10)):
    """Approximate circular arc by splitting into small segments.
    Returns list of (x,y) excluding the start point and including the end point.
    """
    # angles
    a0 = math.atan2(start_y - center_y, start_x - center_x)
    a1 = math.atan2(end_y - center_y, end_x - center_x)

    if clockwise:
        if a1 > a0:
            a1 -= 2 * math.pi
        total = a0 - a1
        steps = max(1, int(math.ceil(total / max_seg_angle)))
        angles = [a0 - (i / steps) * total for i in range(1, steps + 1)]
    else:
        if a1 < a0:
            a1 += 2 * math.pi
        total = a1 - a0
        steps = max(1, int(math.ceil(total / max_seg_angle)))
        angles = [a0 + (i / steps) * total for i in range(1, steps + 1)]

    r = math.hypot(start_x - center_x, start_y - center_y)
    pts = [(center_x + r * math.cos(a), center_y + r * math.sin(a)) for a in angles]
    return pts


def parse_gcode_points_extrude(file_path: str):
    """Yield (x, y, extruding) for G0/G1 moves and G2/G3 arcs.
    extruding=1 if E increases, else 0. Only works for absolute E mode.
    """
    mode_absolute = True  # G90/G91 for XYZ, M82/M83 for E
    e_absolute = True     # M82/M83 for E
    cur_x = 0.0
    cur_y = 0.0
    cur_z = 0.0
    cur_e = 0.0
    last_e = 0.0
    e_offset = 0.0
    extruding_state = 0
    debug_count = 0
    with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            line = _strip_comments(raw)
            if not line:
                continue
            if line.startswith("G90"):
                mode_absolute = True
            elif line.startswith("G91"):
                mode_absolute = False
            elif line.startswith("M82"):
                e_absolute = True
            elif line.startswith("M83"):
                e_absolute = False
            elif line.startswith("G92"):
                coords = _parse_coords(line)
                if "E" in coords:
                    cur_e = coords["E"]
                    last_e = cur_e
                    e_offset = cur_e
                if "Z" in coords:
                    cur_z = coords["Z"]
            if MOVE_CMD_RE.search(line):
                coords = _parse_coords(line)
                x_found = "X" in coords
                y_found = "Y" in coords
                z_found = "Z" in coords
                e_found = "E" in coords
                prev_e = cur_e
                if x_found:
                    cur_x = coords["X"]
                if y_found:
                    cur_y = coords["Y"]
                if z_found:
                    cur_z = coords["Z"]
                # Update extrusion state only if E is present
                if e_found:
                    if e_absolute:
                        cur_e = coords["E"]
                        extruding_state = 1 if (cur_e > prev_e) else 0
                    else:
                        cur_e += coords["E"]
                        extruding_state = 1 if coords["E"] > 0 else 0
                # Only yield if at least one of X, Y, or Z is present (ignore pure E moves)
                if x_found or y_found or z_found:
                    if debug_count < 20:
                        print(f"DEBUG: X={cur_x}, Y={cur_y}, Z={cur_z}, E={cur_e}, e_found={e_found}, extruding={extruding_state}, e_absolute={e_absolute}, line='{line}'")
                        debug_count += 1
                    yield (cur_x, cur_y, cur_z, extruding_state)
                last_e = cur_e


def batch_points_for_spline(
    file_path: str,
    batch_size: int = 1000,
    angle_threshold_deg: float = 30.0,
    corner_density: int = 6,
    straight_sample_dist: float = 0.5,
) -> Generator[List[Tuple[float, float]], None, None]:
    """Stream points suitable for spline fitting in small batches.

    - Detects corners where the change in direction exceeds angle_threshold_deg
      and adds extra samples around the corner (corner_density per adjacent segment).
    - Straight lines are decimated by distance (straight_sample_dist)
    - Yields lists of tuples (x,y) with approximately batch_size items

    This generator keeps only a tiny rolling buffer in memory so it can handle
    very large files.
    """
    angle_threshold = math.radians(angle_threshold_deg)

    gen = parse_gcode_points(file_path)

    # rolling buffers
    prev2: Optional[Tuple[float, float]] = None
    prev1: Optional[Tuple[float, float]] = None

    batch: List[Tuple[float, float]] = []

    def push(p: Tuple[float, float]):
        batch.append(p)
        if len(batch) >= batch_size:
            # Keep last two points for continuity when resuming
            tail = batch[-2:]
            to_yield = batch[:-2]
            if to_yield:
                yield_list = to_yield.copy()
            else:
                yield_list = []
            # rotate batch: keep tail as new batch
            batch.clear()
            batch.extend(tail)
            return yield_list
        return None

    # Helper to decimate segment from a->b according to distance
    def _append_segment(a, b):
        dist = math.hypot(b[0] - a[0], b[1] - a[1])
        if dist <= 0:
            return None
        n = max(1, int(math.ceil(dist / straight_sample_dist)))
        pts = _lin_interpolate(a, b, n)
        for q in pts:
            res = push(q)
            if res is not None:
                yield res

    for p in gen:
        if prev1 is None:
            prev1 = p
            res = push(p)
            if res is not None:
                yield res
            continue
        if prev2 is None:
            prev2 = prev1
            prev1 = p
            # simple append segment prev2->prev1
            for r in _append_segment(prev2, prev1) or []:
                yield r
            continue

        # prev2, prev1, p available
        v1 = np.array([prev1[0] - prev2[0], prev1[1] - prev2[1]])
        v2 = np.array([p[0] - prev1[0], p[1] - prev1[1]])
        ang = _angle_between(v1, v2)

        if ang >= angle_threshold:
            # corner detected around prev1; increase sampling near corner
            # Subdivide segments prev2->prev1 and prev1->p with extra density
            # First, add subdivision from prev2 to prev1
            n_side = corner_density
            xs1 = np.linspace(prev2[0], prev1[0], n_side + 1)[1:]
            ys1 = np.linspace(prev2[1], prev1[1], n_side + 1)[1:]
            for qx, qy in zip(xs1, ys1):
                res = push((qx, qy))
                if res is not None:
                    yield res
            # Then subdivisions from prev1 to p
            xs2 = np.linspace(prev1[0], p[0], n_side + 1)[1:]
            ys2 = np.linspace(prev1[1], p[1], n_side + 1)[1:]
            for qx, qy in zip(xs2, ys2):
                res = push((qx, qy))
                if res is not None:
                    yield res
        else:
            # not a corner, decimate based on distance
            for r in _append_segment(prev1, p) or []:
                yield r

        prev2 = prev1
        prev1 = p

    # end for: yield any remaining batch
    if batch:
        yield batch.copy()



def collect_sparse_points(file_path: str, max_points: int = 5000, raw: bool = False, **kwargs):
    """
    If raw=True, returns all (x, y, extruding) points in strict G-code order (no downsampling, no corner detection).
    Otherwise, returns a reduced set of points suitable for spline fitting (legacy behavior).
    """
    if raw:
        # Return all points with extrusion info, in order (no interpolation, no extra points)
        xs, ys, zs, es = [], [], [], []
        for x, y, z, e in parse_gcode_points_extrude(file_path):
            xs.append(x)
            ys.append(y)
            zs.append(z)
            es.append(e)
        return np.array(xs), np.array(ys), np.array(zs), np.array(es)
    # Legacy downsampling mode
    kept = []
    total = 0
    for batch in batch_points_for_spline(file_path, **kwargs):
        total += len(batch)
        kept.extend(batch)
        if len(kept) > max_points * 2:
            # downsample by taking every other point
            kept = kept[::2]
    if len(kept) > max_points:
        idxs = np.linspace(0, len(kept) - 1, max_points).astype(int)
        kept = [kept[i] for i in idxs]
    if not kept:
        return np.empty((0,)), np.empty((0,))
    arr = np.array(kept)
    return arr[:, 0], arr[:, 1]


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stream a gcode file and output a reduced point set for spline fitting.")
    parser.add_argument("file", help="G-code file path")
    parser.add_argument("--csv", action="store_true", help="Output CSV with extruding column")
    parser.add_argument("--max-points", type=int, default=2000, help="max points to collect and print summary for")

    args = parser.parse_args()
    if args.csv:
        # Output CSV with extruding column
        outname = args.file + "_extrude.csv"
        with open(args.file, "r") as f:
            pass
        pts = list(parse_gcode_points_extrude(args.file))
        if len(pts) > args.max_points:
            idxs = np.linspace(0, len(pts) - 1, args.max_points).astype(int)
            pts = [pts[i] for i in idxs]
        with open(outname, "w", newline="") as outf:
            import csv as _csv
            w = _csv.writer(outf)
            w.writerow(["x", "y", "extruding"])
            for row in pts:
                w.writerow(row)
        print(f"Wrote {len(pts)} points to {outname}")
    else:
        x, y = collect_sparse_points(args.file, max_points=args.max_points)
        print(f"[DEBUG] Collected {len(x)} points (capped at {args.max_points}) from {args.file}")
        if len(x) > 0:
            print("[DEBUG] First 10 points:")
            for i in range(min(10, len(x))):
                print(f"  ({x[i]}, {y[i]})")
        else:
            print("[DEBUG] No points parsed from file!")
    sys.exit(0)
