#!/bin/sh

# In FFmpeg the CRF settings vary from 0-51 with 0 being lossless and 51 being shockingly poor quality. The default is 23 and you need to find the 'sweet spot' for your particular video of file size and video quality with some experimentatio

# Note that in this command-line the video is re-encoded and the audio is simply copied across. Things to consider:

# If the size is still too big and the video quality is still acceptable you would try -crf 24 and so on (incrementally increasing the crf integer) until you find an acceptable compromise between video quality and file size.

# If the video quality is too poor you would try crf 20 and so on (incrementally decreasing the crf integer) until you find an acceptable compromise between video quality and file size.

ffmpeg -i $1 \
       -c:v libx264 -preset slow -crf 22 \
       -c:a copy \
       output.mp4
