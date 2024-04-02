#!/bin/sh

tar cvfz images.tar.gz `cat $1 | grep "includegraphics" | grep -v "^%" | sed 's/]/\ /g' | awk '{print $2}' | sed 's/{//g' | sed 's/}//g' `
