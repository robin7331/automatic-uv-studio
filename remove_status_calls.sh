#!/bin/bash
# Script to remove all publish_status_message calls from main.py

cd /Users/robin/Documents/Projects/automatic-uv-studio

# Remove publish_status_message calls but keep the logger calls
sed -i.bak '/publish_status_message(/d' main.py

# Clean up backup file
rm -f main.py.bak

echo "Removed all publish_status_message calls from main.py"
