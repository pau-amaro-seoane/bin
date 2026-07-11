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
#
# Setup Instructions
# -------------------
#  Put all your downloaded .mp3 files for one specific album into a folder.
#
#  Inside that folder, create an empty text file. 
#
#  Name it like this: 
#
#      Author_Name__Album_Name.txt 
#
#  Make sure there are two underscores separating the artist and album
#
#  Drop this script into the folder and run it.
#
#
# ==============================================================================

# Import the os module to interact with the operating system (renaming files)
import os
# Import the re module to use regular expressions for text cleaning
import re
# Import the json module to parse the data returned by the iTunes API
import json
# Import urllib.request to fetch data from the internet
import urllib.request
# Import urllib.parse to safely encode search terms into URLs
import urllib.parse
# Import difflib to fuzzily match messy filenames with official song titles
import difflib
# Import glob to easily search for specific file types (like .txt)
import glob

# Global toggle to prevent accidental renaming while testing
# Change this to False ONLY when you are ready to rename the files
DRY_RUN = True 

def get_album_info_from_file():
    """Finds a .txt file formatted as 'Artist__Album_Name.txt' to use as metadata."""
    # Find all text files in the current directory
    txt_files = glob.glob("*.txt")
    
    # Loop through every text file found
    for file in txt_files:
        # Check if the double underscore separator is in the filename
        if "__" in file:
            # Strip away the '.txt' extension to isolate the name
            name_part = os.path.splitext(file)[0]
            
            # Split the name into artist and album using the double underscore
            artist_raw, album_raw = name_part.split("__", 1)
            
            # Replace single underscores with spaces for the artist name (for iTunes)
            artist = artist_raw.replace("_", " ").strip()
            # Replace single underscores with spaces for the album name (for iTunes)
            album = album_raw.replace("_", " ").strip()
            
            # Return the clean artist and album names to the main program
            return artist, album
            
    # If no file matching the format is found, return nothing
    return None, None

def fetch_itunes_tracklist(artist, album):
    """Fetches the official tracklist from the iTunes API."""
    # Print a status message to let the user know what is happening
    print(f"Searching iTunes for: {artist} - {album}...")
    
    # Combine the artist and album into a single search query string
    query = f"{artist} {album}"
    # Construct the iTunes API URL, making sure the query is URL-safe
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit=100"
    
    # Try block to handle any potential internet connection errors gracefully
    try:
        # Open the URL and request the data
        response = urllib.request.urlopen(url)
        # Read the response and decode it from JSON into a Python dictionary
        data = json.loads(response.read())
        
        # Create an empty dictionary to hold our final tracklist
        tracklist = {}
        
        # Loop through every song result returned by iTunes
        for result in data.get('results', []):
            # Check if the artist name roughly matches what we are looking for
            if artist.lower() in result.get('artistName', '').lower() and \
               album.lower() in result.get('collectionName', '').lower(): # Check album match
                
                # Extract the official track name
                track_name = result.get('trackName')
                # Extract the official track number
                track_num = result.get('trackNumber')
                
                # Save it to our dictionary, padding the number with a zero (e.g., '01')
                tracklist[track_name] = str(track_num).zfill(2)
                
        # If the loop finishes and the dictionary is empty, the album wasn't found
        if not tracklist:
            # Warn the user
            print("Warning: Could not find exact album matches on iTunes. Check spelling.")
            # Return nothing
            return None
            
        # Tell the user how many tracks were successfully found
        print(f"Success: Found {len(tracklist)} tracks online!\n")
        # Return the populated tracklist dictionary
        return tracklist
        
    # Catch any connection errors (like being offline)
    except Exception as e:
        # Print the exact error message
        print(f"Error: Failed to connect to iTunes: {e}")
        # Return nothing
        return None

def isolate_song_title(filename, artist):
    """Strips junk to isolate just the song title for better matching."""
    # Separate the filename from its .mp3 extension
    name, _ = os.path.splitext(filename)
    
    # Remove YouTube IDs and anything else enclosed in brackets
    name = re.sub(r'\s*\[.*?\]', '', name)
    # Remove tags like '(Official Video)' enclosed in parentheses
    name = re.sub(r'\s*\(.*?\)', '', name)
    # Remove bizarre bash-escaped sequences downloaded by youtube-dl/yt-dlp
    name = re.sub(r"'\$'.*?''", "", name)
    # Remove the artist's name from the track title string
    name = re.sub(f'(?i){artist}', '', name)
    # Remove the standalone word 'by'
    name = re.sub(r'(?i)\bby\b', '', name)
    # Remove common video and audio metadata keywords
    name = re.sub(r'(?i)official video|audio|remastered|lyric', '', name)
    # Replace any remaining punctuation with a standard space
    name = re.sub(r'[^\w\s]', ' ', name)
    
    # Strip any trailing or leading whitespace and return the core title
    return name.strip()

def format_clean_name(text):
    """Converts a string to Title_Case_With_Underscores."""
    # Convert the string to Title Case
    text = text.title()
    # Strip out any remaining non-alphanumeric characters except spaces
    text = re.sub(r'[^\w\s]', '', text)
    # Replace all spaces (single or consecutive) with a single underscore
    text = re.sub(r'\s+', '_', text)
    
    # Return the newly formatted text
    return text

def main():
    """Main execution function."""
    # Attempt to read the artist and album from the dummy text file
    artist, album = get_album_info_from_file()
    
    # Check if the file was found and read successfully
    if not artist or not album:
        # Print an error if the file is missing or malformed
        print("Error: Could not find a text file for instructions.")
        # Explain how the file should be formatted
        print("Please create an empty text file named like: 'Artist_Name__Album_Name.txt'")
        # Exit the program
        return

    # Attempt to fetch the official tracklist from iTunes using the parsed info
    tracklist = fetch_itunes_tracklist(artist, album)
    # If the tracklist failed to download, stop the script
    if not tracklist:
        return

    # Create a list of all files in the current folder ending in .mp3
    files = [f for f in os.listdir('.') if f.lower().endswith('.mp3')]
    
    # Check if the list of mp3 files is completely empty
    if not files:
        # Inform the user there is nothing to do
        print("No .mp3 files found in the current directory.")
        # Exit the program
        return

    # Print a header indicating the start of the process
    print("--- RENAMING PREVIEW ---\n")
    
    # Format the artist name cleanly with underscores for the final filename
    prefix_artist = format_clean_name(artist)
    # Format the album name cleanly with underscores for the final filename
    prefix_album = format_clean_name(album)

    # Loop through every mp3 file in the directory
    for filename in files:
        # Extract just the core song title from the messy filename
        isolated_title = isolate_song_title(filename, artist)
        
        # Use fuzzy logic to find the closest match in the official iTunes tracklist
        # cutoff=0.4 means the title only needs to be a 40% match to be accepted
        best_match = difflib.get_close_matches(isolated_title, tracklist.keys(), n=1, cutoff=0.4)
        
        # Check if a match was successfully found
        if best_match:
            # Extract the actual string of the best matching official title
            official_title = best_match[0]
            # Retrieve the track number associated with that title from our dictionary
            track_num = tracklist[official_title]
            # Format the official title cleanly with underscores
            clean_song_name = format_clean_name(official_title)
            
            # Construct the final, pristine filename string
            new_name = f"{prefix_artist}_{prefix_album}_{track_num}_{clean_song_name}.mp3"
            
        # Execute this block if the script couldn't match the song to the album
        else:
            # Warn the user that a song failed to match
            print(f"Warning: Could not match '{filename}' to the album tracklist.")
            # Format the messy, unmatched title as best as possible
            clean_unmatched = format_clean_name(isolated_title)
            # Construct a fallback filename using track number '00'
            new_name = f"{prefix_artist}_{prefix_album}_00_{clean_unmatched}.mp3"
            
        # Check if the newly constructed name is different from the original name
        if filename != new_name:
            # Print the original name
            print(f"Old: {filename}")
            # Print the new name
            print(f"New: {new_name}\n")
            
            # Check if DRY_RUN is turned off
            if not DRY_RUN:
                # Actually execute the system rename command
                os.rename(filename, new_name)

    # Check if the script was just running a simulation
    if DRY_RUN:
        # Print the end of the simulation block
        print("---\nThis was a DRY RUN. No files were changed.")
        # Remind the user how to activate the actual renaming
        print("Change `DRY_RUN = False` in the script when you are ready.")
    # Execute this block if the script actually renamed the files
    else:
        # Print a success message
        print("---\nFiles successfully renamed!")

# Python idiom ensuring the main function only runs if the script is executed directly
if __name__ == '__main__':
    # Call the main function
    main()
