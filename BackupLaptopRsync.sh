#!/bin/sh

# This script mounts an external USB drive which is encrypted as RAID
# and then backs up some folders from the laptop to it using rsync
# excluding "junk" files.
#
# I am assuming that:
#
#      (1) the drive is mounted in /mnt/BackupDrive  
#      (2) dmesg shows a line containing either <WD, My Passport
#          or <Seagate (the two types of drive I have)
#      (3) it contains a single RAID partition, named "a"
#      (4) after decrypt there's a single partition, named "i"   
#      (5) your doas config file contains
#            permit nopass :pau cmd mount
#            permit nopass :pau cmd umount
#            permit nopass :pau cmd fsck
#            permit nopass pau as root cmd bioctl args -c C -l
#            permit nopass pau as root cmd bioctl args -d
#            permit nopass :pau cmd disklabel
#
# Pau Amaro Seoane, 16 Nov 2019, Berlin
#
# Added automatic reading and using of DUID and encrypted DUID
# Zeuthen 30 Sep 2020




            # ******************** Mount the external drive ******************** #


# Get DUID from the plugged drive
# Note:
# We use grep to search for the line containing either "<WD, My Passport"
# or "<Seagate" because I have three MyPassport drives and one Seagate. 
# The relevant line with the information about the device name (sda2, sda3 etc)
# contains one of those two strings, so that grep is looking for either "<WD, My Passport"
# OR "<Seagate". Since we might have used the script several times on the same session,
# tail -1 makes sure we are picking up the latest drive plugged, shown in dmesg as the
# last entry in that either/or.


NAMEDRIVE=`dmesg | grep -E '(<WD, My Passport|<Seagate)' | tail -1 | awk '{print $1}'`
DUID=`doas disklabel $NAMEDRIVE | grep "duid:" | awk '{print $2}'`

# State name and duid of the drive

echo ""
echo "Found drive $NAMEDRIVE with DUID $DUID."
echo ""

# Make sure /mnt/BackupDrive exists

if [ -d "/mnt/BackupDrive" ]; then
  echo "/mnt/BackupDrive exists, we are good to go."
else
  echo "Folder /mnt/BackupDrive does not exist, creating it now."
  doas mkdir /mnt/BackupDrive
fi

# Mount softraid

echo ""
echo "bioctl'ing now... enter the passphrase..."
doas bioctl -c C -l $DUID.a softraid0

if [[ $? -ne 0 ]] ; then
    echo "Wrong password, script terminates now."
    exit 1
fi

# Get encrypted duid from the drive

NAMECRYPTDRIVE=`dmesg | tail -1 | awk '{print $1}' | sed 's/://'`
CRYPTDUID=`doas disklabel $NAMECRYPTDRIVE | grep "duid:" | awk '{print $2}'`

# State the name and CRYPTDUID

echo ""
echo "Encrypted drive is $NAMECRYPTDRIVE with (crypt) DUID $CRYPTDUID."
echo ""

# Run fsck first

echo ""
echo "Running fsck..."
doas fsck $CRYPTDUID.i

# Mount it

doas mount $CRYPTDUID.i /mnt/BackupDrive

echo ""
echo "Drive $NAMEDRIVE (encrypted is $NAMECRYPTDRIVE) mounted on /mnt/BackupDrive, backup'ing now..."
sleep 2

            # ******************** backup folders ******************** #

# First define our rsync
# try first "--dry-run" after you modify this

myrsync="rsync                                                       \
               --delete --archive --verbose --compress               \
               --human-readable   --progress --times                 \
               --perms --executability --log-file=/tmp/$$            \
               --exclude "*.o"   --exclude "*.log" --exclude "*.dvi" \
               --exclude "*.aux" --exclude "*.out" --exclude "*.blg" \
               --exclude "*.tns" --exclude "*.toc" --exclude "*.nav" \
               --exclude "*.tmp" --exclude "*.tui" --exclude "*.tuo" \
               --exclude "*~"    --exclude "*.swo" --exclude "Atlas"  "

# backup all wireless passwords, rc.conf.local and doas.conf

$myrsync /etc/hostname.iwm0 $HOME/fitx_confg/connexions_sense_fil
$myrsync /etc/hostname.if   $HOME/fitx_confg/connexions_sense_fil
$myrsync /etc/rc.conf.local $HOME/fitx_confg/conf_local
$myrsync /etc/doas.conf     $HOME/fitx_confg/doas_conf

# backup all important folders to /mnt/BackupDrive

$myrsync --log-file=/tmp/$$  \
           $HOME/andromina   \
           $HOME/bin         \
           $HOME/smbin       \
           $HOME/escriptori  \
           $HOME/treball     \
           $HOME/correu      \
           $HOME/fitx_confg  \
           $HOME/temporal    \
           $HOME/ejcaip      \
           $HOME/include     \
           $HOME/lib         \
           $HOME/grafia      \
       /mnt/BackupDrive



           # ******************** Unmount the drive and bioctl -d it as root ******************** #

echo ""
echo "rsync finished, log under /tmp/$$, unmounting folder..."
doas umount /mnt/BackupDrive

echo ""
echo "... unmounted... bioctl'ing -d now..."
doas bioctl -d $CRYPTDUID

if [[ $? -ne 0 ]] ; then
    echo "Wrong password, script terminates now."
    exit 1
fi

# Goodbye
echo ""
echo "Laptop backup'ed, folder unmounted, drive encrypted... Aweeeeesome!"
