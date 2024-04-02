#!/bin/sh

wireless=`ifconfig | grep iw | awk '{print $1}' | sed 's/\://'`

ifconfig $wireless -inet down
ifconfig em0 -inet down
route -n flush
ifconfig $wireless up
