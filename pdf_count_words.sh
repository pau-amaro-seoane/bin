#!/bin/sh
NRWORDS=`pdftotext $1  - | tr -d '.' | wc -w |sed 's/    //g'`
echo "   $1 has $NRWORDS words"
