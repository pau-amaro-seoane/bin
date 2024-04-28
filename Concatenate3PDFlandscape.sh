#!/bin/sh

echo "Usage: ConcatenatePDFlandscape 1.pdf 2.pdf 3.pdf ... "

pdfjam $1 $2 $3 --nup 3x1 --landscape --pdfauthor "Pau Amaro Seoane" --outfile OUT.pdf
pdfcrop OUT.pdf OUT.pdf
