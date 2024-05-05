#!/usr/bin/env zsh

# Normalize File Numbering
#
# This shell script normalizes the number of digits in file names within a
# specified directory. It identifies the largest numerical value in any file
# name, calculates the necessary number of leading zeros to equalize the length
# of all numbers, and renames each file accordingly. This ensures consistent file
# naming conventions, facilitating easier sorting and access. The script works
# regardless of the position of the number within the filename and maintains the
# non-numeric parts of the filename and file extension unchanged.
# 
# ISC License
# 
# Copyright (c) 2024, Pau Amaro Seoane
# 
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
# 
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.


# Function to extract the numeric part from filenames
extract_number() {
    echo "$1" | grep -o '[0-9]\+' | head -1
}

# Find the largest number in filenames
max_num=0
for file in *; do
    num=$(extract_number "$file")
    if [[ "$num" -gt "$max_num" ]]; then
        max_num="$num"
    fi
done

# Determine the number of digits in the largest number
max_digits=${#max_num}

# Rename files to include leading zeros in the numbers
for file in *; do
    # Extract the number from the filename
    num=$(extract_number "$file")
    if [[ ! -z "$num" ]]; then
        # Determine how many leading zeros are needed
        num_digits=${#num}
        required_zeros=$((max_digits - num_digits))

        # Generate the new number with leading zeros
        new_num=$(printf "%0${required_zeros}d%s" 0 "$num")

        # Construct the new filename
        new_filename=$(echo "$file" | sed "s/$num/$new_num/")

        # Rename the file if the new filename is different from the old one
        if [[ "$file" != "$new_filename" ]]; then
            mv "$file" "$new_filename"
        fi
    fi
done

echo "File renaming complete."
