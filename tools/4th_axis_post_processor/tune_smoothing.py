"""tune_smoothing.py

Quick utility to evaluate angle continuity for different smoothing window sizes.
Produces a small report to stdout and saves diagnostic PNGs showing wheel direction
at a set of sample points.

Usage: python tune_smoothing.py input.gcode --windows 1 3 5 9
"""
import argparse
import os
import sys
import math
import numpy as np
import matplotlib.pyplot as plt

try:
    from gcode_parser import collect_sparse_points
except Exception:
    collect_sparse_points = None


def load_xy(infile):
    ext = os.path.splitext(infile)[1].lower()
    if ext in ('.gcode', '.nc', '.tap', '.txt') or True:
        if collect_sparse_points is None:
            raise RuntimeError('gcode_parser.collect_sparse_points not available in this environment')
        res = collect_sparse_points(infile, raw=True)
        if len(res) == 4:
            xg, yg, zg, extr = res
        else:
            xg, yg, extr = res
        xs = np.array(xg)
        ys = np.array(yg)
        return xs, ys


def compute_thetas(xs, ys, window=5):
    pts = np.column_stack((xs, ys))
    n = len(xs)
    if n < 2:
        return np.zeros(n)
    segs = np.diff(pts, axis=0)
    seg_lens = np.linalg.norm(segs, axis=1)
    u = np.zeros_like(segs)
    nz = seg_lens > 1e-12
    u[nz] = segs[nz] / seg_lens[nz, None]
    tangents = np.zeros((n, 2))
    for idx in range(n):
        if idx == 0:
            tangents[idx] = u[0]
        elif idx == n - 1:
            tangents[idx] = u[-1]
        else:
            u_in = u[idx-1]
            u_out = u[idx]
            s = u_in + u_out
            norm_s = np.linalg.norm(s)
            if norm_s < 1e-8:
                if seg_lens[idx-1] >= seg_lens[idx]:
                    tangents[idx] = u_in
                else:
                    tangents[idx] = u_out
            else:
                tangents[idx] = s / norm_s
    thetas = np.arctan2(tangents[:,1], tangents[:,0])
    thetas = np.unwrap(thetas)
    if window > 1:
        kernel = np.ones(window) / window
        thetas = np.convolve(thetas, kernel, mode='same')
    return thetas


def angle_stats(thetas):
    # compute per-sample delta angle (absolute) in degrees
    d = np.abs(np.diff(thetas))
    d = (d + np.pi) % (2*np.pi) - np.pi
    d = np.abs(d)
    return {
        'max_deg': np.degrees(np.max(d)) if len(d)>0 else 0.0,
        'median_deg': np.degrees(np.median(d)) if len(d)>0 else 0.0,
        'mean_deg': np.degrees(np.mean(d)) if len(d)>0 else 0.0
    }


def plot_sample(xs, ys, thetas, out_png, step=50, scale=5.0):
    plt.figure(figsize=(8,8))
    plt.plot(xs, ys, '-', color='lightgray')
    plt.plot(xs, ys, 'o', ms=2, color='gray', alpha=0.4)
    for i in range(0, len(xs), step):
        x = xs[i]
        y = ys[i]
        th = thetas[i]
        dx = math.cos(th)*scale
        dy = math.sin(th)*scale
        plt.arrow(x, y, dx, dy, head_width=scale*0.3, head_length=scale*0.4, color='red')
    plt.axis('equal')
    plt.title(f'Wheel directions (every {step} pts)')
    plt.savefig(out_png)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('infile')
    parser.add_argument('--windows', type=int, nargs='+', default=[1,3,5,9])
    parser.add_argument('--sample-step', type=int, default=100)
    parser.add_argument('--min-frames', type=int, default=4)
    parser.add_argument('--max-frames', type=int, default=24)
    args = parser.parse_args()

    xs, ys = load_xy(args.infile)
    print(f'Loaded {len(xs)} points from {args.infile}')

    # simulation parameters matching wheelsim.py interpolation (allow override)
    min_frames = args.min_frames
    max_frames = args.max_frames
    for w in args.windows:
        thetas = compute_thetas(xs, ys, window=w)
        stats = angle_stats(thetas)
        # simulate per-frame interpolation deltas
        per_frame_deltas = []
        prev_theta = None
        n = len(thetas)
        for i in range(n):
            theta = thetas[i]
            if prev_theta is None:
                prev_theta = theta
                continue
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
            interp_frames = int(min_frames + (max_frames - min_frames) * (abs_dtheta / np.pi))
            interp_frames = max(min_frames, min(max_frames, interp_frames))
            last_frame_theta = prev_theta
            for f in range(1, interp_frames+1):
                t = f / interp_frames
                interp_theta = interp_start + (interp_end - interp_start) * t
                step_delta = abs((interp_theta - last_frame_theta + np.pi) % (2*np.pi) - np.pi)
                per_frame_deltas.append(step_delta)
                last_frame_theta = interp_theta
            prev_theta = theta
        # convert to degrees
        pf_deg = np.degrees(per_frame_deltas) if per_frame_deltas else np.array([0.0])
        print(f'window={w:2d}: raw_max={stats["max_deg"]:.2f} deg, raw_median={stats["median_deg"]:.2f} deg, raw_mean={stats["mean_deg"]:.2f} deg | per-frame max={pf_deg.max():.2f} deg, per-frame mean={pf_deg.mean():.2f} deg')
        png = f'theta_window_{w}.png'
        plot_sample(xs, ys, thetas, png, step=args.sample_step, scale=max( (max(xs)-min(xs)) / 40.0, 1.0))
        print(f'  -> wrote {png}')

if __name__ == '__main__':
    main()
