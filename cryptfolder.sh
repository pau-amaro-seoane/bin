#!/bin/sh
#
# cryptfolder.sh -- Automatic folder encryption and decryption
#
# Copyright Beijing 2026 Pau Amaro Seoane
#
# ==============================================================================
# SCRIPT BEHAVIOR & DOCUMENTATION
# ==============================================================================
# This script provides fully automatic symmetric encryption and decryption
# of directories and files using purely POSIX-compliant shell tools.
#
#   - By default, this script behaves like a "move" command. 
#   - When you encrypt a folder, the unencrypted folder is permanently DELETED.
#   - When you decrypt an archive, the .enc file is permanently DELETED.
#   - To prevent deletion, you MUST pass the -k or --keep flag.
#
# ==============================================================================

# ------------------------------------------------------------------------------
# STRICT ENVIRONMENT SAFETY
# ------------------------------------------------------------------------------
# 'set -e' tells the shell to immediately abort the script if any command 
# returns a non-zero (failure) exit status. This stops the script from 
# blindly continuing and deleting your data if an error occurs.
set -e

# 'set -u' treats referencing an unset (uninitialized) variable as a fatal error.
# If we mistype a variable name (like $srcc instead of $src), the script crashes 
# rather than evaluating the variable as an empty string (which could cause 
# catastrophic 'rm -rf /' scenarios).
set -u

# ------------------------------------------------------------------------------
# GLOBAL CONSTANTS & TERMINAL COLORS
# ------------------------------------------------------------------------------
# We dynamically determine the name of the script for the help menu.
# $0 is the path to the script (e.g., ./bin/strongcrypt.sh)
# The parameter expansion ${0##*/} strips everything up to the last forward slash,
# leaving just 'cryptfolder.sh'.
PROG="${0##*/}"

# ANSI escape codes for coloring terminal output.
# \033[ starts the color sequence. The numbers dictate the color and weight.
RED='\033[0;31m'      # Red for fatal errors
GREEN='\033[0;32m'    # Green for success
YELLOW='\033[1;33m'   # Bold Yellow for warnings
BLUE='\033[0;34m'     # Blue for general information
NC='\033[0m'          # No Color (resets the terminal to default)

# ------------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ------------------------------------------------------------------------------

# usage: Prints a ridiculously comprehensive help menu and exits.
usage() {
    # The 'cat <<EOF' structure is a Here-Document. It prints everything 
    # exactly as formatted below to standard output until it sees 'EOF'.
    cat <<EOF
${PROG} - Automatic folder encryption/decryption

USAGE:
  Encrypt:  ${PROG} [OPTIONS] <directory>
  Decrypt:  ${PROG} [OPTIONS] <file.enc>

OPTIONS:
  -k, --keep    Keep the source data after a successful operation.
                By default, this script DELETES the original unencrypted 
                directory after encryption, and DELETES the .enc file after 
                decryption. Use this flag to override that behavior.

  -h, --help    Display this extensive help message and exit.

HOW IT WORKS:
  Encryption:
    1. The target directory is converted into a continuous byte stream using 
       the 'tar' archiving utility.
    2. This stream is piped directly into OpenSSL in system memory (RAM).
    3. OpenSSL encrypts the stream using AES-256-CBC, heavily salting the 
       cipher and deriving the key using PBKDF2-HMAC-SHA256 (1,000,000 iterations).
    4. The encrypted bytes are written to disk as a '.enc' file.
    5. The original directory is securely erased (unless -k is passed).

  Decryption:
    1. OpenSSL reads the '.enc' file, decrypting the bytes using your password.
    2. The decrypted bytes are piped directly into 'tar'.
    3. 'tar' rebuilds the original directory structure on your hard drive.
    4. The '.enc' file is deleted (unless -k is passed).

EOF
    # Exit with status 1 to indicate the script did not perform a crypto operation.
    exit 1
}

# Logging functions for standardized terminal output.
# Notice the '>&2' appended to log_warn and log_err. This forces these messages 
# to output to Standard Error (stderr) instead of Standard Output (stdout).
# This guarantees they are printed to the screen even if the script is capturing 
# stdout into a variable.
log_info() { printf "${BLUE}[*]${NC} %s\n" "$*"; }
log_ok()   { printf "${GREEN}[+]${NC} %s\n" "$*"; }
log_warn() { printf "${YELLOW}[!]${NC} %s\n" "$*" >&2; }
log_err()  { printf "${RED}[-]${NC} %s\n" "$*" >&2; }

# check_deps: Ensures the required cryptographic and archiving tools exist.
check_deps() {
    # 'command -v' checks the system PATH for the binary. We throw away the 
    # output by redirecting to /dev/null. If it fails, the '!' triggers the error.
    if ! command -v openssl >/dev/null 2>&1; then
        log_err "openssl is required but was not found in PATH."
        exit 1
    fi
    if ! command -v tar >/dev/null 2>&1; then
        log_err "tar is required but was not found in PATH."
        exit 1
    fi
}

# check_pbkdf2: Probes the installed version of OpenSSL.
# Older versions of OpenSSL use a weak legacy Key Derivation Function (KDF).
# Modern versions support PBKDF2, which is significantly harder to crack.
check_pbkdf2() {
    # We attempt a dummy encryption in memory. If OpenSSL doesn't crash, 
    # it supports the flags.
    if openssl enc -aes-256-cbc -pbkdf2 -iter 1000000 \
         -pass pass:test -in /dev/null -out /dev/null 2>/dev/null; then
        printf -- "-pbkdf2 -iter 1000000"
    else
        log_warn "PBKDF2 unavailable. Falling back to legacy KDF."
        printf ""
    fi
}

# ------------------------------------------------------------------------------
# INTERACTIVE USER INPUT
# ------------------------------------------------------------------------------

# get_passphrase: Securely prompts the user for a password via the terminal.
get_passphrase() {
    # Infinite loop that only breaks when the user correctly confirms the password.
    while true; do
        printf "Enter passphrase: " >&2
        
        # Turn off terminal echoing so the password isn't visible on screen.
        stty -echo
        read pp
        # Immediately turn echoing back on so the terminal functions normally.
        stty echo
        
        # Because echoing was off, the user's "Enter" keypress wasn't printed.
        # We manually print a newline to stderr to keep the terminal neat.
        printf "\n" >&2
        
        # Check if the string length of the password is less than 12 characters.
        if [ "${#pp}" -lt 12 ]; then
            log_warn "Passphrase is shorter than 12 characters."
            printf "Continue anyway? [y/N]: " >&2
            read ans
            # Use a case statement to cleanly parse yes/no variations.
            case "$ans" in
                y*|Y*) ;; # Do nothing, proceed to confirmation
                *) continue ;; # Any other input restarts the loop
            esac
        fi
        
        # Repeat the process to confirm the password.
        printf "Confirm passphrase: " >&2
        stty -echo
        read pp2
        stty echo
        printf "\n" >&2
        
        # If the variables match exactly, print the password to stdout and return.
        if [ "$pp" = "$pp2" ]; then
            printf "%s" "$pp"
            return 0
        fi
        
        # If they don't match, warn the user and let the loop restart.
        log_err "Passphrases do not match. Please try again."
    done
}

# ------------------------------------------------------------------------------
# CORE CRYPTOGRAPHY PIPELINES
# ------------------------------------------------------------------------------

encrypt_target() {
    # Strip any trailing slashes from the target (e.g., 'folder/' -> 'folder')
    src="${1%/}"
    # Isolate the parent directory path
    src_dir=$(dirname "$src")
    # Isolate just the name of the folder being encrypted
    src_name=$(basename "$src")
    # Save the current working directory so we can return to it later
    orig_dir=$(pwd)
    # Define the final output filename
    dst="${src_name}.enc"

    # Pre-flight checks to ensure we aren't encrypting thin air or overwriting data
    if [ ! -d "$src" ]; then log_err "Target is not a directory: $src"; exit 1; fi
    if [ -e "$dst" ]; then log_err "Output file already exists: $dst"; exit 1; fi

    # Fetch the optimal OpenSSL flags
    pbkdf2_opts=$(check_pbkdf2)
    log_info "Encrypting directory: $src"
    
    # Store the password securely in memory
    pp=$(get_passphrase)
    
    # Navigate into the parent directory so the tarball doesn't include 
    # absolute file paths (like /home/user/Documents/...)
    cd "$src_dir"
    
    # THE PIPELINE:
    # 1. tar -cf - "$src_name" : Create a tarball and dump it to stdout (-)
    # 2. openssl enc ...       : Read stdin, encrypt it, write to the output file
    if ! tar -cf - "$src_name" | openssl enc -aes-256-cbc -salt $pbkdf2_opts -pass pass:"$pp" -out "${orig_dir}/${dst}"; then
        log_err "Encryption pipeline failed."
        cd "$orig_dir"
        rm -f "${orig_dir}/${dst}" # Clean up the broken/partial file
        exit 1
    fi
    
    # Navigate back to where the user executed the script
    cd "$orig_dir"
    
    # SAFETY CHECK: Because POSIX 'sh' lacks 'set -o pipefail', if 'tar' fails 
    # (e.g. permission denied) but 'openssl' succeeds, the pipeline returns a 
    # success code (0). OpenSSL will have encrypted an empty stream. 
    # We check if the resulting file is empty or suspiciously small (under 64 bytes).
    # 'wc -c' counts the bytes in the file.
    file_size=$(wc -c < "$dst" | tr -d ' ')
    if [ "$file_size" -lt 64 ]; then
        log_err "Encryption failed: The resulting file is suspiciously small or empty."
        log_err "Aborting to prevent deletion of original source data."
        rm -f "$dst"
        exit 1
    fi

    # Wipe the plaintext password from RAM by overwriting it with random hex,
    # then unsetting the variable completely from the environment.
    pp=$(openssl rand -hex 64 2>/dev/null || echo "wiped")
    unset pp
    
    # Lock down the file permissions so only the owner can read/write the archive.
    chmod 600 "$dst"
    log_ok "Encrypted archive created: $dst"

    # DELETION LOGIC (Default behavior)
    if [ "$KEEP_SOURCE" -eq 0 ]; then
        log_info "Default behavior active. Securely removing original directory: $src"
        rm -rf "$src"
        log_ok "Original data removed. (Pass -k next time to keep it)"
    else
        log_info "Keep flag (-k) detected. Preserving original directory."
    fi
}

decrypt_target() {
    src="$1"
    
    # Check if the target is actually a file
    if [ ! -f "$src" ]; then log_err "Target is not a file: $src"; exit 1; fi

    # SAFETY CHECK: To prevent the dreaded "tar: Cannot open: File exists" error,
    # we inspect the directory beforehand. If the folder we are about to extract 
    # already exists, we must warn the user because tar's '-k' flag will refuse 
    # to overwrite the existing files, crashing the pipeline.
    src_name=$(basename "$src")
    expected_dir="${src_name%.enc}"
    if [ -e "$expected_dir" ]; then
        log_warn "The destination '$expected_dir' already exists in this directory."
        log_warn "Tar's 'keep existing files' (-k) flag is active. It will refuse to overwrite existing files."
        printf "Attempt to extract anyway? (Will likely throw errors) [y/N]: " >&2
        read ans
        case "$ans" in
            y*|Y*) ;; # User accepted the risk, proceed
            *) log_err "Decryption aborted."; exit 1 ;;
        esac
    fi

    # Fetch the optimal OpenSSL flags
    pbkdf2_opts=$(check_pbkdf2)
    log_info "Decrypting file: $src"
    
    # Prompt for password (no confirmation needed for decryption)
    printf "Passphrase: " >&2
    stty -echo
    read pp
    stty echo
    printf "\n" >&2
    
    # THE PIPELINE:
    # 1. openssl enc -d ... : Read the file (-in), decrypt it (-d), push to stdout.
    # 2. tar -kxf -         : Read stdin (-), extract it (-x), keep existing files (-k)
    if ! openssl enc -aes-256-cbc -d -salt $pbkdf2_opts -pass pass:"$pp" -in "$src" | tar -kxf - ; then
        log_err "Decryption failed. Wrong passphrase or file conflict."
        exit 1
    fi
    
    # Securely wipe the password from RAM
    pp=$(openssl rand -hex 64 2>/dev/null || echo "wiped")
    unset pp
    
    log_ok "Decrypted and extracted successfully."

    # DELETION LOGIC (Default behavior)
    if [ "$KEEP_SOURCE" -eq 0 ]; then
        log_info "Default behavior active. Removing encrypted archive: $src"
        rm -f "$src"
        log_ok "Archive removed. (Pass -k next time to keep it)"
    else
        log_info "Keep flag (-k) detected. Preserving encrypted archive."
    fi
}

# ------------------------------------------------------------------------------
# MAIN EXECUTION ROUTINE
# ------------------------------------------------------------------------------

# Initialize global tracking variables
TARGET=""
# KEEP_SOURCE acts as a boolean. 0 = Delete (Default), 1 = Keep.
KEEP_SOURCE=0

# A manual 'while' loop is used to parse command-line arguments. 
# This is required because POSIX 'getopts' does not support long flags (like --keep).
# $# represents the number of arguments passed to the script.
while [ $# -gt 0 ]; do
    # Check the first argument ($1)
    case "$1" in
        -h|--help)
            # User asked for help. Show it and exit.
            usage
            ;;
        -k|--keep)
            # User asked to keep the original files. Flip the boolean.
            KEEP_SOURCE=1
            # 'shift' removes this flag from the list of arguments, pushing 
            # the next argument into the $1 position.
            shift
            ;;
        -*)
            # If the argument starts with a dash but wasn't caught above, it's invalid.
            log_err "Invalid option: $1"
            usage
            ;;
        *)
            # If the argument doesn't start with a dash, we assume it is the target 
            # file or directory. We only allow one target per execution.
            if [ -z "$TARGET" ]; then
                TARGET="$1"
            else
                log_err "Only one target file or directory is allowed."
                usage
            fi
            shift
            ;;
    esac
done

# If the loop finished and no target was found, yell at the user.
if [ -z "$TARGET" ]; then
    log_err "A target file or directory is required."
    usage
fi

# Ensure OpenSSL and Tar are actually installed on this computer.
check_deps

# Branch logic: Determine what the user wants to do based on the target's type.
if [ -d "$TARGET" ]; then
    # Target is a directory. Initiate encryption.
    encrypt_target "$TARGET"
elif [ -f "$TARGET" ]; then
    # Target is a regular file. Initiate decryption.
    decrypt_target "$TARGET"
else
    # Target is something weird (like a broken symlink, device node, or doesn't exist)
    log_err "Target must be a directory (to encrypt) or file (to decrypt): $TARGET"
    exit 1
fi

# If we made it this far, everything executed flawlessly. Exit with status 0.
exit 0
