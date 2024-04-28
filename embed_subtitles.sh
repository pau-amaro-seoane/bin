#!/bin/sh

# https://stackoverflow.com/questions/57869367/ffmpeg-subtitles-alignment-and-position
ffmpeg -i $1 -vf "subtitles=$2:force_style='Alignment=2,Fontname=Ubuntu'" output.mp4

#ffmpeg -i sample_video_ffmpeg.mp4 -vf subtitles=sample_video_subtitle_ffmpeg.srt output_srt.mp4
