#!/bin/sh
ffmpeg -i $1 -codec:v libtheora -qscale:v 3 \
	     -codec:a libvorbis -qscale:a 3 \
	     -f ogv \
	  "${1%.*}.ogv"
