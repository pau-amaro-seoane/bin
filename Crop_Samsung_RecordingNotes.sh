#!/bin/sh
# https://www.linuxuprising.com/2020/01/ffmpeg-how-to-crop-videos-with-examples.html

# Play with 
# ffplay -vf "crop=680:200:0:150" input.mp4
#
# "crop=W:H:X:Y" means we're using the "crop" video filter, with 4 values:

#    --> w the width of the output video (so the width of the cropped region), 
#    which defaults to the input video width (input video width = iw, which is the same as in_w); 
#    out_w may also be used instead of w
#
#    --> h the height of the output video (the height of the cropped region), 
#    which defaults to the input video height (input video height = ih, with in_h being another 
#    notation for the same thing); out_h may also be used instead of h
#
#    --> x the horizontal position from where to begin cropping, starting from the left (with the absolute left margin being 0)
#    --> y the vertical position from where to begin cropping, starting from the top of the video (the absolute top being 0)

# For a landscape recording:
##ffmpeg -i $1 -filter:v "crop=830:550:200:110" output.mp4
#ffmpeg -i $1 -filter:v "crop=1150:600:20:110" output.mp4

# For zoom recordings on the tablet
ffmpeg -i $1 -filter:v "crop=1390:900:225:220" output.mp4

# For a vertical recording:
#ffmpeg -i $1 -filter:v "crop=680:850:0:150" $$.mp4

/bin/rm /tmp/TITOL.txt

tee /tmp/TITOL.txt <<EOF
A course on Gravitational Waves : Introduction.
Pau Amaro Seoane - Berlin, 18/Aug/2023
EOF

ffmpeg -i output.mp4 -vf "drawtext=fontfile=Cantarell:textfile='/tmp/TITOL.txt':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=15:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0,20)'" -codec:a copy Resultat.mp4

# -ss 28 trims the first 28 seconds of the video, must be used after the input flag, -i
