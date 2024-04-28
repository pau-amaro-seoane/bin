#!/bin/sh

cp $1 $1_bak

gs -dQUIET -dBATCH -dNOPAUSE -dNOPROMPT -sDEVICE=png16m \
   -dTextAlphaBits=4 -dGraphicsAlphaBits=4 "-r300x300"  \
   -sOutputFile=`basename $1 .pdf`.png $1

convert `basename $1 .pdf`.png $1
rm `basename $1 .pdf`.png
