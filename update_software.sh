#!/bin/sh

# Check we're root
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

# Update
if dmesg | grep  -q "current"; then
    echo "This is current, updating software now with 'pkg_add -Iuv'"
    pkg_add -Iuv
else
    echo "You have updated during a release cycle, updating software now with 'pkg_add -D snap -Iuv'"
    pkg_add -D snap -Iuv
fi

# Remove old files
\rm -f /var/db/colord/mapping.db
\rm -f /var/db/colord/storage.db
\rm -rf /etc/cups/*.conf.O /var/log/cups
\rm -rf /var/cache/cups
\rm -rf /var/spool/cups
\rm -rf /etc/dconf/db/*
\rm -rf /etc/dconf/profile/*
\rm -f /var/db/upower/history-*

# Remove dependencies of programmes you initially installed
# but later deleted

pkg_delete -ac

# Goodbye message
echo ""
echo "  Your software has been updated and old files have been removed."
echo ""
