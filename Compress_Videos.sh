#!/bin/bash
# ==============================================================================
# Script Name: Compress_Video.sh
# Description: This script reduces the file size of video files while maintaining
#              near-original visual quality using the H.265 (HEVC) codec. It 
#              supports on-the-fly rotation by multiples of 90 degrees, custom
#              retention policies for source files, wildcard inputs, and allows 
#              trimming the video from a specific start to end timestamp.
#              It automatically sanitizes filenames, replacing spaces and 
#              non-UNIX-safe characters with underscores before processing.
#              NEW: Introduces five dynamic compression levels (-c 1-5).
#              NEW: Swapped legacy mathematical denoising for 'arnndn' (AI 
#              Recurrent Neural Network) to drastically improve white noise removal.
#              Redesigned summary table tracks original vs final filenames.
#              Includes heavy-duty timeline repair flags to prevent freezing
#              on files with corrupted metadata or broken timestamps.
#              Prints a formatted list of output filenames at completion.
#
# Usage:       ./Compress_Video.sh [options] <file1> [file2] [file3] ...
#              Example: ./Compress_Video.sh -c 4 -k n -r 90 *.mp4
#              Example: ./Compress_Video.sh -c 2 -t 01:32 03:34 -wnr y video.avi
#              Example: ./Compress_Video.sh --help
#
# Options:     -h, --help
#                  Displays this help documentation and exits.
#              -c, --compression <1-5>
#                  Choose the level of file size reduction:
#                  1: Mild   (CRF 22, Preset: fast)
#                  2: Normal (CRF 26, Preset: fast) - Default
#                  3: Strong (CRF 28, Preset: medium)
#                  4: High   (CRF 30, Preset: slow)
#                  5: Max    (CRF 32, Preset: slower)
#              -k, --keep <yes|y|no|n>
#                  Specifies whether to preserve or delete the original file
#                  upon successful compression. (Default: yes)
#              -r, --rotate <90|180|270|-90>
#                  Rotates the video stream by the specified degree. 
#                  90 or 270 rotates Clockwise; -90 rotates Counter-Clockwise.
#              -t, --trim <start> <end>
#                  Cuts the video, keeping only the footage between the <start> 
#                  and <end> timestamps (formatted as MM:SS or HH:MM:SS).
#                  Anything before the start and after the end is deleted.
#              -wnr, --white-noise-rm <yes|y|no|n>
#                  Applies the AI-driven 'arnndn' audio filter to isolate voices 
#                  and eliminate heavy background static and camera hum.
#
# Limitations: - Requires 'ffmpeg', 'awk', and 'curl' or 'wget' on your system.
#              - Re-encoding with H.265 is highly CPU intensive.
#              - Deleting originals (-k no/n) is irreversible; use with caution.
#
# Author:      Pau Amaro Seoane
#
# License:
# Copyright Beijing 2026 Pau Amaro Seoane
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
# ==============================================================================

# Capture the script's actual filename immediately to avoid Zsh function-scope overwrites
SCRIPT_NAME=$(basename -- "$0")

# Initialize a default configuration variable for the new compression level framework
COMPRESSION_LEVEL="2"
# Initialize a default configuration variable determining if source files are kept
KEEP_ORIGINAL="yes"
# Initialize a default configuration variable determining if the AI white noise filter is applied
WHITE_NOISE_RM="no"
# Initialize an empty configuration variable to hold the user's rotation angle
ROTATION_ANGLE=""
# Initialize an empty variable to hold the trim start timestamp
TRIM_START=""
# Initialize an empty variable to hold the trim end timestamp
TRIM_END=""
# Initialize an empty array variable that will collect clean input file paths
INPUT_FILES=()
# Initialize an empty array to track the final names of all successfully processed outputs
SUCCESSFUL_OUTPUTS=()
# Initialize a multiline text variable to accumulate the rows of the final summary report
SUMMARY_ROWS=""
# Initialize a global counter to track how many files fail during the batch run
FAIL_COUNT=0

# Define a function to display a comprehensive help manual to the standard output
show_help() {
    # Print the program header borders for clean terminal styling
    echo "=============================================================================="
    # Print the primary title of the helper wizard
    echo "Advanced Video Compression, Trimming & Layout Transformation Engine"
    # Print the program header borders for clean terminal styling
    echo "=============================================================================="
    # Print basic usage instruction formatting syntax utilizing the isolated script name
    echo "Usage: ${SCRIPT_NAME} [options] <file1> [file2] ..."
    # Print an empty line to provide spatial breathing room in the terminal interface
    echo ""
    # Print the header label for the arguments group
    echo "Options:"
    # Explain the purpose and usage mechanics of the help flags
    echo "  -h, --help              Display this detailed instructional help system."
    # Explain the compression levels targeting varying CRF and preset mathematically mapped options
    echo "  -c, --compression <1-5> Choose the level of file size reduction:"
    echo "                          1: Mild   (CRF 22, Preset: fast)"
    echo "                          2: Normal (CRF 26, Preset: fast) - Default"
    echo "                          3: Strong (CRF 28, Preset: medium)"
    echo "                          4: High   (CRF 30, Preset: slow)"
    echo "                          5: Max    (CRF 32, Preset: slower)"
    # Explain the purpose and usage mechanics of the source retention control flags, including shorthand
    echo "  -k, --keep <yes|y|no|n> Choose whether to keep or erase the original video."
    # State the default behavior explicitly so the user knows what happens without flags
    echo "                          (Default policy is set to 'yes')"
    # Explain the purpose, limitations, and options for the rotation configuration flags
    echo "  -r, --rotate <angle>    Rotate video: 90 (CW), 180, 270 (CW), or -90 (CCW)."
    # Explain the purpose and parameters for the timeline trim flags
    echo "  -t, --trim <mm:ss> <mm:ss> Cut the video from a start time to an end time."
    # Further clarify the behavior of the trim parameters regarding excluded footage
    echo "                          Footage outside this timeframe will be discarded."
    # Explain the purpose and parameters for the AI white noise reduction audio flags
    echo "  -wnr, --white-noise-rm <yes|y|no|n> Strip heavy camera hiss using an AI neural network."
    # Note the automatic filename sanitization behavior so the user is aware of renames
    echo ""
    echo "Note: This script will automatically rename files to replace spaces and"
    echo "      non-UNIX-safe characters with underscores before processing."
    # Print the program header borders for clean terminal styling
    echo "=============================================================================="
}

# Define a portable UNIX utility function to transform raw bytes into human-readable text
format_size() {
    # Assign the first argument passed to this function to a descriptive local variable
    local raw_bytes=$1
    # Use awk to perform floating point division reliably across diverse UNIX flavors
    awk -v b="$raw_bytes" 'BEGIN {
        # Check if the file size is strictly less than 1 Kilobyte (1024 bytes)
        if (b < 1024) printf "%.2f B", b
        # Check if the file size falls between 1 Kilobyte and 1 Megabyte
        else if (b < 1048576) printf "%.2f KB", b/1024
        # Check if the file size falls between 1 Megabyte and 1 Gigabyte
        else if (b < 1073741824) printf "%.2f MB", b/1048576
        # If the file size is 1 Gigabyte or larger, format the output in Gigabytes
        else printf "%.2f GB", b/1073741824
    }'
}

# Initiate a manual argument evaluation loop checking all inputs passed down via $@
while [ "$#" -gt 0 ]; do
    # Evaluate the active value stored inside the first positional argument parameter ($1)
    case "$1" in
        # Intercept matching occurrences of the short or long configuration help flags
        -h|--help)
            # Invoke our previously defined help visualization helper function
            show_help
            # Terminate the script gracefully with a success code since help was fulfilled
            exit 0
            ;;
        # Intercept matching occurrences of the newly added compression scaling flags
        -c|--compression)
            # Verify if the subsequent argument exists and is an integer bounded strictly between 1 and 5
            if [[ "$2" =~ ^[1-5]$ ]]; then
                # Assign the validated numerical scale level directly to our target variable configuration
                COMPRESSION_LEVEL="$2"
                # Advance the argument counter forward by two slots to clear the flag and integer value
                shift 2
            # Handle instances where a non-number or out-of-bounds integer was supplied
            else
                # Pipe an explicit argument evaluation error message out to standard error
                echo "Error: The --compression option requires a number between 1 and 5." >&2
                # Exit the runtime environment signaling a configuration structure failure
                exit 1
            # Conclude the nested compression argument confirmation statement
            fi
            ;;
        # Intercept matching occurrences of the short or long original video retention flags
        -k|--keep)
            # Verify if the subsequent argument parameter exists and matches 'yes' or 'y'
            if [ "$2" = "yes" ] || [ "$2" = "y" ]; then
                # Assign the normalized 'yes' string directly to our target variable configuration
                KEEP_ORIGINAL="yes"
                # Advance the argument counter forward by two slots to clear the flag and value
                shift 2
            # Verify if the subsequent argument parameter exists and matches 'no' or 'n'
            elif [ "$2" = "no" ] || [ "$2" = "n" ]; then
                # Assign the normalized 'no' string directly to our target variable configuration
                KEEP_ORIGINAL="no"
                # Advance the argument counter forward by two slots to clear the flag and value
                shift 2
            # Handle instances where an invalid configuration argument value was supplied
            else
                # Pipe an explicit argument evaluation error message out to standard error
                echo "Error: The --keep option requires an argument value of 'yes', 'y', 'no', or 'n'." >&2
                # Exit the runtime environment signaling a configuration structure failure
                exit 1
            # Conclude the nested file retention argument confirmation statement
            fi
            ;;
        # Intercept matching occurrences of the short or long video stream rotation flags
        -r|--rotate)
            # Verify if the subsequent value is a valid multiple of 90 degrees
            if [ "$2" = "90" ] || [ "$2" = "180" ] || [ "$2" = "270" ] || [ "$2" = "-90" ]; then
                # Assign the validated numerical rotation parameter to our configurations
                ROTATION_ANGLE="$2"
                # Advance the argument counter forward by two slots to clear the flag and value
                shift 2
            # Handle formatting exceptions where unsupported rotation degrees were declared
            else
                # Print a descriptive input error framework out to the standard error pool
                echo "Error: --rotate requires a valid option entry: 90, 180, 270, or -90." >&2
                # Terminate execution pointing to a runtime flag setup breakdown
                exit 1
            # Conclude the nested rotation property validation conditional statement
            fi
            ;;
        # Intercept matching occurrences of the short or long video timeline trim flags
        -t|--trim)
            # Ensure two subsequent arguments are actually provided and neither is another flag (starting with '-')
            if [ -n "$2" ] && [ -n "$3" ] && [[ "$2" != -* ]] && [[ "$3" != -* ]]; then
                # Assign the first captured parameter to the trim start configuration variable
                TRIM_START="$2"
                # Assign the second captured parameter to the trim end configuration variable
                TRIM_END="$3"
                # Advance the argument counter forward by three slots to clear the flag and both times
                shift 3
            # Handle instances where the user failed to provide two valid timestamp boundaries
            else
                # Output a detailed error mapping the exact parameters missing from the user's call
                echo "Error: --trim requires exactly two timestamp arguments (start and end, e.g. 01:32 03:34)." >&2
                # Exit the script indicating a failure to parse the necessary timeline constraints
                exit 1
            # Conclude the nested timeline trim argument confirmation framework
            fi
            ;;
        # Intercept matching occurrences of the short or long audio noise reduction flags
        -wnr|--white-noise-rm)
            # Verify if the subsequent argument parameter exists and matches 'yes' or 'y'
            if [ "$2" = "yes" ] || [ "$2" = "y" ]; then
                # Assign the normalized 'yes' string directly to our target variable configuration
                WHITE_NOISE_RM="yes"
                # Advance the argument counter forward by two slots to clear the flag and value
                shift 2
            # Verify if the subsequent argument parameter exists and matches 'no' or 'n'
            elif [ "$2" = "no" ] || [ "$2" = "n" ]; then
                # Assign the normalized 'no' string directly to our target variable configuration
                WHITE_NOISE_RM="no"
                # Advance the argument counter forward by two slots to clear the flag and value
                shift 2
            # Handle instances where an invalid configuration argument value was supplied
            else
                # Pipe an explicit argument evaluation error message out to standard error
                echo "Error: The --white-noise-rm option requires an argument value of 'yes', 'y', 'no', or 'n'." >&2
                # Exit the runtime environment signaling a configuration structure failure
                exit 1
            # Conclude the nested white noise reduction argument confirmation statement
            fi
            ;;
        # Intercept all items that do not match recognized operational parameter flags
        *)
            # Append the current loop item directly into our clean video processing array
            INPUT_FILES+=("$1")
            # Shift the arguments stream index leftward by one block to progress the loop
            shift
            ;;
    # Finalize the multi-branch case matching layout framework
    esac
# Conclude the command line parameters evaluation loop
done

# Check if the total length of collected positional target files inside our array equals zero
if [ "${#INPUT_FILES[@]}" -eq 0 ]; then
    # Direct an explicit, visible missing argument error out to standard error tracking
    echo "Error: No target video inputs or wildcard mappings were detected." >&2
    # Output quick documentation reminders outlining acceptable call logic structures
    echo "Usage: ${SCRIPT_NAME} [options] <video_file1> [video_file2] ..." >&2
    # Halt runtime frameworks immediately returning an operational empty argument code
    exit 1
# End the verification block checking for missing path parameters
fi

# Define a variable holding the path destination where modified videos are constructed
output_directory="compressed_videos"

# Execute a safe directory construction pass ensuring path creations skip existing folders
mkdir -p "${output_directory}"

# Evaluate the user's chosen compression level and assign mathematical targets
case "${COMPRESSION_LEVEL}" in
    1)
        # Level 1: Mild file size reduction targeting the highest possible visual fidelity
        CRF_VAL="22"
        PRESET_VAL="fast"
        ;;
    2)
        # Level 2: The standard default targeting a balanced visual quality and size ratio
        CRF_VAL="26"
        PRESET_VAL="fast"
        ;;
    3)
        # Level 3: Strong compression targeting a notably smaller file footprint
        CRF_VAL="28"
        PRESET_VAL="medium"
        ;;
    4)
        # Level 4: High compression for tight storage spaces requiring slower CPU rendering
        CRF_VAL="30"
        PRESET_VAL="slow"
        ;;
    5)
        # Level 5: Maximum mathematical compression targeting the absolute smallest output size
        CRF_VAL="32"
        PRESET_VAL="slower"
        ;;
esac

# Initialize an empty Bash array to safely hold structural rotation filter arguments
FFMPEG_FILTER=()
# Evaluate if the user selected a 90-degree clockwise structural transformation
if [ "${ROTATION_ANGLE}" = "90" ]; then
    # Push the required transposition flags as distinct isolated elements into the array
    FFMPEG_FILTER=("-vf" "transpose=1")
# Evaluate if the user selected a 180-degree absolute flip transformation
elif [ "${ROTATION_ANGLE}" = "180" ]; then
    # Push two stacked 90-degree transposition commands as isolated elements into the array
    FFMPEG_FILTER=("-vf" "transpose=1,transpose=1")
# Evaluate if the user chose a 270-degree clockwise or 90-degree counter-clockwise flip
elif [ "${ROTATION_ANGLE}" = "270" ] || [ "${ROTATION_ANGLE}" = "-90" ]; then
    # Push the counter-clockwise transposition flags safely into the array
    FFMPEG_FILTER=("-vf" "transpose=2")
# Close the rotation conversion evaluation matrix
fi

# Initialize an empty Bash array to safely hold structural timeline cutting arguments
FFMPEG_TRIM=()
# Evaluate if the user provided valid start and end timestamps to initiate a sequence cut
if [ -n "${TRIM_START}" ] && [ -n "${TRIM_END}" ]; then
    # Push the precise seeking flags and timestamps as four distinct items into the array
    FFMPEG_TRIM=("-ss" "${TRIM_START}" "-to" "${TRIM_END}")
# Close the timeline cutting evaluation matrix
fi

# Initialize an empty Bash array to safely hold acoustic denoising filter arguments
FFMPEG_AUDIO_FILTER=()
# Evaluate if the user requested the removal of background static and white noise
if [ "${WHITE_NOISE_RM}" = "yes" ]; then
    # Define a temporary system path for the recurrent neural network machine learning model
    MODEL_FILE="/tmp/ffmpeg_rnnoise_cb.rnnn"
    
    # Check if the model file is missing from the temporary directory to avoid re-downloading
    if [ ! -f "${MODEL_FILE}" ]; then
        # Print a verbose message indicating the AI model is being fetched from the internet
        echo "AI White noise reduction requested. Fetching the 'cb.rnnn' acoustic model..."
        # Safely attempt to download the RNNoise model from RichardPL's official GitHub repository
        if command -v curl >/dev/null 2>&1; then
            # Execute a silent curl request to pull the raw model file onto the local disk
            curl -sSL "https://raw.githubusercontent.com/richardpl/arnndn-models/master/cb.rnnn" -o "${MODEL_FILE}"
        # Fall back to wget if curl is not installed on the user's UNIX system
        elif command -v wget >/dev/null 2>&1; then
            # Execute a quiet wget request to pull the raw model file onto the local disk
            wget -qO "${MODEL_FILE}" "https://raw.githubusercontent.com/richardpl/arnndn-models/master/cb.rnnn"
        # Handle environments where neither standard web fetching tool is available
        else
            # Send a critical error to standard error regarding missing download utilities
            echo "Error: 'curl' or 'wget' is required to download the AI audio model." >&2
            # Halt runtime execution to prevent a broken FFmpeg audio pipeline
            exit 1
        # Close the download tool availability check
        fi
        
        # Guard clause to ensure the download actually completed and the file exists
        if [ ! -f "${MODEL_FILE}" ]; then
            # Throw an error if network policies blocked the retrieval of the file
            echo "Error: Failed to fetch the AI model from GitHub. Please check your connection." >&2
            # Abort execution to prevent FFmpeg from crashing looking for a ghost file
            exit 1
        # Close the post-download existence check
        fi
    # Close the missing AI model file check
    fi
    # Push the Recurrent Neural Network DeNoise (arnndn) filter linking to the downloaded machine learning model
    FFMPEG_AUDIO_FILTER=("-af" "arnndn=m=${MODEL_FILE}")
# Close the audio evaluation matrix
fi

# Print a highly visible initial processing start notification to the active terminal shell
echo "Starting batch compression process under Pau Amaro Seoane's optimization core..."
echo "Using Compression Level: ${COMPRESSION_LEVEL} (CRF ${CRF_VAL}, Preset ${PRESET_VAL})"

# Launch a loop targeting every item inside the extracted array mapping ($@ wildcards)
for input_file in "${INPUT_FILES[@]}"; do
    # Draw a clean separation interface layout to organize text readouts systematically
    echo "--------------------------------------------------------------------------------"
    # Announce the filename item currently pulled into the working context pipeline
    echo "Evaluating input candidate: '${input_file}'"
    
    # Confirm that the current target is an existing standard data file and not a folder
    if [ ! -f "${input_file}" ]; then
        # Skip directories (like the script's output folder matching wildcards) with a notice
        echo "Skipping '${input_file}': Not a regular file or standard media path entry."
        # Jump instantly back to the top loop evaluation phase clearing the non-file item
        continue
    # End the regular file classification guard checking framework
    fi

    # Extract the directory path of the current file to ensure renames happen in the correct location
    dir_name=$(dirname -- "${input_file}")
    # Extract the isolated trailing file name from the relative or absolute system path string
    base_name=$(basename -- "${input_file}")
    # Store the exact original filename untouched before sanitization for the final report
    original_base_name="${base_name}"
    
    # Sanitize the filename: use sed to replace anything that IS NOT a letter, number, dot, or dash with an underscore
    sanitized_base_name=$(echo "${base_name}" | sed 's/[^a-zA-Z0-9._-]/_/g')
    # Chain a second sed command to squeeze multiple consecutive underscores into a single underscore for clean visuals
    sanitized_base_name=$(echo "${sanitized_base_name}" | sed 's/__*/_/g')
    
    # Evaluate if the original filename differs from the sanitized filename (meaning it contained bad characters)
    if [ "${base_name}" != "${sanitized_base_name}" ]; then
        # Construct the new, fully sanitized file path string
        safe_input_file="${dir_name}/${sanitized_base_name}"
        
        # Check to ensure we don't accidentally overwrite an existing file that already has the clean name
        if [ -e "${safe_input_file}" ]; then
            # Issue a stark warning to the terminal if the sanitized destination is already occupied by another file
            echo "Warning: Cannot sanitize '${base_name}' because '${sanitized_base_name}' already exists. Skipping." >&2
            # Continue to the next item in the loop to prevent destructive data loss
            continue
        # Close the conflict prevention guard check
        fi
        
        # Verbose terminal output informing the user that their file is being renamed on disk
        echo "Sanitizing filename: Renaming to '${sanitized_base_name}' to remove unsafe characters..."
        # Safely execute the system move command (-- ensures filenames starting with hyphens don't break mv flags)
        mv -- "${input_file}" "${safe_input_file}"
        
        # Update our internal loop variables to seamlessly point to the newly renamed file
        input_file="${safe_input_file}"
        base_name="${sanitized_base_name}"
    # Close the filename sanitization sequence block
    fi
    
    # Strip away the existing file extension layout by dropping the final dot string onward
    name_without_ext="${base_name%.*}"
    
    # Define a clean output absolute string targeting our dedicated repository directory
    output_file="${output_directory}/${name_without_ext}_compressed.mkv"
    # Capture only the basename of the final destination file for the summary table and completion list
    final_table_name=$(basename -- "${output_file}")
    
    # Check if a naming conflict occurs where the input file matches the new target file destination
    if [ "${input_file}" = "${output_file}" ]; then
        # Output an explicit self-overwrite warn banner to standard error blocks
        echo "Error: Input file path matches output destination. Skipping to protect sources." >&2
        # Exit the local loop pass to protect underlying user media records from truncation
        continue
    # Conclude the target destination intersection testing block
    fi

    # Print a verbose log identifying the destination directory path for the new file
    echo "Target output file designated as: '${output_file}'"
    # Capture the original raw storage footprint size in bytes using completely portable methods
    size_before=$(wc -c < "${input_file}")
    # Run the raw size byte metrics directly through our human conversion calculation utility
    readable_before=$(format_size "$size_before")
    # Output the initial spatial measurements aloud via clear verbose terminal announcements
    echo "Original file size measured at: ${readable_before}"
    
    # Output a final verbose operational notice indicating FFmpeg initialization points
    echo "Invoking processing threads..."
    
    # Run the full FFmpeg command suite with dynamically injected compression scaling algorithms
    ffmpeg -v verbose -fflags +genpts "${FFMPEG_TRIM[@]}" -i "${input_file}" "${FFMPEG_FILTER[@]}" "${FFMPEG_AUDIO_FILTER[@]}" -max_muxing_queue_size 9999 -vcodec libx265 -crf "${CRF_VAL}" -preset "${PRESET_VAL}" -c:a aac -b:a 128k -async 1 -y "${output_file}"
    
    # Monitor the numerical output exit state of the immediately preceding transcoder call
    if [ $? -eq 0 ]; then
        # Capture the newly minted file footprint in raw bytes using standard input streams
        size_after=$(wc -c < "${output_file}")
        # Translate the compressed byte payload footprint out into friendly spatial units
        readable_after=$(format_size "$size_after")
        
        # Calculate space savings ratio using awk arithmetic to avoid bash math limitations
        saved_pct=$(awk -v b="$size_before" -v a="$size_after" 'BEGIN {
            if (b > 0) printf "%.1f%%", ((b - a) / b) * 100
            else printf "0.0%"
        }')
        
        # Output successful processing milestones highlighting localized execution metrics
        echo "Success: Compression sequence finished for '${input_file}'."
        # Confirm space reductions to the active standard output monitoring screen
        echo "Compressed size achieved: ${readable_after} (Saved: ${saved_pct})"
        
        # Append the successfully created output filename to our global success tracking array
        SUCCESSFUL_OUTPUTS+=("${final_table_name}")
        
        # Format a beautifully aligned row tracking the original pre-sanitized name mapping to the final name.
        # String formatting caps variables at 30 characters maximum (.30s) so the terminal grid never breaks.
        row=$(printf "\n%-30.30s | %-30.30s | %-10s | %-10s | %-8s" "$original_base_name" "$final_table_name" "$readable_before" "$readable_after" "$saved_pct")
        # Append the constructed information column directly into our master global summary accumulator
        SUMMARY_ROWS="${SUMMARY_ROWS}${row}"
        
        # Evaluate if the configuration runtime rules demand the destruction of source media files
        if [ "${KEEP_ORIGINAL}" = "no" ]; then
            # Announce the permanent purge of the current working copy via verbose declarations
            echo "Retention flag set to 'no'. Purging original source file: '${input_file}'"
            # Execute a clean system deletion call dropping the processed original file object
            rm -f "${input_file}"
        # Conclude the optional original file destruction routine
        fi
    # Route execution behaviors for failure scenarios where transcoding engines broke down
    else
        # Print a prominent, high-visibility operational error block tracking execution failures
        echo -e "\n\033[1;31m!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\033[0m" >&2
        echo -e "\033[1;31m!! CRITICAL WARNING: Compression FAILED for '${input_file}'\033[0m" >&2
        echo -e "\033[1;31m!! The original file remains untouched. Please check the FFmpeg logs above.\033[0m" >&2
        echo -e "\033[1;31m!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\033[0m\n" >&2
        
        # Format a stylized problem indicator row to alert the user inside the final report summary
        row=$(printf "\n%-30.30s | %-30.30s | %-10s | %-10s | %-8s" "$original_base_name" "FAILED" "$readable_before" "FAILED" "0.0%")
        # Append the explicit failure log layout tracking indicators directly into the report rows
        SUMMARY_ROWS="${SUMMARY_ROWS}${row}"
        
        # Clean up the potentially broken/half-finished output file left by the failed FFmpeg process
        [ -f "${output_file}" ] && rm -f "${output_file}"
        
        # Increment the global failure tracking counter by one to alter the final exit message
        FAIL_COUNT=$((FAIL_COUNT + 1))
    # Finalize the engine execution status validation paths
    fi
    
# Conclude the structural loop, pointing tracking engines back upwards to handle next items
done

# Draw a distinct visual break line splitting up processing details from the report segment
echo "--------------------------------------------------------------------------------"
# Output the overarching table title card block identifying final data transformations
echo "================================= BATCH COMPRESSION SUMMARY =================================="
# Print standardized structural headers to neatly align downstream measurement values
printf "%-30s | %-30s | %-10s | %-10s | %-8s" "ORIGINAL NAME" "FINAL NAME" "BEFORE" "AFTER" "SAVED %"
# Draw a structural grid boundary underscore separator across the column interfaces
echo -e "\n-------------------------------|--------------------------------|------------|------------|--------"

# Inspect if our report container rows have gathered rows or remained totally empty
if [ -z "${SUMMARY_ROWS}" ]; then
    # Output an explicit fallback message indicating zero successful file evaluations took place
    echo " [No files were successfully processed during this execution pass]"
# Handle normal operation loops where statistical columns exist
else
    # Output the cumulative rows variable directly utilizing the formatting engine specifications
    echo -e "${SUMMARY_ROWS}"
# Conclude the final reporting presence confirmation checks
fi

# Print structural base grid borders framing the completed statistical visualization dashboard
echo "=============================================================================================="

# Evaluate if the failure counter remained at zero indicating a perfect execution run
if [ "${FAIL_COUNT}" -eq 0 ]; then
    # Output the standard final system completion message noting where the files live
    echo "Process fully complete. The outputs are available in: ./${output_directory}/"
    # Initiate a loop to cleanly print out the filenames of all successfully generated output files
    for output_name in "${SUCCESSFUL_OUTPUTS[@]}"; do
        # Print each filename clearly indented with a visual arrow pointer for easy reading
        echo "    -> ${output_name}"
    # Conclude the output filename formatting loop
    done
# Route execution behavior if one or more files failed during the loop phase
else
    # Replace the success banner with a highly visible terminal error message
    echo -e "\033[1;31mError: Batch process concluded, but ${FAIL_COUNT} file(s) failed. Please review the summary above.\033[0m" >&2
# Finalize the closing message conditional block
fi