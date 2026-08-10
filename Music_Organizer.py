#!/usr/bin/env python3
# ==============================================================================
# Copyright 2026 Pau Amaro Seoane
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
#
# NOTE: This script is designed to organize audio files downloaded from YouTube.
# To download high-quality MP3s from YouTube, you can use the following command:
#
# yt-dlp -x --audio-format mp3 --audio-quality 0 "YOUTUBEURL"
#
# Note: If you find the error with yt-dlp:
#
#    "No supported JavaScript runtime could be found"
#
# You might need to do the following:
# 
# curl -fsSL https://deno.land/install.sh | sh
#
# ==============================================================================
#
# USAGE:
#   python3 Music_Organizer.py [--rename] [--artist ARTIST] [--album ALBUM]
#
#   If no --artist/--album provided, the script looks for a text file:
#        Artist__Album.txt   (double underscore)
#
#   If iTunes cannot find the tracklist, you will be prompted to create a
#   file named 'tracklist.txt' with one track title per line in the correct order.
#
#   Example tracklist.txt:
#        Main Title
#        The Devil's Advocate
#        Fire
#        ...
#
#   Then the script will match your MP3 files to these titles and rename them
#   with track numbers.
#
#   Use --rename to actually rename files; otherwise it's a dry-run preview.
#
#   Run with -h or --help for more details.
#
# ==============================================================================

# -----------------------------------------------------------------------------
# Import standard Python modules
# -----------------------------------------------------------------------------
import os
import re
import json
import urllib.request
import urllib.parse
import difflib
import glob
import sys
import argparse

# ==============================================================================
# CONFIGURATION – adjust these to suit your needs
# ==============================================================================

DRY_RUN = True                 # Set to False to actually rename
FUZZY_CUTOFF = 0.4             # Lower = more lenient matching
SEARCH_LIMIT = 50              # Max iTunes results

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_album_info_from_file():
    """
    Finds a text file in the current directory with format:
        Artist__Album.txt
    (double underscore separates artist and album).
    Returns (artist, album) or (None, None).
    """
    txt_files = glob.glob("*.txt")
    for file in txt_files:
        if "__" in file:
            base = os.path.splitext(file)[0]
            artist_raw, album_raw = base.split("__", 1)
            artist = artist_raw.replace("_", " ").strip()
            album = album_raw.replace("_", " ").strip()
            return artist, album
    return None, None

def load_local_tracklist(filename="tracklist.txt"):
    """
    Loads a tracklist from a text file.
    Each line is a track title (no numbers).
    Returns a dict: {title: padded_number} where number is sequential starting from 01.
    Returns None if file not found.
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            print(f"Warning: '{filename}' exists but is empty.")
            return None
        tracklist = {}
        # Assign numbers sequentially starting from 01
        for idx, title in enumerate(lines, start=1):
            num = str(idx).zfill(2)
            tracklist[title] = num
        return tracklist
    except FileNotFoundError:
        return None

def fetch_album_tracklist(artist, album):
    """
    Fetches official tracklist from iTunes.
    Returns dict {title: padded_number} or None on failure.
    """
    print(f"Searching iTunes for: {artist} - {album}...")
    # First try album search
    query = f"{artist} {album}"
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=album&limit={SEARCH_LIMIT}"
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
        # Find best matching album
        best_match = None
        best_score = 0.0
        for result in data.get('results', []):
            result_artist = result.get('artistName', '')
            result_album = result.get('collectionName', '')
            artist_words = set(artist.lower().split())
            album_words = set(album.lower().split())
            res_artist_words = set(result_artist.lower().split())
            res_album_words = set(result_album.lower().split())
            if artist_words and album_words:
                artist_overlap = len(artist_words & res_artist_words) / max(len(artist_words), 1)
                album_overlap = len(album_words & res_album_words) / max(len(album_words), 1)
                score = (artist_overlap + album_overlap) / 2
                if score > best_score:
                    best_score = score
                    best_match = result
        if best_match and best_score >= 0.3:
            collection_id = best_match.get('collectionId')
            if collection_id:
                lookup_url = f"https://itunes.apple.com/lookup?id={collection_id}&entity=song"
                lookup_resp = urllib.request.urlopen(lookup_url)
                lookup_data = json.loads(lookup_resp.read())
                tracklist = {}
                for res in lookup_data.get('results', []):
                    if res.get('kind') == 'song':
                        track_name = res.get('trackName')
                        track_num = res.get('trackNumber')
                        if track_name and track_num:
                            tracklist[track_name] = str(track_num).zfill(2)
                if tracklist:
                    print(f"Success: Found {len(tracklist)} tracks from album.")
                    return tracklist
    except Exception as e:
        print(f"Album search error: {e}")

    # Fallback: song-level search
    print("Album search failed. Trying song-level search...")
    try:
        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit=200"
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
        tracklist = {}
        for result in data.get('results', []):
            result_artist = result.get('artistName', '')
            result_album = result.get('collectionName', '')
            if artist.lower() in result_artist.lower() and album.lower() in result_album.lower():
                track_name = result.get('trackName')
                track_num = result.get('trackNumber')
                if track_name and track_num:
                    tracklist[track_name] = str(track_num).zfill(2)
        if tracklist:
            print(f"Song search success: Found {len(tracklist)} tracks.")
            return tracklist
        else:
            print("Song search failed.")
            return None
    except Exception as e:
        print(f"Song search error: {e}")
        return None

def get_tracklist_from_user_interactive():
    """
    Asks the user to enter track numbers and titles manually.
    Returns a dict {title: padded_number}.
    """
    print("\nPlease enter the tracklist for this album (one track per line).")
    print("Format: number title (e.g., '01 Hello' or '01. Hello')")
    print("Press Enter on an empty line when done.")
    tracklist = {}
    while True:
        line = input("Track: ").strip()
        if not line:
            break
        # Try to parse "01. Title" or "01 Title"
        match = re.match(r'^(\d+)[\.\s]+(.+)$', line)
        if match:
            num = match.group(1).zfill(2)
            title = match.group(2).strip()
            tracklist[title] = num
        else:
            print("Invalid format. Use '01 Title' or '01. Title'.")
    return tracklist

def clean_song_title(filename, artist):
    """
    Cleans the filename to extract a pure song title for matching.
    Removes artist name, YouTube IDs, common tags, and separators.
    """
    # Remove extension
    name, _ = os.path.splitext(filename)
    
    # Remove bracketed content [like this]
    name = re.sub(r'\s*\[.*?\]\s*', ' ', name)
    # Remove parenthetical content that are common tags: (Official Video), (Audio), etc.
    name = re.sub(r'(?i)\s*\(official\s*(video|audio|music\s*video)\)', '', name)
    name = re.sub(r'(?i)\s*\(remastered\)', '', name)
    name = re.sub(r'(?i)\s*\(lyric\s*(video)?\)', '', name)
    name = re.sub(r'(?i)\s*official\s*(video|audio)', '', name)
    
    # Remove "by Artist" pattern
    name = re.sub(rf'(?i)\s*by\s+{re.escape(artist)}', '', name)
    
    # Remove artist name from the end: common pattern " - Artist" or "｜ Artist"
    escaped_artist = re.escape(artist)
    # Look for artist at the end after a separator: (?: - |\s*[｜|]\s*|\s+by\s+)
    pattern = re.compile(rf'\s*[-–—]\s*{escaped_artist}\s*$', re.IGNORECASE)
    name = re.sub(pattern, '', name)
    pattern = re.compile(rf'\s*[｜|]\s*{escaped_artist}\s*$', re.IGNORECASE)
    name = re.sub(pattern, '', name)
    # Also if artist is at the beginning: "Artist - Song" -> "Song"
    pattern = re.compile(rf'^{escaped_artist}\s*[-–—]\s*', re.IGNORECASE)
    name = re.sub(pattern, '', name)
    pattern = re.compile(rf'^{escaped_artist}\s*[｜|]\s*', re.IGNORECASE)
    name = re.sub(pattern, '', name)
    
    # Remove standalone word "by"
    name = re.sub(r'(?i)\s*\bby\b\s*', ' ', name)
    # Remove any leftover youtube-dl artifacts like "'$'..."
    name = re.sub(r"'\$'.*?''", '', name)
    
    # Replace any remaining punctuation except apostrophe and hyphen with space
    name = re.sub(r'[^\w\s\'-]', ' ', name)
    # Normalize spaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def format_clean_name(text):
    """Converts text to Title_Case_With_Underscores, removing special chars."""
    text = re.sub(r'[/:]', ' ', text)
    text = text.title()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', '_', text)
    return text

def interactive_mapping(unmatched_files, tracklist, artist, album):
    """
    Manually map unmatched files to track numbers.
    Returns dict {original_filename: new_filename}.
    """
    mappings = {}
    sorted_tracks = sorted((num, title) for title, num in tracklist.items())
    print("\nSome files couldn't be matched. Please map each one to a track.")
    print("Available tracks:")
    for num, title in sorted_tracks:
        print(f"  {num}: {title}")
    
    for filename in unmatched_files:
        cleaned = clean_song_title(filename, artist)
        print(f"\nFile: {filename}")
        print(f"Cleaned title: '{cleaned}'")
        choice = input("Enter track number to map, 's' to skip, 'q' to quit: ").strip()
        if choice.lower() == 'q':
            sys.exit(0)
        if choice.lower() == 's':
            continue
        # Find track by number
        found = next(( (num, title) for num, title in sorted_tracks if num == choice.zfill(2) ), None)
        if found:
            prefix_artist = format_clean_name(artist)
            prefix_album = format_clean_name(album)
            clean_song = format_clean_name(found[1])
            new_name = f"{prefix_artist}_{prefix_album}_{found[0]}_{clean_song}.mp3"
            mappings[filename] = new_name
        else:
            print(f"Invalid number. Skipping {filename}.")
    return mappings

def obtain_tracklist(artist, album):
    """
    Obtains a tracklist from one of several sources:
    1. Local file 'tracklist.txt' (user-provided)
    2. iTunes API
    3. User creates 'tracklist.txt' after being prompted
    4. User enters tracklist interactively
    Returns a dict {title: padded_number} or None if cancelled.
    """
    # First check for local tracklist
    tracklist = load_local_tracklist()
    if tracklist:
        print(f"Found local 'tracklist.txt' with {len(tracklist)} tracks.")
        return tracklist

    # Try iTunes
    tracklist = fetch_album_tracklist(artist, album)
    if tracklist:
        return tracklist

    # iTunes failed – ask user to create a tracklist file
    print("\nCould not retrieve tracklist from iTunes.")
    print("Please create a file named 'tracklist.txt' in this folder.")
    print("Add one track title per line in the correct order (no numbers).")
    print("Example:")
    print("  Main Title")
    print("  The Devil's Advocate")
    print("  Fire")
    print("  ...")
    print("\nPress Enter when you have created the file, or type 'skip' to continue without a tracklist.")
    response = input().strip().lower()
    if response == 'skip':
        return None
    # Try to load again
    tracklist = load_local_tracklist()
    if tracklist:
        print(f"Loaded tracklist with {len(tracklist)} tracks.")
        return tracklist
    else:
        print("Still no tracklist found.")
        # Ask if user wants to enter manually
        choice = input("Do you want to enter the tracklist manually now? (y/n): ").strip().lower()
        if choice == 'y':
            return get_tracklist_from_user_interactive()
        else:
            return None

def main():
    # Create the argument parser – -h/--help is automatically included
    parser = argparse.ArgumentParser(description="Organize MP3 files with iTunes tracklist.")
    parser.add_argument('--rename', action='store_true', help="Actually rename files (otherwise dry-run).")
    parser.add_argument('--artist', type=str, help="Override artist name.")
    parser.add_argument('--album', type=str, help="Override album name.")
    # Note: -h and --help are provided automatically by argparse

    args = parser.parse_args()

    global DRY_RUN
    if args.rename:
        DRY_RUN = False

    # Get artist/album
    artist, album = None, None
    if args.artist and args.album:
        artist = args.artist
        album = args.album
        print(f"Using artist: {artist}, album: {album} (from command line)")
    else:
        artist, album = get_album_info_from_file()
        if not artist or not album:
            print("Error: No artist/album found.")
            print("Please create 'Artist__Album.txt' or use --artist and --album.")
            return

    # Obtain tracklist
    tracklist = obtain_tracklist(artist, album)
    if tracklist is None:
        print("Proceeding without a tracklist – all files will be numbered '00'.")
        tracklist = {}

    # List MP3 files
    files = [f for f in os.listdir('.') if f.lower().endswith('.mp3')]
    if not files:
        print("No .mp3 files found.")
        return

    print(f"\nFound {len(files)} MP3 files.\n")

    prefix_artist = format_clean_name(artist)
    prefix_album = format_clean_name(album)

    rename_map = {}
    unmatched = []

    for filename in files:
        cleaned = clean_song_title(filename, artist)
        print(f"Processing: {filename}")
        print(f"  Cleaned: '{cleaned}'")
        
        # Try exact match after normalization
        def normalize(s):
            s = re.sub(r'[^\w\s]', '', s).lower()
            s = re.sub(r'\s+', ' ', s).strip()
            return s
        normalized_cleaned = normalize(cleaned)
        best_match = None
        for official_title in tracklist.keys():
            if normalize(official_title) == normalized_cleaned:
                best_match = official_title
                break
        if best_match:
            print(f"  Exact match: '{best_match}'")
        else:
            # Fuzzy match
            matches = difflib.get_close_matches(cleaned, tracklist.keys(), n=1, cutoff=FUZZY_CUTOFF)
            if matches:
                best_match = matches[0]
                print(f"  Fuzzy match: '{best_match}' (cutoff={FUZZY_CUTOFF})")
            else:
                print(f"  No match found.")
        
        if best_match:
            track_num = tracklist[best_match]
            clean_song = format_clean_name(best_match)
            new_name = f"{prefix_artist}_{prefix_album}_{track_num}_{clean_song}.mp3"
            rename_map[filename] = new_name
        else:
            unmatched.append(filename)

    # Handle unmatched
    if unmatched:
        print(f"\n{len(unmatched)} files unmatched.")
        if tracklist and len(tracklist) > 0:
            choice = input("Do you want to manually map them? (y/n): ").strip().lower()
            if choice == 'y':
                manual = interactive_mapping(unmatched, tracklist, artist, album)
                rename_map.update(manual)
                # Remove those that were manually mapped from unmatched list
                unmatched = [f for f in unmatched if f not in manual]
        # For any remaining unmatched, use "00_"
        for filename in unmatched:
            clean_title = clean_song_title(filename, artist)
            clean_song = format_clean_name(clean_title)
            new_name = f"{prefix_artist}_{prefix_album}_00_{clean_song}.mp3"
            rename_map[filename] = new_name
            print(f"  Using '00_' for: {filename}")

    # Summary
    print("\n--- RENAMING SUMMARY ---")
    for orig, new in rename_map.items():
        if orig != new:
            print(f"  {orig}  ->  {new}")

    if DRY_RUN:
        print("\n--- DRY RUN: No files were changed. ---")
        print("Run with --rename to actually rename.")
    else:
        for orig, new in rename_map.items():
            if orig != new and os.path.exists(orig):
                try:
                    os.rename(orig, new)
                    print(f"Renamed: {orig} -> {new}")
                except Exception as e:
                    print(f"Error renaming {orig}: {e}")
        print("\n--- Renaming complete. ---")

if __name__ == '__main__':
    main()