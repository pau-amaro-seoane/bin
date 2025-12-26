#!/usr/bin/env python3
"""
=============================================================================
POSTSCRIPT DATA EXTRACTOR & CALIBRATOR
=============================================================================

DESCRIPTION:
    This script recovers numerical data points (X, Y) from vector-based
    PostScript (.ps) or Encapsulated PostScript (.eps) plots.

    Unlike image-based digitization tools (which use OCR or color detection
    on raster pixels), this tool parses the underlying vector drawing commands.
    This results in exact coordinate extraction without pixelation errors.

HOW IT WORKS:
    1. VECTOR PARSING:
       The script reads the file line-by-line, looking for standard PostScript
       path construction operators:
       - 'moveto' (M/m): Starts a new line segment.
       - 'rlineto' (V/R): Adds a point relative to the last point.
       - 'lineto' (L/l): Adds a point at an absolute page coordinate.

    2. BOUNDING BOX DETECTION:
       As it parses, the script tracks the global minimum and maximum
       page coordinates (PostScript points, 1/72 inch) of every vector
       found in the file. This defines the "Page Space."

    3. HEURISTIC FILTERING:
       Scientific plots typically consist of:
       - Short segments: Ticks, axis lines, grid markers, frame borders.
       - Long segments: The actual data curves.
       To isolate the data, this script discards any continuous line segment
       containing fewer than 10 points.

    4. CALIBRATION & COORDINATE TRANSFORMATION:
       If user limits are provided, the script maps "Page Space" to "Data Space":

       a. Normalize page coordinate $P$ to range [0, 1]:
          $Norm = (P - PageMin) / (PageMax - PageMin)$

       b. Map to physical unit $U$:
          - Linear: $U = Norm * (UserMax - UserMin) + UserMin$
          - Log10:  $U = 10 ^ { Norm * (log10(UserMax) - log10(UserMin)) + log10(UserMin) }$

USAGE EXAMPLES:

    1. Raw Extraction (No Calibration):
       Outputs raw PostScript coordinates (useful for debugging).
       $ python ExtractDataPS.py plot.eps

    2. Linear Calibration:
       Map X to [0, 100] and Y to [-5, 5].
       $ python ExtractDataPS.py plot.eps --xmin 0 --xmax 100 --ymin -5 --ymax 5

    3. Logarithmic Calibration:
       Map X linearly [0, 50], Y logarithmically [1e-2, 1e2].
       $ python ExtractDataPS.py plot.eps --xmin 0 --xmax 50 --ymin 0.01 --ymax 100 --logy

ARGUMENTS:
    filename    : The input .ps or .eps file.
    --xmin, max : The physical X-axis limits of the plot.
    --ymin, max : The physical Y-axis limits of the plot.
    --logx, y   : Flags to indicate if an axis uses a logarithmic scale.

OUTPUT:
    A text file (filename.txt) containing two columns (X Y).
    Segments are separated by a blank line. Header contains metadata.

Pau Amaro Seoane, Berlin, 26 December 2025

ISC License

Copyright 2025 Pau Amaro Seoane

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.

=============================================================================
"""
import sys
import os
import argparse
import math

def extract_ps_data(input_file, user_limits=None, output_file=None):
    # 1. Determine output filename
    if output_file is None:
        base, _ = os.path.splitext(input_file)
        output_file = f"{base}.txt"

    print(f"Reading from: {input_file}")
    
    try:
        with open(input_file, 'r') as f:
            content = f.readlines()
    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
        sys.exit(1)

    # 2. Parse PostScript
    # We collect ALL segments first to determine the plot bounding box.
    all_segments = []
    current_segment = []
    
    # Track the global min/max of the PostScript coordinates (page layout)
    # Initialize with None
    ps_bounds = {'xmin': None, 'xmax': None, 'ymin': None, 'ymax': None}

    def update_bounds(x, y):
        if ps_bounds['xmin'] is None or x < ps_bounds['xmin']: ps_bounds['xmin'] = x
        if ps_bounds['xmax'] is None or x > ps_bounds['xmax']: ps_bounds['xmax'] = x
        if ps_bounds['ymin'] is None or y < ps_bounds['ymin']: ps_bounds['ymin'] = y
        if ps_bounds['ymax'] is None or y > ps_bounds['ymax']: ps_bounds['ymax'] = y

    current_x, current_y = 0.0, 0.0
    
    for line in content:
        line = line.strip()
        tokens = line.split()
        
        if not tokens:
            continue
            
        cmd = tokens[-1]

        try:
            if cmd in ['M', 'm', 'moveto']:
                if len(tokens) >= 3:
                    if current_segment:
                        all_segments.append(current_segment)
                        current_segment = []
                    current_x = float(tokens[-3])
                    current_y = float(tokens[-2])
                    # Moves also define the plot area boundaries
                    update_bounds(current_x, current_y)
            
            elif cmd in ['V', 'R', 'rmoveto', 'rlineto']:
                if len(tokens) >= 3:
                    dx = float(tokens[-3])
                    dy = float(tokens[-2])
                    if not current_segment:
                        current_segment.append((current_x, current_y))
                        update_bounds(current_x, current_y)
                    
                    current_x += dx
                    current_y += dy
                    current_segment.append((current_x, current_y))
                    update_bounds(current_x, current_y)

            elif cmd in ['L', 'l', 'lineto']:
                if len(tokens) >= 3:
                    if not current_segment:
                        current_segment.append((current_x, current_y))
                        update_bounds(current_x, current_y)
                    
                    current_x = float(tokens[-3])
                    current_y = float(tokens[-2])
                    current_segment.append((current_x, current_y))
                    update_bounds(current_x, current_y)
            
            elif cmd in ['stroke', 'S']:
                if current_segment:
                    all_segments.append(current_segment)
                    current_segment = []

        except (ValueError, IndexError):
            continue

    if current_segment:
        all_segments.append(current_segment)

    # 3. Filter Data
    # Keep segments with > 10 points (likely data). Discard axes/ticks/grids.
    data_segments = [seg for seg in all_segments if len(seg) > 10]
    
    print(f"Detected Page Bounds: X[{ps_bounds['xmin']:.1f}:{ps_bounds['xmax']:.1f}] Y[{ps_bounds['ymin']:.1f}:{ps_bounds['ymax']:.1f}]")
    print(f"Filtered out {len(all_segments) - len(data_segments)} short segments (grid/axes).")

    # 4. Conversion Logic
    def convert_value(val, ps_min, ps_max, user_min, user_max, is_log):
        # Normalize to 0..1 based on the Page Bounding Box
        if ps_max == ps_min: return user_min
        norm = (val - ps_min) / (ps_max - ps_min)
        
        if is_log:
            # Logarithmic Interpolation: value = 10^( norm * log_range + log_min )
            try:
                log_min = math.log10(user_min)
                log_max = math.log10(user_max)
                return 10 ** (norm * (log_max - log_min) + log_min)
            except ValueError:
                print("Error: User limits must be positive for log scale.")
                sys.exit(1)
        else:
            # Linear Interpolation
            return norm * (user_max - user_min) + user_min

    # 5. Write Output
    with open(output_file, 'w') as out:
        out.write(f"# Data extracted from {os.path.basename(input_file)}\n")
        
        if user_limits:
            out.write(f"# Calibrated using limits: X[{user_limits['xmin']}:{user_limits['xmax']}] Y[{user_limits['ymin']}:{user_limits['ymax']}]\n")
            if user_limits['logx']: out.write("# X-Axis: Logarithmic\n")
            if user_limits['logy']: out.write("# Y-Axis: Logarithmic\n")
            out.write("# Column 1: X (calibrated) Column 2: Y (calibrated)\n")
        else:
            out.write("# Column 1: X (raw ps) Column 2: Y (raw ps)\n")
        
        total_points = 0
        for segment in data_segments:
            for x_raw, y_raw in segment:
                if user_limits:
                    # Apply calibration
                    x_out = convert_value(x_raw, ps_bounds['xmin'], ps_bounds['xmax'], 
                                        user_limits['xmin'], user_limits['xmax'], user_limits['logx'])
                    y_out = convert_value(y_raw, ps_bounds['ymin'], ps_bounds['ymax'], 
                                        user_limits['ymin'], user_limits['ymax'], user_limits['logy'])
                else:
                    x_out, y_out = x_raw, y_raw

                out.write(f"{x_out:.6f} {y_out:.6f}\n")
                total_points += 1
            out.write("\n")
                
    print(f"Done. Wrote {total_points} points to '{output_file}'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract and calibrate data from PostScript plots.")
    parser.add_argument("filename", help="The .ps or .eps file to parse")
    
    # Calibration Arguments
    group = parser.add_argument_group('Calibration (Optional)', 'Map raw PS coordinates to real data values')
    group.add_argument("--xmin", type=float, help="Data value at the left edge")
    group.add_argument("--xmax", type=float, help="Data value at the right edge")
    group.add_argument("--ymin", type=float, help="Data value at the bottom edge")
    group.add_argument("--ymax", type=float, help="Data value at the top edge")
    group.add_argument("--logx", action="store_true", help="X axis is logarithmic")
    group.add_argument("--logy", action="store_true", help="Y axis is logarithmic")

    args = parser.parse_args()
    
    # Check if user provided ALL limits (partial limits are ambiguous)
    limits = None
    if any([args.xmin, args.xmax, args.ymin, args.ymax]):
        if not all([args.xmin is not None, args.xmax is not None, args.ymin is not None, args.ymax is not None]):
            print("Error: If calibrating, you must provide ALL bounds: --xmin, --xmax, --ymin, --ymax")
            sys.exit(1)
        limits = {
            'xmin': args.xmin, 'xmax': args.xmax,
            'ymin': args.ymin, 'ymax': args.ymax,
            'logx': args.logx, 'logy': args.logy
        }

    extract_ps_data(args.filename, limits)
