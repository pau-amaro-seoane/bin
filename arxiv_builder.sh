#!/bin/bash


# ==============================================================================
# SCRIPT: arxiv_builder.sh
# DESCRIPTION:
#   This script automates the creation of a submission tarball for arXiv.
#   It performs the following operations:
#
#   1. STAGING: Creates a temporary staging directory to avoid modifying source files.
#
#   2. CLEANING:
#      - Removes comments strictly at the beginning of lines (^%) to preserve
#        inline comments and URL percentages.
#      - Removes specific invisible character (NBSP) with sed -i 's/\xc2\xa0/ /g' main.tex  
#      - Renames the input TeX file to 'main.tex' (arXiv standard).
#
#   3. BIBLIOGRAPHY INJECTION (The "Camera-Ready" Step):
#      - Locates the corresponding .bbl file (must match input filename).
#      - Removes the \bibliographystyle{...} command from the TeX.
#      - Replaces the \bibliography{...} command with the actual contents of
#        the .bbl file. This ensures the submission is self-contained.
#
#   4. ASSET COLLECTION:
#      - Greps for \includegraphics to find figures.
#      - Copies figures into the staging area, preserving their directory structure.
#      - Scans for and copies local .sty, .cls, and .bst files.
#
#   5. PACKAGING:
#      - Creates 'submission.tar.gz' containing the flat 'main.tex' and assets.
#
# USAGE:
#   ./arxiv_builder.sh <your_file.tex>
#
# EXPECTS:
#   - Run from the directory containing the .tex file.
#   - A .bbl file *with the same basename* must exist (generate via Overleaf/BibTeX).
#
# LICENSE: ISC License
# ==============================================================================
# Copyright (c) Pau Amaro Seoane 2026 (time flieeees!)
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
# OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.
# ==============================================================================


# Check Arguments
if [ -z "$1" ]; then
    echo "Usage: $0 <filename.tex>"
    exit 1
fi

INPUT_TEX="$1"
ARCHIVE_NAME="submission.tar.gz"
TEMP_DIR="arxiv_staging_temp"

# Verify Input
if [ ! -f "$INPUT_TEX" ]; then
    echo "Error: File '$INPUT_TEX' not found."
    exit 1
fi

# Cleanup previous runs
rm -rf "$TEMP_DIR"
rm -f "$ARCHIVE_NAME"
mkdir -p "$TEMP_DIR"

echo "--- Initializing arXiv Builder ---"
echo "Processing: $INPUT_TEX"

# ---------------------------------------------------------
# Step 1: Clean Comments & Rename
# ---------------------------------------------------------
echo "[1/4] Cleaning comments and creating main.tex..."

# 1. Remove lines starting with % and write to the temp directory
sed '/^%/d' "$INPUT_TEX" > "$TEMP_DIR/main.tex"

# 2. Remove Non-Breaking Spaces (NBSP) from the new main.tex
#    (This is the new line)
sed -i 's/\xc2\xa0/ /g' "$TEMP_DIR/main.tex"

# ---------------------------------------------------------
# Step 2: Inject Bibliography (.bbl)
# ---------------------------------------------------------
echo "[2/4] Injecting .bbl content..."

BASENAME=$(basename "$INPUT_TEX" | sed 's/\.[^.]*$//')
BBL_FILE="${BASENAME}.bbl"

if [ -f "$BBL_FILE" ]; then
    echo "      Found '$BBL_FILE'. replacing \bibliography command..."

    # We use Perl for robust multiline replacement.
    # 1. It reads the .bbl file content into variable $bbl
    # 2. It removes \bibliographystyle
    # 3. It finds \bibliography{...} and replaces it with $bbl content
    
    perl -i -0777 -pe '
        BEGIN {
            open(my $fh, "<", "'"$BBL_FILE"'") or die "Cannot open .bbl file: $!";
            local $/;
            $bbl = <$fh>;
            close($fh);
        }
        # Remove bibliographystyle (multiline safe)
        s/\\bibliographystyle\s*\{.*?\}/% \\bibliographystyle removed/gs;
        
        # Replace bibliography command with actual BBL content
        s/\\bibliography\s*\{.*?\}/$bbl/gs;
    ' "$TEMP_DIR/main.tex"
    
    echo "      Success: Bibliography injected."
else
    echo "      WARNING: '$BBL_FILE' not found!"
    echo "      Could not inject bibliography. Submission may fail on arXiv."
fi

# ---------------------------------------------------------
# Step 3: Collect Assets (Figures & Styles)
# ---------------------------------------------------------
echo "[3/4] Collecting figures and styles..."

# A. Styles
for stylefile in *.bst *.sty *.cls; do
    [ -e "$stylefile" ] || continue
    cp "$stylefile" "$TEMP_DIR/"
    echo "      Included style: $stylefile"
done

# B. Figures
# Grep for \includegraphics, extract content inside {}, ignoring options []
FIG_REFS=$(grep -oP '\\includegraphics(\[.*?\])?\{\K[^}]+' "$INPUT_TEX")

for fig in $FIG_REFS; do
    fig=$(echo "$fig" | xargs) # Trim whitespace
    
    FILE_TO_COPY=""
    if [ -f "$fig" ]; then
        FILE_TO_COPY="$fig"
    else
        # Try extensions
        for ext in .pdf .png .jpg .jpeg .eps; do
            if [ -f "${fig}${ext}" ]; then
                FILE_TO_COPY="${fig}${ext}"
                break
            fi
        done
    fi

    if [ -n "$FILE_TO_COPY" ]; then
        # Maintain directory structure (e.g. figures/plot.pdf)
        DIRNAME=$(dirname "$FILE_TO_COPY")
        mkdir -p "$TEMP_DIR/$DIRNAME"
        cp "$FILE_TO_COPY" "$TEMP_DIR/$FILE_TO_COPY"
        echo "      Included figure: $FILE_TO_COPY"
    else
        echo "      WARNING: Figure '$fig' referenced but not found."
    fi
done

# ---------------------------------------------------------
# Step 4: Compress
# ---------------------------------------------------------
echo "[4/4] Creating archive..."

cd "$TEMP_DIR" || exit
tar -czvf "../$ARCHIVE_NAME" ./*
cd ..
rm -rf "$TEMP_DIR"

echo "--- Done! ---"
echo "Submission ready: $ARCHIVE_NAME"
