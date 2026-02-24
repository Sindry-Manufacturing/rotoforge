import csv
import sys

HEADER = [
    "; Generated from wheel_centers.csv",
    "G90 ; Absolute positioning",
    "G21 ; Set units to mm",
    "G92 X0 Y0 Z0 ; Set current position as zero",
]
FOOTER = [
    "M2 ; End of program"
]

def csv_to_gcode(csv_path, gcode_path):
    with open(csv_path, newline='') as csvfile, open(gcode_path, 'w') as gfile:
        reader = csv.DictReader(csvfile)
        gfile.write("\n".join(HEADER) + "\n")
        for row in reader:
            x = row.get('center_x')
            y = row.get('center_y')
            z = row.get('center_z')
            a = row.get('angle_deg')   
            # Accept both 'a' and 'A' and 'angle_deg' as possible angle columns
           # a = row.get('a') or row.get('A') or row.get('angle_deg')
            if x is None or y is None:
                continue
            line = f"G1 X{x} Y{y}"
            if z is not None and z != '':
                line += f" Z{z}"
            if a is not None and a != '':
                line += f" A{a}"
            gfile.write(line + "\n")
        gfile.write("\n".join(FOOTER) + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python wheel_centers_to_gcode.py wheel_centers.csv [output.gcode]")
        sys.exit(1)
    csv_path = sys.argv[1]
    gcode_path = sys.argv[2] if len(sys.argv) > 2 else "wheel_centers_out.gcode"
    csv_to_gcode(csv_path, gcode_path)
    print(f"Wrote G-code to {gcode_path}")
