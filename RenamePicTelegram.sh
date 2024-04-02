#!/usr/bin/env zsh

# Define the help method
if [[ $1 == "-h" || $1 == "--help" ]]; then
  echo ""
  echo "This programme converts file names of Telegram pictures"
  echo "as downloaded with the export chat option. The format is"
  echo "          day_month_year_hour_min_sec.jpg"
  echo "If more than one instance exist, then it appends a counter"
  echo "starting at 0001."
  echo "If you want a dry run, add the flag -n to the main command."
  exit 0
fi


autoload zmv
typeset -A n=()

# Main command, for a dry run, write zmv -n
zmv -n '(**/)photo_<->@((<->)-(<->)-(<->)_(<->)-(<->)-(<->))(.jpg)(#qn.)' \
       '$1${3}_${4}_${5}_${6}h${7}m${8}s_${(l[5][0])$((++n[\$2]))}$9'
