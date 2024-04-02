#!/bin/sh

# Free space, first of all
sudo journalctl --vacuum-time=3d
rm -rf ~/.cache/thumbnails/*

# Remove old revisions of snaps
# Close all snaps before running this
#set -eu
#sudo snap list --all | awk '/disabled/{print $1, $3}' |
#    while read snapname revision; do
#        sudo snap remove "$snapname" --revision="$revision"
#    done

# Update et al
sudo apt update
sudo apt -y upgrade
sudo apt autoclean
sudo apt clean
sudo apt -y autoremove

# old kernels
# sudo apt install byobu
sudo purge-old-kernels

# snap
sudo snap refresh

# flatpak
flatpak update -y --noninteractive

# zoom
url=https://zoom.us/client/latest/
file=zoom_amd64.deb
cd /home/pau/Downloads

wget -qN $url$file
downloadedVer=`dpkg -f $file version`

dpkgReport=`dpkg -s zoom`
echo "$dpkgReport" | grep '^Status: install ok' > /dev/null && \
  installedVer=`echo "$dpkgReport" | grep ^Version: | sed -e 's/Version: //'`

if [ "$installedVer" != "$downloadedVer" ]; then
  sudo dpkg -i $file
else
  echo "Zoom is already the latest version."
fi

# check for new ubuntu releases
sudo do-release-upgrade --check-dist-upgrade-only
