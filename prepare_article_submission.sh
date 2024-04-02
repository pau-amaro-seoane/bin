#!/bin/sh

# Remove all comments from a tex file, look for the
# figures that we are using in it, and create a 
# tar.gz of the result in /tmp for submission.

echo ""
echo "Have you embedded the bbl file into the tex file?"
echo ""
read answer
case $answer in
yes|Yes|y|Y|S|s)
    cat $1 | sed '/^%/ d' > output.tex
    echo ""
    echo "Removed all comments from the tex."
    sleep 1
    echo ""
    echo "The figures that are being actively used in the tex are: "
    echo ""
    sleep 1
    cat output.tex | grep "includegraphics" | grep -v "^%" | sed 's/]/\ /g' | awk '{print $2}' | sed 's/{//g' | sed 's/}//g'
    echo ""
    echo "Preparing a targz with the tex and figures..."
    sleep 1
    mv output.tex p.tex
    tar cvfz  /tmp/$$.tar.gz /tmp/p.tex `cat output.tex | grep "includegraphics" | grep -v "^%" | sed 's/]/\ /g' | awk '{print $2}' | sed 's/{//g' | sed 's/}//g' `
    echo ""
    echo "Tex file without comments and figures compressed in /tmp/$$.tar.gz"
    echo ""
    rm p.tex
;;
no|n|N)
echo ""
echo "Then do it and launch this script again..."
echo ""
;;
esac
