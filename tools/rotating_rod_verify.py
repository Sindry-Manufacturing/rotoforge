#!/usr/bin/env python3
"""Verify analytic formulas for a uniform rod of length L and mass m
rotating about an axis perpendicular to the rod through one end (cantilever).

Analytic results:
  F_total = (1/2) m ω^2 L
  M_total = (1/3) m ω^2 L^2  (moment about the pivot due to distributed radial force)
  r_res = 2/3 * L  (location of resultant force from pivot)

This script numerically integrates the distributed dF = dm * ω^2 * r and compares.
Usage:
  python3 rotating_rod_verify.py [-m M] [-L L] [-w W] [-N N] [--quiet]

Defaults preserve previous behavior: m=2 kg, L=0.5 m, w=50 rad/s, N=200000
"""
import argparse
import math
import sys


def analytic(m, L, w):
    F = 0.5 * m * w**2 * L
    M = (1.0 / 3.0) * m * w**2 * L**2
    r_res = 2.0 * L / 3.0
    return F, M, r_res


def numeric(m, L, w, N=100000):
    # divide rod into N equal segments
    lam = m / L
    dr = L / N
    F = 0.0
    M = 0.0
    for i in range(N):
        # use midpoint of segment for r
        r = (i + 0.5) * dr
        dm = lam * dr
        dF = dm * w**2 * r
        F += dF
        M += dF * r  # moment about pivot
    # compute resultant location
    r_res = M / F if F != 0 else float('nan')
    return F, M, r_res


def approx_equal(a, b):
    if math.isfinite(a) and math.isfinite(b) and b != 0:
        return abs((a - b) / b)
    return float('nan')


def parse_args(argv):
    p = argparse.ArgumentParser(description="Verify distributed rotation forces for a uniform rod.")
    p.add_argument('-m', '--mass', type=float, default=2.0, help='total mass (kg)')
    p.add_argument('-L', '--length', type=float, default=0.5, help='rod length (m)')
    p.add_argument('-w', '--omega', type=float, default=50.0, help='angular speed (rad/s)')
    p.add_argument('-N', '--segments', type=int, default=200000, help='number of numeric segments')
    p.add_argument('--quiet', action='store_true', help='suppress detailed print, only print summary')
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    m = args.mass
    L = args.length
    w = args.omega
    N = args.segments

    F_a, M_a, r_a = analytic(m, L, w)
    F_n, M_n, r_n = numeric(m, L, w, N=N)

    if not args.quiet:
        print(f"Parameters: m={m} kg, L={L} m, w={w} rad/s, segments={N}\n")
        print("Analytic results:")
        print(f"  F_total = {F_a:.6f} N")
        print(f"  M_total = {M_a:.6f} N*m")
        print(f"  r_res   = {r_a:.6f} m")
        print()
        print("Numeric integration results:")
        print(f"  F_total = {F_n:.6f} N")
        print(f"  M_total = {M_n:.6f} N*m")
        print(f"  r_res   = {r_n:.6f} m")
        print()
        print("Relative errors (numeric vs analytic):")
        print(f"  F error = {approx_equal(F_n, F_a):.3e}")
        print(f"  M error = {approx_equal(M_n, M_a):.3e}")
        print(f"  r error = {approx_equal(r_n, r_a):.3e}")
    else:
        # quiet summary: print analytic and numeric in one line
        print(f"m={m},L={L},w={w},N={N},F_a={F_a:.6f},F_n={F_n:.6f},M_a={M_a:.6f},M_n={M_n:.6f},r_a={r_a:.6f},r_n={r_n:.6f}")


if __name__ == '__main__':
    main()
