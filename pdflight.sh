#!/bin/sh

# Reduce the size of a pdf file, to be passed as $1

gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook \
   -dNOPAUSE -dQUIET -dBATCH \
   -sOutputFile=output.pdf \
   $1

# replace with -dPDFSETTINGS=/ebook for a higher quality (and larger size)
