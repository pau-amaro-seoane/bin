#!/bin/sh

# Make sure that $HOME/.fem exists

if [ -d "$HOME/.fem" ]; then
  :
else
  mkdir $HOME/.fem
  echo "Created $HOME/.fem directory"  
fi

# Record pwd of the file to be moved, along with the 
# name(s) of the file(s), in case we want to restore 
# them to their original location.

# First check that the pwd log file exists in $HOME/.fem

if [ -f "$HOME/.fem/pwdlog.txt" ]; then
  :
else
  touch $HOME/.fem/pwdlog.txt
  echo "Created pwd log file in $HOME/.fem"  
fi

# Then log it

PWD=`pwd`
APPEND=`echo $PWD`"/"$@
echo $APPEND >> $HOME/.fem/pwdlog.txt

# Since we are aliasing rm with mv, make sure that the
# rm flags do not pose a problem:

while [[ $1 = -* ]]; do
        case $1 in
                -r ) shift 1 ;;
                -f ) shift 1 ;;
                -d ) shift 1 ;;
                -i ) shift 1 ;;
                -P ) shift 1 ;;
                -R ) shift 1 ;;
                -v ) shift 1 ;;
        esac
done

# Move the file(s) and display information

mv -iv "$@" $HOME/.fem
