#!/bin/bash
# Mainline-native Power-Loss-Recovery resume builder for SV08 (user: biqu)
set -u
HOME_DIR=/home/biqu
VARS="$HOME_DIR/printer_data/config/saved_variables.cfg"
PLR_PATH="$HOME_DIR/printer_data/gcodes/plr"
mkdir -p "$PLR_PATH"
getvar() { sed -n "s/^$1 *= *//p" "$VARS" | tr -d "'\"" | head -1; }
filepath=$(getvar filepath)
last_file=$(getvar last_file)
z=$(getvar power_resume_z)
pos=$(getvar power_resume_pos)
bed=$(getvar power_resume_bed)
ext=$(getvar power_resume_ext)
eabs=$(getvar power_resume_eabs)
elast=$(getvar power_resume_e)
echo "PLR: file=$filepath z=$z pos=$pos bed=$bed ext=$ext eabs=$eabs"
if [ -z "$filepath" ] || [ "$filepath" = "default" ] || [ ! -f "$filepath" ]; then
    echo "PLR ERROR: source gcode not found: '$filepath'" >&2; exit 1; fi
if [ -z "$pos" ] || [ "$pos" -le 0 ] 2>/dev/null; then
    echo "PLR ERROR: no valid resume offset (pos='$pos')" >&2; exit 1; fi
out="$PLR_PATH/$last_file"
{
    echo "; ==== PLR resume generated $(date) ===="
    echo "; source=$filepath  offset=$pos  z=$z"
    echo "M140 S$bed"
    echo "M104 S$ext"
    echo "M190 S$bed"
    echo "M109 S$ext"
    echo "SET_KINEMATIC_POSITION Z=$z"
    echo "G90"
    if [ "$eabs" = "True" ]; then
        echo "M82"; echo "G92 E${elast:-0}"
    else
        echo "M83"; echo "G92 E0"
    fi
    echo "G91"
    echo "G1 Z5 F600"
    echo "G90"
    echo "G28 X Y"
    echo "; ==== original gcode resumes from byte $pos ===="
} > "$out"
tail -c +$((pos + 1)) "$filepath" >> "$out"
echo "PLR: wrote $out"
