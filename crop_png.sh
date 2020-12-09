#!/bin/sh

# Believe it or not, this crops a png file

for file in $(ls *.png)
do convert -trim $file `basename $file .png`.png ;
done
