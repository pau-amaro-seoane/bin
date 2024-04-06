#!/bin/sh

# This script renames files with blank characters, but also
# anything which could pose a problem in a proper OS.
# 
# Pau Amaro Seoane, Berlin

ls | while read -r FILE
do
    mv "$FILE" `echo $FILE | tr ' ' '_' | tr -d '[{}(),\!]' | tr -d "\'" | sed 's/_-_/_/g'`
done
