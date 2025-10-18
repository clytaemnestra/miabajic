#!/usr/bin/env python3
"""
Update the episode page with the full transcript.
"""

from pathlib import Path
import re

# Read the transcript HTML
transcript_path = Path('data/transcripts/release-managers-transcript.html')
with open(transcript_path, 'r', encoding='utf-8') as f:
    transcript_html = f.read()

# Read the episode page
episode_path = Path('episodes/cpython-release-management.html')
with open(episode_path, 'r', encoding='utf-8') as f:
    episode_content = f.read()

# Find and replace the transcript content section
# We want to replace everything between <div class="transcript-content"> and </div>
pattern = r'(<div class="transcript-content">).*?(</div>\s*</details>)'
replacement = r'\1\n' + transcript_html + r'\n                \2'

updated_content = re.sub(pattern, replacement, episode_content, flags=re.DOTALL)

# Write back to the episode file
with open(episode_path, 'w', encoding='utf-8') as f:
    f.write(updated_content)

print(f"✓ Episode page updated with full transcript")
print(f"  Transcript entries: {transcript_html.count('transcript-entry')}")
print(f"  File: {episode_path}")
