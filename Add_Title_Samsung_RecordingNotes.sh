#!/bin/sh
ffplay -vf "[in]drawtext=fontfile=Cantarell:text='Integración - Conceptos y regla de sustitución - Pau Amaro Seoane':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=15:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0,13)'"  output.mp4
