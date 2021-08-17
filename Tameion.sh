#!/bin/sh

# Tameion.sh
#
# This script decripts and untars an existing file "tameion.tar.gz.enc",
# which is located in a folder named "Tameion".
#
# The file tameion.tar.gz.enc when decripted and untarred creates a folder,
# which we call tameion. In that folder we have sensitive data: Passwords,
# bank account details as pictures etc: E.g. file1, file2, file3.
#
# The user can access those data, watch the pictures, edit the password file,
# add new passwords to it, remove them etc. 
#
# In my case, I mostly edit or read the password file, so that I ask the script
# to open it with vim. If this is not your case, just comment out the lines of
# the block starting with "Edit the file with passwords with vim".
#
# During that time, the script is on hold, changeloging until the user 
# presses ENTER, which will recreate tameion.tar.gz.enc and after that, 
# obliterate the open directory with its files and the terminal closes.
#
# Structure:
# =========
#
# Before running the script: 
# -------------------------
# Tameion
# `-- tameion.tar.gz.enc
# 
# While running the script:
# ------------------------
# Tameion
# `-- tameion
#     |-- file1
#     |-- file2
#     `-- file3
# 
# After exit:
# ----------
# Tameion
# `-- tameion.tar.gz.enc
# 
# Assumptions:
# ===========
# -The folder named tameion contains the sensitive files
# -This folder is a subfolder of Tameion, the main folder
# -Tameion is located in a given path, defined as TAMEION
# -openssl is installed
#
# Author and license
# ===================
# 
# Pau Amaro Seoane, Berlin, 14 August 2021
# OpenBSD license
# amaro@riseup.net


# Define variables
# ================

# Folder in which the file tameion.tar.gz.enc resides
TAMEION=$HOME/fitx_confg/Tameion

# vim
myvim=`which vim`

# Define your file with passwords (in my case tameion.txt)
passwdfile=$TAMEION/tameion/tameion.txt


# Decrypt
# =======

# Decrypt tameion.tar.gz.enc and unfold it.

# Make sure that if the password is wrong, the script
# terminates, because otherwise that would lead to
# the removal of tameion.tar.gz.enc

echo "Please type in the password..."
echo ""
openssl enc -d -aes-256-cbc -md sha512 -pbkdf2 -iter 100000 -salt \
        -in  $TAMEION/tameion.tar.gz.enc \
        -out $TAMEION/tameion.tar.gz 2>/dev/null ;
ec=$?  # grab the exit code into a variable so that it can
       # be reused later, without the fear of being overwritten
case $ec in
    0) echo "Correct, untarring now..."; sleep 1    ;;
    1) echo "Wrong password... script finishes here";
       /bin/rm $TAMEION/tameion.tar.gz;
       exit 1;;
esac
clear

# Don't trust much the -C option of tar, cd instead
cd      $TAMEION
tar xfz $TAMEION/tameion.tar.gz

# Obliterate tameion.tar.gz.enc, since we might modify it
dd if=/dev/urandom of=$TAMEION/tameion.tar.gz.enc bs=21 count=1024 conv=notrunc
dd if=/dev/urandom of=$TAMEION/tameion.tar.gz     bs=21 count=1024 conv=notrunc

# "remove" the result
/bin/rm $TAMEION/tameion.tar.gz.enc
/bin/rm $TAMEION/tameion.tar.gz

# Echo some instructions
clear
echo "Folder Tameion decrypted." 
echo "I will launch now vim to edit the password files."
echo "Do whatever you have to do and remember to save the changes, if any."

# Edit the file with passwords with vim
# =====================================

# Edit tameion.txt
# you should be careful
xterm -fa "Ubuntu Mono" -fs 14 -rightbar \
      -C -xrm xterm.vt100.pointerColor:blue +mb -pob +vb -bd red \
      -fg red -bg black -title "tameion open"\
      -e "$myvim $passwdfile"

# Clear and log, changelog to wait for the user to press ENTER
clear
echo  "The folder tameion is still open and accessible."
echo  "If you want to close it and encrypt it, press ENTER in this terminal."
read continue

# Encrypt
# =======

# First tar and compress the folder
# Option -C of tar to avoid including parent directory
# seems buggy, so cd into folder instead
cd $TAMEION
tar cfz tameion.tar.gz tameion

# Encrypt it
echo "Ecnrypting tameion, please choose a good password..."
openssl enc -aes-256-cbc -md sha512 -pbkdf2 -iter 100000 -salt \
	-in  $TAMEION/tameion.tar.gz \
	-out $TAMEION/tameion.tar.gz.enc

# Obliterate tameion.tar.gz ensuring the obfuscated bytes are synced to disk
# and delete the file
dd if=/dev/urandom of=$TAMEION/tameion.tar.gz bs=21 count=1024 conv=notrunc
rm $TAMEION/tameion.tar.gz

# Obliterate contents of folder tameion ensuring the obfuscated bytes are synced to disk
# and delete the folder
find $TAMEION/tameion -type f | while read line; do dd if=/dev/urandom of=$line bs=21 count=1024; done
/bin/rm -r $TAMEION/tameion

# Log message
clear
echo "Folder tameion encrypted. You can close this terminal."
