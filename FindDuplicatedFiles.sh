#!/usr/bin/env zsh

find . -type f | sort -t '/' -k2 | awk -F/ '{
    filename=$NF
    if (seen[filename]++) {
        duplicates[filename]=1
    }
    paths[filename]=paths[filename] ? paths[filename]"\n"$0 : $0
}
END {
    for (filename in duplicates) {
        print "\nDuplicate filename:\n "filename"\nFound in folders:\n"paths[filename]""
    }
}'

