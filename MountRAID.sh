#!/bin/sh

# This script mounts an external USB drive which is encrypted as RAID
#
# I am assuming that:
#
#      (1) the drive is mounted in /mnt/USBRaid  
#      (2) dmesg shows a line containing either <WD, My Passport
#          or <Seagate (the two types of drive I have)
#      (3) it contains a single RAID partition, named "a"
#      (4) after decrypt there's a single partition, named "i"   
#      (5) your doas config file contains
#            permit nopass :pau cmd mount
#            permit nopass :pau cmd umount
#            permit nopass :pau cmd fsck
#
# Pau Amaro Seoane, 17 Nov 2019, Rome
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

# (1) Make sure /mnt/USBRaid exists

if [ -d "/mnt/USBRaid" ]; then
  echo "/mnt/USBRaid exists, we are good to go."
else
  echo "Folder /mnt/USBRaid does not exist, creating it now."
  doas mkdir /mnt/USBRaid
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

# (2) Run fsck first

echo ""
echo "Running fsck..."
doas fsck $CRYPTDUID.i

# Mount it

doas mount $CRYPTDUID.i /mnt/USBRaid

echo ""
echo "Drive $NAMEDRIVE (encrypted is $NAMECRYPTDRIVE) mounted on /mnt/USBRaid..."


           # ******************** Wait until user decides to unmount ******************** #

echo ""
echo "If you wish to unmount and bioctl -d the drive, press any key..."
read


           # ******************** Unmount the drive and bioctl -d it ******************** #

echo ""
echo "Unmounting folder..."
doas umount /mnt/USBRaid

echo ""
echo "... unmounted... bioctl'ing -d now..."
doas bioctl -d $CRYPTDUID

# Goodbye
echo ""
echo "Folder unmounted and drive encrypted. Bye."
