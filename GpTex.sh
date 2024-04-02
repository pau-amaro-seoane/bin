#!/bin/sh
#
# This script is meant to quickly and silently produce an eps
# from a File.tex and File.eps created with gnuplot. 
#
#  Usage:  GpTex.sh [-p] filename
#
#  -p  optional, to convert to pdf and crop the file.  
#      This runs epstopdf and pdfcrop if -p is present.
#
#  filename  -- input file.  Presumed to be filename.tex
#
#
# You have to use the epslatex in gnuplot. This is an
# example:
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# set terminal epslatex          <---                                     %
# set output "MyFile.tex"        <---                                     %
# set xlabel "Time ($10^9$ sec)"                                          %
# set ylabel "$e_{\\bullet}$"                                             %
# set mxtics 5                                                            %
# set mytics 5                                                            %
# set nokey                                                               %
#                                                                         %
# plot './orbital_elements.dat' u ($1/1e+9):2 ls 1 w l smooth csplines, \ %
#      'orbital_elements2.dat' u ($1/1e+9):2 ls 1 w l smooth csplines     %
#                                                                         %
# set terminal x11                                                        %
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
#
# All latex symbols need to be protected with a second backslash: \\
#
# Write the above script as MyScript.gnuplot and run
# $ gnuplot MyScript.gnuplot
# This produces a .tex file, which is the argument of GpTex.sh
# 
# Pau Amaro Seoane, 20/09/2011, Berlin 
#
#  Note:
#  I've used redirect to /dev/null to quiet LaTeX and dvips output
#  To restore the noise, simply remove those redirects.
#
#

template()
{
	cat <<__EOF__
\documentclass{article}
\usepackage{graphics}
\usepackage{nopageno}
\usepackage{txfonts}
\usepackage{wasysym}
%\usepackage{usenames}
\usepackage{color}
\usepackage{moresize}
\usepackage[scientific-notation=true]{siunitx}
\newcommand{\hl}[1]{\setlength{\fboxsep}{0.75pt}\colorbox{white}{#1}}

%\usepackage[default]{cantarell} %% Use option "defaultsans" to use cantarell as sans serif only
%\usepackage[T1]{fontenc}

\begin{document}
\begin{center}
\input{${FILESTUB}.tex}
\end{center}
\end{document}
__EOF__

}

args=`getopt p $*`

if [ $? -ne 0 ]; then
	cat <<__EOF__
Usage:  $0: [-p] filename
	-p  optional.  Do the epstopdf and pdfcrop if -p is present.
	filename  -- input file.  Presumed to be filename.tex
__EOF__
	exit 1;
fi

set -- $args

dopdf=0

while [ $# -ge 0 ]
	do
		case "$1" in
			-p) dopdf=1; shift;;
			--) shift; break;;
		esac
	done

if [ $# -eq 0 ]; then
	echo Filename is missing.  Usage: $0 filename
	exit 1
elif [ $# -gt 1 ]; then
	shift
	echo Extraneous stuff on command line: $@
	exit 1
fi

FILESTUB=${1%%.*}

if [ ! -f ${FILESTUB}.tex ]; then
	echo File ${FILESTUB}.tex not found.
	exit 1
fi
if [ ! -f ${FILESTUB}.eps ]; then
	echo File ${FILESTUB}.eps not found.
	exit 1
fi

# The following block is obsolete; look at the explanation below %%%%%%%%%%%
# regarding set format y "10^{%L}"                                         %
#                                                                          %
# Use powers of ten instead of 1e+ or 1e- in the TeX                       %
#                                                                          %
# 1- First step converts from 1eX to $10^{X}$                              %
# 2- First step removes leading zeroes in the negative exponents           %
# 3- First step removes leading zeroes in the positive exponents           %
#                                                                          %
#sed 's/ 1e+\{0,1\}\(-\{0,1\}[0-9]*\)/$10^{\1}$/g' ${FILESTUB}.tex  | \    %
#  sed 's/{-0\(.*\)/{-\1/' |\                                              %
#  sed 's/{0\(.*\)/{\1/' > TMP                                             %
#                                                                          %
#mv TMP ${FILESTUB}.tex %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


# Produces texput.dvi
# -interaction scrollmode to avoid problems with 
#      set format y "10^{%L}"
# because latex thinks $ are missing
template | latex -interaction scrollmode >/dev/null 2>&1
#template | latex >/dev/null 2>&1

#Produces STUB.ps
dvips texput.dvi -o ${FILESTUB}.ps >/dev/null 2>&1

if [ ! -e ${FILESTUB}.ps ]; then
	cat <<__EOF__

${FILESTUB}.ps does not exist after running dvips.
Something evil has happened.  Maybe you have a virus.
__EOF__
	exit 1
fi

# -pdf stuff

if [ $dopdf -eq 1 ]; then
	epstopdf ${FILESTUB}.ps >/dev/null 2>&1
	pdfcrop ${FILESTUB}.pdf >/dev/null 2>&1
	mv ${FILESTUB}-crop.pdf ${FILESTUB}.pdf
fi

rm -f texput.* 
rm ${FILESTUB}.tex
rm ${FILESTUB}.ps
rm ${FILESTUB}.eps

exit 0

# Update, 22 April 2020, Berlin

# The gnu script should output to out.tex always to avoid
# errors; I have overwritten often the gnu file by mistake
# A possible script to use would be:
#
##!/bin/sh
#
## This is a dummy script which uses
## gnuplot and GpTex -p assuming that
## gnuplot exports always to out.tex
## to then open it with a pdf viewer
#
## Look for a viewer
#
#EVINCE=`which evince 2> /dev/null`
#ATRIL=`which atril 2> /dev/null`
#MUPDF=`which mupdf 2> /dev/null`
#XPDF=`which xpdf 2> /dev/null`
#
## Define an openpdf function
#
#openpdf () {
#   if [ -f out.pdf ] ; then
#                         if [ -s $EVINCE ]
#                          then $EVINCE out.pdf
#                             else
#                              if [ -s $ATRIL ]
#                              then $ATRIL out.pdf
#                                else $MUPDF out.pdf
#                              if [ -s $XPDF ]
#                                then $XPDF out.pdf
#                                 else echo "You don't either evince, nor atril, nor mupdf nor xpdf... I give up."
#                                fi
#                              fi
#                        fi
#   else
#       echo "MMmh... there is no out.pdf, I think you have a virus."
#   fi
# }
#
#
## Check if you are a macuser
#
#if [[ "$OSTYPE" == "darwin"* ]]; then 
#    echo "Macuser detected (ffs... why??)"
#    gnuplot $1
#    $HOME/bin/GpTex.sh -p out.tex
#    open ./out.pdf
#    rm out.tex
#else
#    gnuplot $1
#    $HOME/bin/GpTex.sh -p out.tex
#    openpdf ./out.pdf
#    rm out.tex
#fi
