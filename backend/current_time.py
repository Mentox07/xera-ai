#!/usr/bin/env python3
"""
Script to print the current time every second.
"""

import datetime
import time

def print_current_time():
    """Print the current time in HH:MM:SS format."""
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    print(current_time)

def main():
    """Main function to run the time printer."""
    try:
        while True:
            print_current_time()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nScript stopped by user.")

if __name__ == "__main__":
    main()