#!/bin/bash

#
# JoinPlots - Combine multiple PDF files into a single PDF with horizontal or vertical layout
#
# Description:
#   This script uses LaTeX to combine multiple PDF files into a single PDF document
#   with images arranged either horizontally (in a row) or vertically (stacked).
#   The output is automatically cropped to remove margins and whitespace.
#
# Features:
#   - Supports any number of input PDFs
#   - Preserves aspect ratio of all images
#   - Creates tightly cropped output
#   - Horizontal or vertical layouts
#   - Custom output filename support
#
# Dependencies:
#   - pdflatex (TeX Live or equivalent)
#   - pdfcrop (usually comes with TeX Live)
#
# Copyright (c) 2025, Pau Amaro Seoane
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# Default values
layout="horizontal"
output_base="Tex_joined"
help_flag=0
error_flag=0

# Display help information
show_help() {
    cat <<-EOF
Usage: $0 [OPTIONS] FILE1 FILE2 [FILE3 ...]

Join multiple PDF files into a single PDF using LaTeX.

Options:
  -h, --help        Show this help message and exit
  -H, --horizontal  Arrange images horizontally (default)
  -V, --vertical    Arrange images vertically
  -o, --output FILE Specify output file (default: /tmp/Tex_joined-crop.pdf)

Examples:
  $0 --vertical 1.pdf 2.pdf 3.pdf
  $0 -H -o combined.pdf a.pdf b.pdf c.pdf
  $0 --horizontal *.pdf
EOF
}

# Parse command line arguments
files=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            help_flag=1
            shift
            ;;
        -H|--horizontal)
            layout="horizontal"
            shift
            ;;
        -V|--vertical)
            layout="vertical"
            shift
            ;;
        -o|--output)
            output_file="$2"
            shift 2
            ;;
        -*)
            echo "Error: Unknown option $1" >&2
            error_flag=1
            shift
            ;;
        *)
            files+=("$1")
            shift
            ;;
    esac
done

# Handle help and error flags
if [[ $help_flag -eq 1 ]]; then
    show_help
    exit 0
fi

if [[ $error_flag -eq 1 ]]; then
    echo "Use -h for help" >&2
    exit 1
fi

# Validate input files
if [[ ${#files[@]} -lt 1 ]]; then
    echo "Error: At least 1 PDF file is required" >&2
    echo "Use -h for help" >&2
    exit 1
fi

for file in "${files[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "Error: File '$file' not found" >&2
        exit 1
    fi
done

# Set default output file if not specified
if [[ -z "$output_file" ]]; then
    output_file="/tmp/${output_base}-crop.pdf"
fi

# Create working directory in /tmp
work_dir=$(mktemp -d "/tmp/pdf_join_XXXXXX")
tex_file="${work_dir}/${output_base}.tex"
pdf_file="${work_dir}/${output_base}.pdf"
log_file="${work_dir}/pdflatex.log"

# Get absolute paths for input files
abs_files=()
for file in "${files[@]}"; do
    abs_files+=("$(realpath "$file")")
done

# Generate LaTeX document
cat > "$tex_file" <<-EOF
\\documentclass{article}
\\usepackage[a4paper,verbose]{geometry}
\\usepackage{graphicx}
\\usepackage{calc}
\\pagestyle{empty}
\\setlength{\\parindent}{0pt}
\\begin{document}
\\centering
EOF

if [[ "$layout" == "horizontal" ]]; then
    # Horizontal layout using minipages
    width=$(awk -v n=${#files[@]} 'BEGIN { printf "%.3f", 1.0/n }')
    echo "\\begin{minipage}{\\textwidth}%" >> "$tex_file"
    for file in "${abs_files[@]}"; do
        echo "\\begin{minipage}{${width}\\textwidth}%" >> "$tex_file"
        echo "\\includegraphics[width=\\linewidth,height=0.95\\textheight,keepaspectratio]{${file}}%" >> "$tex_file"
        echo "\\end{minipage}%" >> "$tex_file"
    done
    echo "\\end{minipage}" >> "$tex_file"
else
    # Vertical layout
    for file in "${abs_files[@]}"; do
        echo "\\begin{minipage}{\\textwidth}%" >> "$tex_file"
        echo "\\includegraphics[width=\\linewidth,height=0.95\\textheight,keepaspectratio]{${file}}%" >> "$tex_file"
        echo "\\end{minipage}\\\\" >> "$tex_file"
    done
fi

echo "\\end{document}" >> "$tex_file"

# Compile LaTeX document
if ! pdflatex -interaction=nonstopmode -output-directory="$work_dir" "$tex_file" > "$log_file" 2>&1; then
    echo "LaTeX compilation failed. See log: $log_file" >&2
    echo "Temporary files kept in: $work_dir" >&2
    exit 1
fi

# Crop PDF
if ! pdfcrop --margins 0 "$pdf_file" "$output_file" >> "$log_file" 2>&1; then
    echo "PDF cropping failed. See log: $log_file" >&2
    echo "Temporary files kept in: $work_dir" >&2
    exit 1
fi

# Clean up temporary files
rm -rf "$work_dir"

echo "Successfully created: $output_file"
exit 0
