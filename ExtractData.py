
#!/usr/bin/env python3
"""
=============================================================================
STANDALONE VECTOR DATA EXTRACTOR (PDF, EPS, PS)
=============================================================================

DESCRIPTION:
    This tool recovers numerical data points (X, Y) from vector-based scientific
    plots saved as PDF, EPS, or PostScript files. It is useful for recovering
    lost data from old publications or extracting data from generated charts.

    It is completely standalone and requires NO external dependencies.

HOW IT WORKS:
    1. FORMAT DETECTION:
       - PostScript/EPS: Parsed as plain text.
       - PDF: Parsed as a binary container. The script heuristically scans for
         internal data streams (zlib compressed) and extracts the vector
         drawing commands without needing a full PDF library.

    2. VECTOR PARSING:
       It interprets standard vector commands used by plotting libraries
       (Matplotlib, Gnuplot, etc.):
       - 'moveto' (m): Start a new line.
       - 'lineto' (l): Draw a line to a coordinate.
       - 'rlineto' (V): Draw a line relative to the last point.

    3. HEURISTIC FILTERING:
       Scientific plots consist of data curves (long continuous lines) and
       decorations (axes, ticks, grids - usually short lines). This script
       automatically discards segments with fewer than 10 points to isolate
       the data.

    4. CALIBRATION (Mapping Page Units to Physical Data):
       PostScript defines coordinates in "points" (1/72 inch). If you provide
       the physical axis limits (e.g., Time 0-100, Amp -1 to 1), the script
       will automatically scale the raw page coordinates to your data units.

USAGE EXAMPLES:

    1. Raw Extraction (No Calibration):
       Outputs raw page coordinates. Useful for quick checks.
       $ python ExtractData.py myplot.pdf

    2. Linear Calibration:
       Map X to [0, 100] and Y to [-5, 5].
       $ python ExtractData.py myplot.pdf --xmin 0 --xmax 100 --ymin -5 --ymax 5

    3. Logarithmic Calibration:
       Map X linearly [0, 50], Y logarithmically [1e-2, 1e2].
       $ python ExtractData.py myplot.eps --xmin 0 --xmax 50 --ymin 0.01 --ymax 100 --logy

OUTPUT:
    Creates 'filename.txt' with two columns (X Y).

COPYRIGHT:

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
import re
import zlib

# =============================================================================
# PDF STREAM EXTRACTOR (Heuristic)
# Replaces pypdf with standard library logic to keep script standalone.
# =============================================================================
def extract_pdf_content(filename):
    """
    Scans a PDF file for internal streams, attempts to decompress them,
    and returns a concatenated string of valid PostScript-like commands.
    """
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        return ""

    # Regex to find stream blocks: stream\r\n ... \r\nendstream
    # We capture the content between the keywords.
    stream_pattern = re.compile(rb'stream[\r\n]+(.*?)[\r\n]+endstream', re.DOTALL)

    extracted_text = []

    for match in stream_pattern.finditer(data):
        stream_bytes = match.group(1)

        # Attempt 1: Try decompressing (FlateDecode is standard for plots)
        try:
            # zlib.decompress is strict; sometimes PDF streams have header issues.
            # -15 allows raw decompression without zlib headers.
            decompressed = zlib.decompress(stream_bytes)
            text = decompressed.decode('latin-1', errors='ignore')
            extracted_text.append(text)
            continue
        except zlib.error:
            pass

        # Attempt 2: Maybe it's not compressed? (Raw PostScript)
        try:
            text = stream_bytes.decode('latin-1')
            # Heuristic: does it look like vector code?
            if ' m' in text or ' l' in text or ' re' in text:
                extracted_text.append(text)
        except UnicodeDecodeError:
            pass

    return "\n".join(extracted_text)

# =============================================================================
# MAIN PARSING LOGIC
# =============================================================================
def get_plot_commands(filename):
    """Dispatcher: Reads file based on extension."""
    ext = os.path.splitext(filename)[1].lower()

    if ext == '.pdf':
        print("  > PDF detected. Scanning internal streams (heuristic)...")
        content = extract_pdf_content(filename)
        if not content:
            print("  > Warning: No vector data streams found. File might be rasterized images.")
        return content
    else:
        # PostScript / EPS (Text based)
        try:
            with open(filename, 'r', errors='ignore') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: File {filename} not found.")
            sys.exit(1)

def extract_vector_data(input_file, user_limits=None, output_file=None):
    # 1. Determine output filename
    if output_file is None:
        base, _ = os.path.splitext(input_file)
        output_file = f"{base}.txt"

    print(f"Reading from: {input_file}")

    raw_content = get_plot_commands(input_file)

    # 2. Tokenize
    clean_tokens = []
    for line in raw_content.splitlines():
        line = line.split('%')[0] # Strip comments
        clean_tokens.extend(line.split())

    # 3. Parse Vector Commands
    all_segments = []
    current_segment = []

    # Global Bounding Box (Page Coordinates)
    ps_bounds = {'xmin': None, 'xmax': None, 'ymin': None, 'ymax': None}

    def update_bounds(x, y):
        if ps_bounds['xmin'] is None or x < ps_bounds['xmin']: ps_bounds['xmin'] = x
        if ps_bounds['xmax'] is None or x > ps_bounds['xmax']: ps_bounds['xmax'] = x
        if ps_bounds['ymin'] is None or y < ps_bounds['ymin']: ps_bounds['ymin'] = y
        if ps_bounds['ymax'] is None or y > ps_bounds['ymax']: ps_bounds['ymax'] = y

    current_x, current_y = 0.0, 0.0

    i = 0
    while i < len(clean_tokens):
        token = clean_tokens[i]

        try:
            # --- MOVETO (x y m) ---
            if token in ['m', 'M', 'moveto'] and i >= 2:
                x = float(clean_tokens[i-2])
                y = float(clean_tokens[i-1])

                if current_segment:
                    all_segments.append(current_segment)
                    current_segment = []

                current_x, current_y = x, y
                update_bounds(x, y)

            # --- LINETO (x y l) ---
            elif token in ['l', 'L', 'lineto'] and i >= 2:
                x = float(clean_tokens[i-2])
                y = float(clean_tokens[i-1])

                if not current_segment:
                    current_segment.append((current_x, current_y))

                current_segment.append((x, y))
                current_x, current_y = x, y
                update_bounds(x, y)

            # --- RELATIVE LINETO (dx dy V) ---
            elif token in ['V', 'R', 'rmoveto', 'rlineto'] and i >= 2:
                dx = float(clean_tokens[i-2])
                dy = float(clean_tokens[i-1])

                dest_x = current_x + dx
                dest_y = current_y + dy

                if not current_segment:
                    current_segment.append((current_x, current_y))
                    update_bounds(current_x, current_y)

                current_segment.append((dest_x, dest_y))
                current_x, current_y = dest_x, dest_y
                update_bounds(dest_x, dest_y)

            # --- RECTANGLE (x y w h re) --- (PDF specific)
            elif token == 're' and i >= 4:
                x = float(clean_tokens[i-4])
                y = float(clean_tokens[i-3])
                w = float(clean_tokens[i-2])
                h = float(clean_tokens[i-1])

                if current_segment:
                    all_segments.append(current_segment)

                # Treat rectangle as a closed loop
                rect_seg = [(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)]
                all_segments.append(rect_seg)
                current_segment = []
                update_bounds(x, y)
                update_bounds(x+w, y+h)

            # --- STROKE/CLOSE ---
            elif token in ['S', 's', 'stroke', 'h', 'closepath']:
                if current_segment:
                    all_segments.append(current_segment)
                    current_segment = []

        except ValueError:
            pass
        i += 1

    if current_segment:
        all_segments.append(current_segment)

    # 4. Filter Data (Heuristic: length > 10)
    # This removes axes, ticks, and small symbols, keeping the main data curves.
    data_segments = [seg for seg in all_segments if len(seg) > 10]

    print(f"Detected Page Bounds: X[{ps_bounds['xmin']:.1f}:{ps_bounds['xmax']:.1f}] Y[{ps_bounds['ymin']:.1f}:{ps_bounds['ymax']:.1f}]")
    print(f"Filtered out {len(all_segments) - len(data_segments)} short segments (grid/axes).")

    # 5. Conversion Logic
    def convert_value(val, ps_min, ps_max, user_min, user_max, is_log):
        if ps_max == ps_min: return user_min
        # Normalize to 0..1
        norm = (val - ps_min) / (ps_max - ps_min)

        if is_log:
            try:
                log_min = math.log10(user_min)
                log_max = math.log10(user_max)
                return 10 ** (norm * (log_max - log_min) + log_min)
            except ValueError:
                print("Error: User limits must be positive for log scale.")
                sys.exit(1)
        else:
            return norm * (user_max - user_min) + user_min

    # 6. Write Output
    with open(output_file, 'w') as out:
        out.write(f"# Data extracted from {os.path.basename(input_file)}\n")

        if user_limits:
            out.write(f"# Calibrated using: X[{user_limits['xmin']}:{user_limits['xmax']}] Y[{user_limits['ymin']}:{user_limits['ymax']}]\n")
            if user_limits['logx']: out.write("# X-Axis: Logarithmic\n")
            if user_limits['logy']: out.write("# Y-Axis: Logarithmic\n")
            out.write("# Column 1: X (calibrated) Column 2: Y (calibrated)\n")
        else:
            out.write("# Column 1: X (raw coord) Column 2: Y (raw coord)\n")

        total_points = 0
        for segment in data_segments:
            for x_raw, y_raw in segment:
                if user_limits:
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
    parser = argparse.ArgumentParser(
        description="Extract X Y data from PDF, EPS, or PS plots (Standalone).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python ExtractData.py plot.pdf --xmin 0 --xmax 100 --ymin 0 --ymax 1")

    parser.add_argument("filename", help="The file to parse")

    group = parser.add_argument_group('Calibration (Optional)', 'Map coordinates to real data values')
    group.add_argument("--xmin", type=float, help="Left edge value")
    group.add_argument("--xmax", type=float, help="Right edge value")
    group.add_argument("--ymin", type=float, help="Bottom edge value")
    group.add_argument("--ymax", type=float, help="Top edge value")
    group.add_argument("--logx", action="store_true", help="X axis is logarithmic")
    group.add_argument("--logy", action="store_true", help="Y axis is logarithmic")

    args = parser.parse_args()

    limits = None
    if any([args.xmin, args.xmax, args.ymin, args.ymax]):
        if not all([args.xmin is not None, args.xmax is not None, args.ymin is not None, args.ymax is not None]):
            print("Error: For calibration, you must provide ALL bounds: --xmin, --xmax, --ymin, --ymax")
            sys.exit(1)
        limits = {
            'xmin': args.xmin, 'xmax': args.xmax,
            'ymin': args.ymin, 'ymax': args.ymax,
            'logx': args.logx, 'logy': args.logy
        }

    extract_vector_data(args.filename, limits)
