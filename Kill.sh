#!/bin/sh
kill  -9 `ps aux | grep -i $1 | awk '{print $2}' | tr '\n' " "` &> /dev/null
pkill -9 $1 &> /dev/null
