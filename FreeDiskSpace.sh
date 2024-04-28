#!/bin/sh

# journaling

journalctl --disk-usage
sudo journalctl --vacuum-time=3d

# Temporary files and stremio
rm -rf ~/.cache/thumbnails/*
#rm -rf ~/.var/app/com.stremio.Stremio/.stremio-server/stremio-cache/
rm -rf ~/.local/share/Trash/files/

# apt
sudo apt autoclean
sudo apt clean
sudo apt -y autoremove

# old kernels
# sudo apt install byobu
sudo purge-old-kernels

# Removes old revisions of snaps
# CLOSE ALL SNAPS BEFORE RUNNING THIS
killall snap-store
sleep 3
snap list --all | awk '/disabled/{print $1, $3}' |
    while read snapname revision; do
        sudo snap remove "$snapname" --revision="$revision"
    done

# Size of installed packages

dpigs -H
