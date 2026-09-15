#!/usr/bin/env bash
# =======================================================================
# Script Name:    LuksCreateUSB.sh
# Description:    Automates the secure creation of a LUKS2 encrypted USB drive
#                 using the whole-disk method (no partition table). Implements
#                 multiple rigorous safety checks to prevent accidental data loss,
#                 wipes the drive prior to encryption, and provisions it with
#                 the strongest available LUKS2 cryptographic parameters.
#                 Supports auto-detection of the USB drive via dmesg.
#
#                 Crucially, it checks for and closes any existing active
#                 device-mapper LUKS targets to prevent "Resource Busy" errors
#                 and stale mapper node issues (which cause read-only bugs).
#
# Author:         Pau Amaro Seoane
# Date:           2026-09-14
# Version:        1.4.0
# Requires:       bash, cryptsetup, dd, lsblk, dmesg, fdisk, mkfs.ext4, openssl
# Usage:          sudo ./LuksCreateUSB.sh [OPTIONS] [DEVICE_PATH]
#                 Example: sudo ./LuksCreateUSB.sh 
#                 Example: sudo ./LuksCreateUSB.sh -D
# ========================================================================
# Copyright (c) 2026 Pau Amaro Seoane
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
# ==================================================================

set -e
set -o pipefail

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[1;35m'
NC='\033[0m' # No Color

# Default variables
DRY_RUN=false
DEVICE=""

# =======================================================================
# Functions
# ==================================================================
show_help() {
    echo -e "${CYAN}====================================================${NC}"
    echo -e "${CYAN}       LUKS USB Drive Encryption Utility            ${NC}"
    echo -e "${CYAN}====================================================${NC}"
    echo -e "Usage: sudo $0 [OPTIONS] [DEVICE_PATH]"
    echo ""
    echo -e "Options:"
    echo -e "  -h, --help       Show this help message and exit."
    echo -e "  -D, --dry        Run a dry test with verbose output (no data is destroyed)."
    echo ""
    echo -e "If DEVICE_PATH is omitted, the script will attempt to auto-detect"
    echo -e "the most recently attached USB drive by inspecting 'dmesg'."
    echo ""
    echo -e "Examples:"
    echo -e "  sudo $0                  # Auto-detects device and proceeds"
    echo -e "  sudo $0 -D               # Dry-run auto-detection without changes"
    echo -e "  sudo $0 /dev/sdc         # Manually specify device /dev/sdc"
}

run_destructive() {
    local DESC=$1
    local CMD=$2
    if [ "$DRY_RUN" = true ]; then
        echo -e "${MAGENTA}[DRY RUN] Would execute: ${CMD}${NC}"
    else
        echo -e "${CYAN}[EXEC] ${DESC}${NC}"
        eval "$CMD"
    fi
}

# =========================================================================
# Argument Parsing
# =======================================================================
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -D|--dry)
            DRY_RUN=true
            shift
            ;;
        /dev/sd*|/dev/nvme*|/dev/vd*)
            DEVICE=$1
            shift
            ;;
        *)
            echo -e "${RED}Unknown parameter passed: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}       LUKS USB Drive Encryption Utility            ${NC}"
echo -e "${CYAN}====================================================${NC}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${MAGENTA}*** DRY RUN MODE ENABLED. NO DATA WILL BE DESTROYED. ***${NC}"
fi

# Check for root privileges (required for dmesg, fdisk, cryptsetup)
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}ERROR: This script must be run as root. Try using sudo.${NC}"
    exit 1
fi

# =======================================================================
# Device Auto-Detection
# ========================================================================
if [ -z "$DEVICE" ]; then
    echo -e "\n${YELLOW}No device specified. Attempting to auto-detect from dmesg...${NC}"
    
    # Extract the device name from the last "Attached SCSI removable disk" line
    GUESSED_DEV=$(dmesg | grep "Attached SCSI removable disk" | tail -n 1 | sed -n 's/.*\[\(sd[a-z]*\)\].*/\1/p')

    if [ -n "$GUESSED_DEV" ]; then
        DEVICE="/dev/$GUESSED_DEV"
        echo -e "${GREEN}SUCCESS: Found recently attached USB device in dmesg: ${DEVICE}${NC}"
        
        # Cross-verify with fdisk
        echo -e "${YELLOW}Cross-checking with fdisk -l...${NC}"
        FDISK_MATCH=$(fdisk -l 2>/dev/null | grep "^Disk $DEVICE:")
        
        if [ -n "$FDISK_MATCH" ]; then
            echo -e "${GREEN}Verified $DEVICE in fdisk output:${NC}"
            echo -e "  -> ${CYAN}${FDISK_MATCH}${NC}"
        else
            echo -e "${RED}WARNING: $DEVICE was found in dmesg but not in fdisk -l!${NC}"
            echo -e "This might mean the device was disconnected."
            exit 1
        fi
        
        echo -e "\n${YELLOW}I am going to use: ${RED}${DEVICE}${NC}"
        printf "Is this correct? Press [Enter] to proceed with %s or CTRL+C to abort..." "$DEVICE"
        read -r
    else
        echo -e "${RED}Could not auto-detect a removable USB device from dmesg.${NC}"
        echo -e "Currently attached block devices (excluding loops):"
        lsblk -d -o NAME,SIZE,MODEL,TRAN | grep -v "loop"
        echo ""
        printf "Please manually enter the device path to encrypt (e.g., /dev/sdb): "
        read -r DEVICE
    fi
fi

# ==================================================================
# CHECK 1:  Ensure it is a valid block device, FFS!
# =======================================================================
if [ ! -b "$DEVICE" ]; then
    echo -e "${RED}ERROR: '$DEVICE' is not a valid block device.${NC}"
    exit 1
fi

# =======================================================================
# CHECK 2:   Ensure the device is not currently mounted
# =========================================================================
# This checks both the raw device and any mapped/partitioned children.
# If a desktop environment mounted the unlocked LUKS volume, it will show up here.
if lsblk -no MOUNTPOINT "$DEVICE" | grep -qE '[a-zA-Z0-9]'; then
    echo -e "${RED}ERROR: '$DEVICE' or its mapped partitions are currently mounted!${NC}"
    lsblk "$DEVICE"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${MAGENTA}[DRY RUN] Would normally exit here, but continuing for dry run...${NC}"
    else
        echo -e "${YELLOW}Please unmount it first before proceeding (e.g., sudo umount /mnt/...).${NC}"
        exit 1
    fi
fi

# Check if it's potentially a system drive (non-removable)
REMOVABLE=$(lsblk -ndo RM "$DEVICE" 2>/dev/null || echo "0")
if [ "$REMOVABLE" != "1" ]; then
    echo -e "${RED}WARNING: $DEVICE appears to be a NON-REMOVABLE drive!${NC}"
    echo -e "${RED}Are you absolutely sure this is not your system drive?${NC}"
fi

# ========================================================================
# CHECK 3:   Verify Size and Layout (fdisk & lsblk)
# ==================================================================
echo -e "\n${YELLOW}--- VERIFICATION STEP 1: Device Layout ---${NC}"
fdisk -l "$DEVICE" | head -n 10 || true
echo ""
lsblk "$DEVICE" || true

echo -e "\n${YELLOW}Does the size and model match the USB drive you intend to wipe?${NC}"
printf "Press [Enter] to continue to the next check, or CTRL+C to abort..."
read -r

# =================================================================
# CHECK 4:  Verify via Kernel Ring Buffer (dmesg)
# ========================================================================
echo -e "\n${YELLOW}--- VERIFICATION STEP 2: Recent Kernel Events ---${NC}"
echo -e "Showing the last 20 kernel messages to help you identify if this is the USB you just plugged in:"
echo "----------------------------------------------------------------------"
dmesg | tail -n 20
echo "----------------------------------------------------------------------"
printf "Does the dmesg output confirm that %s is the correct USB drive? (y/N): " "$DEVICE"
read -r CONFIRM_DMESG

if [[ ! "$CONFIRM_DMESG" =~ ^[Yy]$ ]]; then
    echo -e "${RED}Aborted by user.${NC}"
    exit 1
fi

# ========================================================================
# CHECK 5:  Final Explicit Confirmation... idiot proof.
# =======================================================================
echo -e "\n${RED}======================================================================${NC}"
echo -e "${RED}                      !!! POINT OF NO RETURN !!!                      ${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${MAGENTA}   (Actually, this is a dry run, so your data is safe. But still!)    ${NC}"
else
    echo -e "${RED} You are about to completely DESTROY ALL DATA on $DEVICE.${NC}"
fi
echo -e "${RED}======================================================================${NC}"

# Allow the user to press Enter to accept the default, or Ctrl+C to exit
printf "Press [Enter] to permanently wipe and encrypt (%s) or CTRL+C to abort..." "$DEVICE"
read -r

# =======================================================================
# PHASE 0:    Close Existing LUKS Mappings (Crucial Step)
# ==================================================================
# If the USB drive previously contained a LUKS container and was plugged in,
# a desktop environment like GNOME or KDE might have automatically unlocked it 
# and mapped it to /dev/mapper/luks-xxxx. 
#
# Even if it is unmounted (which we checked for in CHECK 2), the *mapping* 
# still locks the underlying physical device. If we attempt to use `dd` or 
# `cryptsetup luksFormat` while this mapping exists, the kernel will throw a 
# "Device or resource busy" error. It can also leave stale device-mapper nodes 
# that confuse the OS later and cause "Read-only file system" errors.
#
# We iterate through any children of $DEVICE that have a type of "crypt"
# and explicitly close them.
echo -e "\n${CYAN}--- Checking for active LUKS mappings ---${NC}"

# Find all 'crypt' type devices that are dependent on the target $DEVICE
ACTIVE_MAPPINGS=$(lsblk -lno NAME,TYPE "$DEVICE" 2>/dev/null | awk '$2 == "crypt" {print $1}')

if [ -n "$ACTIVE_MAPPINGS" ]; then
    echo -e "${YELLOW}Found active device-mapper targets on $DEVICE. Cleaning up...${NC}"
    for MAPPING in $ACTIVE_MAPPINGS; do
        # cryptsetup close is the modern equivalent of cryptsetup luksClose
        run_destructive "Removing stale LUKS mapping: $MAPPING" "cryptsetup close $MAPPING"
    done
    # Give the kernel and udev a brief moment to unregister the block devices
    sleep 1
else
    echo -e "${GREEN}No active LUKS mappings found. The device is free.${NC}"
fi

# =================================================================
# PHASE 1:  Securely Wipe the Drive
# ========================================================================
echo -e "\n${CYAN}--- Wiping Device ---${NC}"
printf "Do you want to fill the drive with random data first? (Takes time, but recommended for obvious reasons) [Y/n]: "
read -r DO_WIPE

if [[ ! "$DO_WIPE" =~ ^[Nn]$ ]]; then
    echo -e "${GREEN}Preparing to wipe $DEVICE with secure pseudo-random data...${NC}"
    if command -v openssl >/dev/null 2>&1; then
        # OpenSSL AES stream is considerably faster than /dev/urandom on modern CPUs
        WIPE_CMD='openssl enc -aes-256-ctr -pass pass:"$(dd if=/dev/urandom bs=128 count=1 2>/dev/null | base64)" -nosalt < /dev/zero | dd of='"$DEVICE"' bs=4M status=progress'
        run_destructive "Wiping device via OpenSSL & dd" "$WIPE_CMD"
    else
        echo -e "${YELLOW}openssl not found, falling back to /dev/urandom...${NC}"
        WIPE_CMD="dd if=/dev/urandom of=$DEVICE bs=4M status=progress"
        run_destructive "Wiping device via /dev/urandom" "$WIPE_CMD"
    fi
    echo -e "${GREEN}Wipe phase completed (or simulated).${NC}"
else
    echo -e "${YELLOW}Skipping wipe step.${NC}"
fi

# ========================================================================
# PHASE 2:     Create LUKS Container (Method 1: Whole Drive)
# ==================================================================
echo -e "\n${CYAN}--- Creating LUKS2 Encrypted Container ---${NC}"
echo -e "Using the strongest possible algorithms (AES-256-XTS, SHA512, Argon2id, 5000ms iterations)..."

# Adding --batch-mode bypasses the secondary "WARNING! Are you sure? (Type YES...)" prompt
LUKS_CMD="cryptsetup luksFormat --batch-mode --type luks2 \
    --cipher aes-xts-plain64 \
    --key-size 512 \
    --hash sha512 \
    --pbkdf argon2id \
    --iter-time 5000 \
    --use-random \
    $DEVICE"

run_destructive "Formatting $DEVICE as LUKS2" "$LUKS_CMD"

# =================================================================
# PHASE 3:    Open Container and Format Filesystem
# =======================================================================
MAPPER_NAME="SecureUSB_$(date +%s)"
echo -e "\n${CYAN}--- Opening Container ---${NC}"
run_destructive "Opening LUKS container at /dev/mapper/$MAPPER_NAME" "cryptsetup open $DEVICE $MAPPER_NAME"

echo -e "\n${CYAN}--- Creating ext4 Filesystem ---${NC}"
run_destructive "Creating ext4 filesystem" "mkfs.ext4 -L \"SecureUSB\" /dev/mapper/$MAPPER_NAME"

# =======================================================================
# PHASE 4:    Configure Mount Point and Permissions
# ==================================================================
echo -e "\n${CYAN}--- Configuring Mount Point and Permissions ---${NC}"
MOUNT_DIR="/mnt/SecureUSB"

run_destructive "Creating mount directory" "mkdir -p $MOUNT_DIR"
run_destructive "Mounting mapped device" "mount /dev/mapper/$MAPPER_NAME $MOUNT_DIR"

# Determine the actual user who ran sudo to give them ownership of the mount
REAL_USER=${SUDO_USER:-$(whoami)}
run_destructive "Setting directory ownership to $REAL_USER" "chown -R $REAL_USER:$REAL_USER $MOUNT_DIR"
run_destructive "Setting secure permissions (700)" "chmod 700 $MOUNT_DIR"

echo -e "\n${GREEN}======================================================================${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${MAGENTA} DRY RUN COMPLETE! Your encrypted USB drive would now be ready.${NC}"
else
    echo -e "${GREEN} SUCCESS! Your encrypted USB drive is ready.${NC}"
fi
echo -e "${GREEN}======================================================================${NC}"
echo -e "It will be mounted at: ${YELLOW}$MOUNT_DIR${NC}"
echo -e "Owned by user: ${YELLOW}$REAL_USER${NC}"
echo -e "\nTo safely remove this drive, run the following commands later:"
echo -e "  sudo umount $MOUNT_DIR"
echo -e "  sudo cryptsetup close $MAPPER_NAME"
echo -e "${GREEN}======================================================================${NC}"
