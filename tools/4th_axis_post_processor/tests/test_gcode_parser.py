import os
import tempfile
from gcode_parser import parse_gcode_points, batch_points_for_spline, collect_sparse_points


def test_parse_linear_moves():
    s = """
    G1 X0 Y0
    G1 X1 Y0
    G1 X2 Y0
    """
    with tempfile.NamedTemporaryFile('w+', delete=False) as f:
        f.write(s)
        fname = f.name
    pts = list(parse_gcode_points(fname))
    os.unlink(fname)
    assert pts == [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]


def test_batch_points_corner_density():
    s = """
    G1 X0 Y0
    G1 X1 Y0
    G1 X1 Y1
    """
    with tempfile.NamedTemporaryFile('w+', delete=False) as f:
        f.write(s)
        fname = f.name
    batches = list(batch_points_for_spline(fname, batch_size=50, angle_threshold_deg=20, corner_density=4, straight_sample_dist=0.2))
    os.unlink(fname)
    pts = [p for b in batches for p in b]
    # There should be more than 3 points because the corner gets extra sampling
    assert len(pts) > 3


def test_collect_sparse_points_simple():
    s = """
    G1 X0 Y0
    G1 X1 Y0
    G1 X2 Y0
    G1 X3 Y0
    G1 X4 Y0
    G1 X5 Y0
    """
    with tempfile.NamedTemporaryFile('w+', delete=False) as f:
        f.write(s)
        fname = f.name
    x, y = collect_sparse_points(fname, max_points=3, batch_size=10)
    os.unlink(fname)
    assert len(x) <= 3
