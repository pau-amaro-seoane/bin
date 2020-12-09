#!/bin/sh

# This is a dummy script which uses
# gnuplot and GpTex -p assuming that
# gnuplot exports always to out.tex
# to then open it with a pdf viewer

# Look for a viewer

EVINCE=`which evince 2> /dev/null`
ATRIL=`which atril 2> /dev/null`
MUPDF=`which mupdf 2> /dev/null`
XPDF=`which xpdf 2> /dev/null`

# Define an openpdf function

openpdf () {
   if [ -f out.pdf ] ; then
                         if [ -s $EVINCE ]
                          then $EVINCE out.pdf
                             else
                              if [ -s $ATRIL ]
                              then $ATRIL out.pdf
                                else $MUPDF out.pdf
                              if [ -s $XPDF ]
                                then $XPDF out.pdf
                                 else echo "You don't either evince, nor atril, nor mupdf nor xpdf... I give up."
                                fi
                              fi
                        fi
   else
       echo "MMmh... there is no out.pdf, I think you have a virus."
   fi
 }


# Check if you are a macuser

if [[ "$OSTYPE" == "darwin"* ]]; then 
    echo "Macuser detected (ffs... why??)"
    gnuplot $1
    $HOME/bin/GpTex.sh -p out.tex
    open ./out.pdf
    rm out.tex
else
    gnuplot $1
    $HOME/bin/GpTex.sh -p out.tex
    openpdf ./out.pdf
    rm out.tex
fi
