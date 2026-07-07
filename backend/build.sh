#!/bin/bash
# Build script for Render

set -e  # Exit on any error

echo "Starting build process..."
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"

# Upgrade pip and setuptools first
echo "Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

# Install packages one by one to identify issues
echo "Installing Flask and basic dependencies..."
pip install Flask==2.3.3
pip install Flask-CORS==4.0.0
pip install python-dotenv==1.0.0
pip install requests>=2.31.0
pip install gunicorn>=21.2.0

echo "Installing financial libraries..."
pip install yfinance>=0.2.28

echo "Installing scientific computing libraries..."
pip install "numpy>=1.26.0"
pip install "pandas>=2.1.0"
pip install "scikit-learn>=1.3.0"

# Try to install TA-Lib using multiple approaches
echo "Installing TA-Lib..."

# Method 1: Try TA-Lib-binary (pre-compiled wheel)
if pip install TA-Lib-binary==0.4.28; then
    echo "✅ TA-Lib-binary installed successfully"
elif pip install TA-Lib-binary; then
    echo "✅ TA-Lib-binary (latest) installed successfully"
# Method 2: Try from conda-forge wheel repository
elif pip install --index-url https://pypi.anaconda.org/conda-forge/simple/ TA-Lib; then
    echo "✅ TA-Lib from conda-forge installed successfully"
# Method 3: Try from alternative wheel source
elif pip install https://github.com/TA-Lib/ta-lib-python/archive/refs/heads/master.zip; then
    echo "✅ TA-Lib from GitHub installed successfully"
# Method 4: Last resort - standard TA-Lib (might fail without C libraries)
elif pip install TA-Lib; then
    echo "✅ TA-Lib standard package installed successfully"
else
    echo "❌ All TA-Lib installation methods failed"
    echo "ℹ️  The app will use pandas-based indicators instead"
fi

# Verify installations
echo "Verifying key installations..."
python -c "import flask; print(f'Flask: {flask.__version__}')"
python -c "import numpy; print(f'NumPy: {numpy.__version__}')"
python -c "import pandas; print(f'Pandas: {pandas.__version__}')"
python -c "import sklearn; print(f'Scikit-learn: {sklearn.__version__}')"

echo "Build completed successfully!"
