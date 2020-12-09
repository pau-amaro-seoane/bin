#!/usr/bin/env zsh

# Make sure only root can run our script
if [ "$(id -u)" != "0" ]; then
   echo ""
   echo "       This script must be run as root" 1>&2
   echo ""
   exit 1
fi

# Make sure there is internet connection
wget -q --spider http://google.com

if [ $? -eq 0 ]; then
    echo "You are online."
else
    echo "You are offline. The script will terminate now."
    exit
fi

# Make sure /nou exists
if [ -d "/nou" ]; then
  echo "Folder /nou exists."
else
  echo "Folder /nou does not exist, creating it now."
  mkdir /nou
fi

# Define ftp server for ftp
FTP=ftp://ftp.spline.de/pub/OpenBSD/snapshots/amd64

# Define http server for wget

HTTP=http://fastly.cdn.openbsd.org/pub/OpenBSD/snapshots/amd64
alias WGET='wget -r -l1 -H -t1 -nd -N -np -erobots=off -A'

# Remove previous snapshots

\rm /nou/*

# Fetch snapshots in /mnt/upgrade

cd /nou

# If using http, employ wget to retrieve files

WGET bsd\*     $HTTP
WGET INS\*     $HTTP
WGET index.txt $HTTP
WGET \*tgz     $HTTP
WGET SHA\*     $HTTP

# If using ftp, uncomment this one
#ftp -i $FTP/{INS\*,index.txt,bsd\*,\*tgz,SHA\*}

# Make a backup of previous bsd.rd and move new one
# to / so that we can update

cp /bsd.rd /bsd.rd.old
cp bsd.rd /

# Ask the user whether running bsd should be backup'ed

echo ""
echo "Do you want to backup the current kernel bsd as bsd.old?"
echo ""
read answer
case $answer in
yes|Yes|y|Y|S|s)
cp /bsd /bsd.old && echo "" && echo "Current bsd backup'ed..."
;;
no|n|N)
echo "Current bsd not backup'ed..."
;;
esac

# Final note

echo ""
echo "Reboot, boot bsd.rd and choose for the location of the sets:"
echo ""
echo " [disk] with path /nou"
echo ""

# Want to update software and reboot?

read "CONT?Should I update your software (y/n)? "
if [[ "$CONT" =~ ^[YySs]$ ]]; then

        # pkg_add

        if dmesg | grep  -q "current"; then
            echo "This is current, updating software now with 'pkg_add -Iuv'"
            pkg_add -Iuv
        else
            echo "You have updated during a release cycle, updating software now with 'pkg_add -D snap -Iuv'"
            pkg_add -D snap -Iuv
        fi

        # ask if reboot

        echo ""
        echo "Do you want to reboot?"
        read answer
        case $answer in
        yes|Yes|y|Y|S|s)
        echo ""
        echo "Finished downloading latest snapshot, software updated, rebooting now..." && reboot
        ;;
        no|n|N)
        echo ""
        echo "Finished downloading latest snapshot, software updated, not rebooting, though..."
        ;;
        esac
else
  exit 1
fi
