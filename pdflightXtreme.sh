#!/bin/sh

# Make a copy
cp $1 $1_bak

# Crop pdf
pdfcrop $1 $1

# Convert to png
gs -dQUIET -dBATCH -dNOPAUSE -dNOPROMPT -sDEVICE=png16m \
   -dTextAlphaBits=4 -dGraphicsAlphaBits=4 "-r300x300"  \
   -sOutputFile=`basename $1 .pdf`.png $1

# Convert to pdf
convert `basename $1 .pdf`.png $1

# Remove png
rm `basename $1 .pdf`.png
