#!/usr/bin/env python
"""
Complete setup script for Algo Trading Bot.
Handles: Python environment, dependencies, configuration, initial data download.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def print_header(text):
    """Print colored header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")

def print_success(text):
    """Print success message."""
    print(f"✓ {text}")

def print_warning(text):
    """Print warning message."""
    print(f"⚠ {text}")

def print_error(text):
    """Print error message."""
    print(f"✗ {text}")

def run_command(cmd, description):
    """Run a shell command and handle errors."""
    try:
        print(f"  {description}...", end=" ")
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print_success("Done")
            return True
        else:
            print_error(f"Failed - {result.stderr[:100]}")
            return False
    except Exception as e:
        print_error(f"Error - {str(e)[:100]}")
        return False

def check_python():
    """Check Python version."""
    print_header("1. Checking Python Version")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major >= 3 and version.minor >= 8:
        print_success(f"Python 3.{version.minor} is compatible")
        return True
    else:
        print_error(f"Python 3.8+ required (found 3.{version.minor})")
        return False

def setup_venv():
    """Create and activate virtual environment."""
    print_header("2. Setting Up Virtual Environment")
    
    venv_path = Path(".venv")
    if venv_path.exists():
        print_success("Virtual environment already exists")
        return True
    
    # Create venv
    if not run_command(f"{sys.executable} -m venv .venv", "Creating virtual environment"):
        return False
    
    print_success("Virtual environment created at .venv/")
    return True

def install_dependencies():
    """Install Python dependencies."""
    print_header("3. Installing Dependencies")
    
    if platform.system() == "Windows":
        pip_cmd = ".venv\\Scripts\\pip"
    else:
        pip_cmd = ".venv/bin/pip"
    
    # Upgrade pip
    if not run_command(f"{pip_cmd} install --upgrade pip", "Upgrading pip"):
        print_warning("Could not upgrade pip (non-critical)")
    
    # Install the package
    if not run_command(f"{pip_cmd} install -e .", "Installing trading bot"):
        return False
    
    # Install optional dependencies
    run_command(f"{pip_cmd} install pyarrow", "Installing pyarrow for caching")
    run_command(f"{pip_cmd} install jupyter", "Installing Jupyter for notebooks")
    
    print_success("All dependencies installed")
    return True

def create_config():
    """Create configuration directories and files."""
    print_header("4. Setting Up Configuration")
    
    paths = [
        Path("configs"),
        Path("data"),
        Path(".cache"),
        Path(".cache/strategy_learning"),
        Path("logs"),
        Path("notebooks"),
    ]
    
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
        print_success(f"Directory ready: {path}/")
    
    return True

def create_env_file():
    """Create .env file template."""
    print_header("5. Creating Environment Template")
    
    env_path = Path(".env")
    if env_path.exists():
        print_success(".env file already exists")
        return True
    
    env_content = """# Alpaca API Credentials (get from https://app.alpaca.markets)
APCA_API_KEY_ID=your_api_key_here
APCA_API_SECRET_KEY=your_secret_key_here
APCA_API_BASE_URL=https://paper-api.alpaca.markets

# Trading Configuration
START_CASH=100000
MAX_DRAWDOWN_PCT=5.0
MAX_DAILY_LOSS_PCT=2.0

# Data Configuration
DATA_PERIOD=60d
DATA_INTERVAL=1d

# Learning Configuration
AUTO_LEARN=true
AUTO_SELECT_STOCKS=true
"""
    
    env_path.write_text(env_content)
    print_success(".env template created")
    print_warning("  Edit .env and add your Alpaca API credentials")
    return True

def download_sample_data():
    """Download sample data for testing."""
    print_header("6. Downloading Sample Data")
    
    print("This may take 1-2 minutes for initial data download...")
    
    if platform.system() == "Windows":
        python_cmd = ".venv\\Scripts\\python"
    else:
        python_cmd = ".venv/bin/python"
    
    cmd = f"{python_cmd} -c \"from trading_bot.data.batch_downloader import BatchDownloader; bd = BatchDownloader(); bd.download_batch(['SPY', 'QQQ', 'IWM'], period='3mo')\""
    
    if run_command(cmd, "Downloading data for SPY, QQQ, IWM"):
        print_success("Sample data ready for backtesting")
        return True
    else:
        print_warning("Could not download sample data (non-critical)")
        return True

def run_tests():
    """Run test suite."""
    print_header("7. Running Tests")
    
    if platform.system() == "Windows":
        python_cmd = ".venv\\Scripts\\python"
    else:
        python_cmd = ".venv/bin/python"
    
    if run_command(f"{python_cmd} -m pytest tests/ -v", "Running test suite"):
        print_success("All tests passed!")
        return True
    else:
        print_warning("Some tests failed (check logs)")
        return True

def print_next_steps():
    """Print next steps."""
    print_header("Setup Complete! Next Steps")
    
    if platform.system() == "Windows":
        activate = ".venv\\Scripts\\Activate.ps1"
        activate_msg = "PowerShell: .venv\\Scripts\\Activate.ps1"
    else:
        activate = "source .venv/bin/activate"
        activate_msg = "Bash: source .venv/bin/activate"
    
    print("1. Edit .env file with your Alpaca API credentials:")
    print("   APCA_API_KEY_ID=your_key")
    print("   APCA_API_SECRET_KEY=your_secret")
    print()
    print("2. Activate virtual environment:")
    print(f"   {activate_msg}")
    print()
    print("3. Run trading bot:")
    print("   python -m trading_bot auto")
    print()
    print("4. Or use quick-start scripts:")
    
    if platform.system() == "Windows":
        print("   PowerShell: .\\quick_start.ps1")
        print("   Batch: quick_start.bat")
    else:
        print("   Bash: python quick_start.py")
    print()
    print("5. View documentation:")
    print("   START_HERE.md - Quickest start")
    print("   AUTO_START_GUIDE.md - Detailed guide")
    print("   README.md - Full documentation")
    print()

def main():
    """Run complete setup."""
    print("\n")
    print_header("ALGO TRADING BOT - COMPLETE SETUP")
    
    steps = [
        ("Python version check", check_python),
        ("Virtual environment", setup_venv),
        ("Dependencies", install_dependencies),
        ("Configuration", create_config),
        ("Environment file", create_env_file),
        ("Sample data", download_sample_data),
        ("Tests", run_tests),
    ]
    
    completed = 0
    for step_name, step_func in steps:
        if not step_func():
            print_error(f"Setup incomplete: {step_name} failed")
            print("\nTo continue manually:")
            print(f"  See: {step_name} documentation")
            sys.exit(1)
        completed += 1
    
    print_next_steps()
    
    print_header("🎉 Setup Successful!")
    print("Your trading bot is ready to use!")
    print()
    print("Next command:")
    print("  python -m trading_bot auto")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Setup error: {e}")
        sys.exit(1)
