#!/bin/sh
splash `ls snapshot* | sort -V`
FITXTEMP=`mktemp`
\ls *.png | \sort -V -o $FITXTEMP
#mencoder mf://@$FITXTEMP -mf w=800:h=600:fps=5:type=png \
mencoder mf://@$FITXTEMP -mf fps=1:type=png \
      -ovc lavc -lavcopts vcodec=mpeg4:mbd=2:trell -oac copy -o output.avi
