#!/bin/sh
pdfjam --nup 2x1 --landscape --outfile output.pdf $1 $2
pdfcrop output.pdf output.pdf
