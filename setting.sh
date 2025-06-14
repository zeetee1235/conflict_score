#!/bin/bash
# Run crawling.py and wait for it to finish
python3 crawling.py
if [ $? -eq 0 ]; then
    echo "Crawling completed successfully. Starting main.py..."
    python3 main.py
else
    echo "Crawling failed. Exiting."
    exit 1
fi
