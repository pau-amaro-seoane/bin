#!/bin/sh

# Remove files that are useless and empty cache directories, which
# can grow a lot to free space.

# print info about memory before cleaning
echo""
echo "This is your current amount of free memory in home:"
df -h | grep home
echo ""

sleep 2

# tex residual files
find $HOME \( -name \*.log -o -name \*.dvi -o -name \*.aux -o -name \*.out -o \
              -name \*.blg -o -name \*.tns -o -name \*.toc -o -name \*.nav -o \
              -name \*.snm -o -name \*.tmp -o -name \*.tui -o -name \*.tuo -o \
              -name \*.mpo -o -name \*.bbl -o -name \*.pyg -o -name \*.vrb -o \
              -name \*.llt \) -delete

# core files
find $HOME -name "*.core" -delete

# libreoffice lock files
find $HOME -name "*.\~lock.*" -delete

# different caches
\rm -rf $HOME/.cache/thumbnails
\rm -rf $HOME/.cache/iridium
\rm -rf $HOME/.cache/go-build
\rm -rf $HOME/.cache/pip
\rm -rf $HOME/.cache/mozilla/firefox/*.default/cache*
\rm -rf $HOME/.cache/mozilla/firefox/*.default/OfflineCache
\rm -rf $HOME/.cache/mozilla/firefox/*.default/thumbnails
\rm -rf $HOME/.cache/mozilla/firefox/*.default/startupCache

echo ""
echo "This is how much you have won after cleaning: "
df -h | grep home
echo ""
