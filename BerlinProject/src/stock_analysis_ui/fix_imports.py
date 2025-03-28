import os
import sys


def setup_imports():
    """
    Add the necessary paths to Python's import system
    so it can find the required modules
    """
    # Get the current directory (should be stock_analysis_ui)
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Go up to the src directory that contains both stock_analysis_ui and data_streamer
    src_dir = os.path.abspath(os.path.join(current_dir, '..'))

    # Add the src directory to Python's import path
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
        print(f"Added {src_dir} to Python path")

    # Also add the parent of src to the path
    parent_dir = os.path.abspath(os.path.join(src_dir, '..'))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        print(f"Added {parent_dir} to Python path")

    return True