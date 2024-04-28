#!/bin/sh

# https://stackoverflow.com/questions/57869367/ffmpeg-subtitles-alignment-and-position
ffmpeg -i $1  -vf "subtitles=$2:force_style='Alignment=6,Fontname=Ubuntu'" output.mp4
