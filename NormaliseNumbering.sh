#!/usr/bin/env zsh

# Normalise numbering
# ===================
# The script is designed to rename files in a specified directory by normalizing
# the numeric parts of their filenames to have consistent zero padding, based on
# the largest number found among all filenames. It first identifies the maximum
# number present in any file name by extracting digits, comparing them, and
# determining the highest value. Then, it calculates how many digits this largest
# number contains to establish a uniform format for all numbers. The script loops
# through each file, extracts each numeric sequence, and reformats it by adding
# the necessary number of leading zeros so that all numeric parts across all
# filenames have the same length. This padding ensures that the files are sorted
# numerically when listed, facilitating easier management and access. The script
# handles filenames with multiple numeric parts by processing each number
# separately, and it avoids overwriting any files by checking if the new filename
# already exists before renaming. This automation is particularly useful for
# maintaining orderly file systems where files are numerically sequenced and
# require systematic organizatio
# 
# License
# =======
# Copyright 2024 Pau Amaro Seoane
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
    echo "$1" | grep -o '[0-9]\+'
}

# Find the largest number in filenames
max_num=0
for file in *; do
    num=$(extract_number "$file" | sort -nr | head -1)
    if [[ "$num" -gt "$max_num" ]]; then
        max_num="$num"
    fi
done

# Determine the number of digits in the largest number
max_digits=${#max_num}

# Rename files to include leading zeros in the numbers
for file in *; do
    # Extract all numbers from the filename, and process each
    numbers=$(extract_number "$file")
    new_filename="$file"
    for num in $numbers; do
        # Determine how many leading zeros are needed
        num_digits=${#num}
        required_zeros=$((max_digits - num_digits))

        # Generate the new number with leading zeros
        new_num=$(printf "%0${max_digits}d" "$num")

        # Construct the new filename
        new_filename=$(echo "$new_filename" | sed "s/$num/$new_num/")

    done

    # Rename the file if the new filename is different from the old one
    if [[ "$file" != "$new_filename" ]]; then
        mv "$file" "$new_filename"
    fi
done

echo "File renaming complete."
