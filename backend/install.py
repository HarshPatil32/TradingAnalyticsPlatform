#!/usr/bin/env python3
"""
Install script for Render deployment
"""

import subprocess
import sys


def run_command(cmd):
    """Run a command and return the result"""
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=True, text=True
        )
        print(f"Success: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}")
        return False


def main():
    """Main installation process"""
    print("Starting Render deployment build...")

    # Upgrade pip and setuptools
    if not run_command("pip install --upgrade pip setuptools wheel"):
        sys.exit(1)

    # Install requirements without TA-Lib first
    print("Installing basic requirements...")
    if not run_command(
        "pip install Flask==2.3.3 Flask-CORS==4.0.0 python-dotenv==1.0.0"
    ):
        sys.exit(1)

    if not run_command(
        "pip install yfinance==0.2.18 requests==2.31.0 gunicorn==21.2.0"
    ):
        sys.exit(1)

    if not run_command("pip install numpy==1.24.3 pandas==2.0.3 scikit-learn==1.3.0"):
        sys.exit(1)

    # Try to install TA-Lib
    print("Installing TA-Lib...")
    talib_installed = False

    # Try different TA-Lib installations
    talib_options = ["TA-Lib-binary==0.4.28", "TA-Lib==0.4.25", "talib-binary==0.4.24"]

    for option in talib_options:
        print(f"Trying to install {option}...")
        if run_command(f"pip install {option}"):
            talib_installed = True
            print(f"Successfully installed {option}")
            break

    if not talib_installed:
        print("Warning: TA-Lib installation failed, but continuing...")

    print("Build completed!")


if __name__ == "__main__":
    main()
