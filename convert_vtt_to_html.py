#!/usr/bin/env python3
"""
Convert WebVTT transcript to HTML format for the podcast episode page.
"""

import re
from pathlib import Path


def parse_vtt_timestamp(timestamp):
    """Convert VTT timestamp (HH:MM:SS.mmm) to [MM:SS] format."""
    # Extract just the time part before the arrow
    time_match = re.match(r'(\d{2}):(\d{2}):(\d{2})', timestamp)
    if time_match:
        hours, minutes, seconds = time_match.groups()
        # Convert to [MM:SS] or [HH:MM:SS] if hours > 0
        if hours == '00':
            return f"[{minutes}:{seconds}]"
        else:
            return f"[{hours}:{minutes}:{seconds}]"
    return "[00:00]"


def parse_vtt_file(vtt_path):
    """Parse VTT file and return list of transcript entries."""
    entries = []
    current_timestamp = None
    current_text = []

    with open(vtt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Check if this is a timestamp line
        if '-->' in line:
            # If we have accumulated text, save the previous entry
            if current_timestamp and current_text:
                entries.append({
                    'timestamp': current_timestamp,
                    'text': ' '.join(current_text)
                })
                current_text = []

            # Extract the start timestamp
            current_timestamp = parse_vtt_timestamp(line.split('-->')[0].strip())

        # Check if this is text content (not empty, not WEBVTT header, not timestamp)
        elif line and line != 'WEBVTT' and '-->' not in line:
            current_text.append(line)

        i += 1

    # Don't forget the last entry
    if current_timestamp and current_text:
        entries.append({
            'timestamp': current_timestamp,
            'text': ' '.join(current_text)
        })

    return entries


def group_entries_by_time(entries, seconds_per_group=30):
    """Group transcript entries to avoid too many small segments."""
    if not entries:
        return []

    grouped = []
    current_group = {
        'timestamp': entries[0]['timestamp'],
        'text': []
    }

    for entry in entries:
        current_group['text'].append(entry['text'])

        # Every few entries, create a new group
        if len(current_group['text']) >= 5:  # Group every ~5 segments
            grouped.append({
                'timestamp': current_group['timestamp'],
                'text': ' '.join(current_group['text'])
            })
            # Start new group
            if entry != entries[-1]:
                current_group = {
                    'timestamp': entry['timestamp'],
                    'text': []
                }

    # Add remaining text
    if current_group['text']:
        grouped.append({
            'timestamp': current_group['timestamp'],
            'text': ' '.join(current_group['text'])
        })

    return grouped


def generate_html_transcript(entries):
    """Generate HTML transcript from entries."""
    html_parts = []

    for entry in entries:
        timestamp = entry['timestamp']
        text = entry['text']

        # Escape HTML special characters
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        html = f'''                    <div class="transcript-entry">
                        <div class="transcript-timestamp">{timestamp}</div>
                        <p class="transcript-text">{text}</p>
                    </div>
'''
        html_parts.append(html)

    return '\n'.join(html_parts)


def main():
    # Paths
    vtt_path = Path('data/transcripts/release-managers.vtt')
    output_path = Path('data/transcripts/release-managers-transcript.html')

    print(f"Reading VTT file: {vtt_path}")
    entries = parse_vtt_file(vtt_path)
    print(f"Found {len(entries)} transcript entries")

    # Group entries to make it more readable
    print("Grouping entries...")
    grouped = group_entries_by_time(entries)
    print(f"Grouped into {len(grouped)} segments")

    # Generate HTML
    print("Generating HTML...")
    html = generate_html_transcript(grouped)

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✓ Transcript HTML written to: {output_path}")
    print(f"\nYou can now copy the contents of this file into the episode page")
    print(f"between the <div class=\"transcript-content\"> tags.")


if __name__ == '__main__':
    main()
