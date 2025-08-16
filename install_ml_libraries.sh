#!/bin/bash

# ===============================================
# ML LIBRARIES INSTALLATION SCRIPT
# Install required ML libraries on remote server
# ===============================================

set -e

echo "🤖 Installing ML Libraries for GPW Trading Advisor"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if library is installed
check_library() {
    local lib_name=$1
    if python3 -c "import $lib_name" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Check Python version
print_status "Checking Python version..."
PYTHON_VERSION=$(python3 --version)
print_status "Found: $PYTHON_VERSION"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    print_status "Activating virtual environment..."
    source venv/bin/activate
    print_success "Virtual environment activated"
elif [ -d "/opt/gpw-trading-advisor/venv" ]; then
    print_status "Activating virtual environment..."
    source /opt/gpw-trading-advisor/venv/bin/activate
    print_success "Virtual environment activated"
else
    print_warning "No virtual environment found, using system Python"
fi

# Update pip first
print_status "Updating pip..."
python3 -m pip install --upgrade pip

# Install core ML libraries
print_status "Installing PyTorch..."
if check_library "torch"; then
    print_success "PyTorch already installed"
else
    # Install CPU version of PyTorch (lighter for servers)
    python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    print_success "PyTorch installed successfully"
fi

print_status "Installing scikit-learn..."
if check_library "sklearn"; then
    print_success "scikit-learn already installed"
else
    python3 -m pip install scikit-learn
    print_success "scikit-learn installed successfully"
fi

print_status "Installing pandas and numpy..."
if check_library "pandas" && check_library "numpy"; then
    print_success "pandas and numpy already installed"
else
    python3 -m pip install pandas numpy
    print_success "pandas and numpy installed successfully"
fi

print_status "Installing matplotlib and seaborn..."
if check_library "matplotlib" && check_library "seaborn"; then
    print_success "matplotlib and seaborn already installed"
else
    python3 -m pip install matplotlib seaborn
    print_success "matplotlib and seaborn installed successfully"
fi

print_status "Installing additional ML libraries..."
python3 -m pip install xgboost ta joblib

print_success "All ML libraries installed successfully!"

# Test imports
print_status "Testing library imports..."

python3 << 'EOF'
try:
    import torch
    import sklearn
    import pandas
    import numpy
    import matplotlib
    import seaborn
    import xgboost
    import ta
    import joblib
    
    print("✅ All libraries imported successfully!")
    print(f"PyTorch version: {torch.__version__}")
    print(f"scikit-learn version: {sklearn.__version__}")
    print(f"pandas version: {pandas.__version__}")
    print(f"numpy version: {numpy.__version__}")
    
except Exception as e:
    print(f"❌ Import error: {e}")
    exit(1)
EOF

if [ $? -eq 0 ]; then
    print_success "Library verification completed successfully!"
else
    print_error "Library verification failed!"
    exit 1
fi

# Create a test script to verify ML functionality
cat > test_ml_functionality.py << 'EOF'
#!/usr/bin/env python3
"""Test ML functionality after installation"""

def test_ml_libraries():
    """Test all ML libraries are working correctly."""
    
    print("🧪 Testing ML Library Functionality")
    print("=" * 50)
    
    # Test PyTorch
    try:
        import torch
        x = torch.randn(5, 3)
        y = torch.randn(5, 3)
        z = x + y
        print("✅ PyTorch: Basic tensor operations working")
    except Exception as e:
        print(f"❌ PyTorch error: {e}")
        return False
    
    # Test scikit-learn
    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.datasets import make_regression
        X, y = make_regression(n_samples=100, n_features=1, noise=0.1)
        model = LinearRegression()
        model.fit(X, y)
        score = model.score(X, y)
        print(f"✅ scikit-learn: Linear regression R² = {score:.3f}")
    except Exception as e:
        print(f"❌ scikit-learn error: {e}")
        return False
    
    # Test pandas
    try:
        import pandas as pd
        import numpy as np
        df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        result = df.mean()
        print("✅ pandas: DataFrame operations working")
    except Exception as e:
        print(f"❌ pandas error: {e}")
        return False
    
    # Test matplotlib (basic)
    try:
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 4, 2])
        plt.close(fig)
        print("✅ matplotlib: Plot generation working")
    except Exception as e:
        print(f"❌ matplotlib error: {e}")
        return False
    
    # Test TA (Technical Analysis)
    try:
        import ta
        import pandas as pd
        df = pd.DataFrame({
            'high': [10, 11, 12, 11, 10],
            'low': [8, 9, 10, 9, 8],
            'close': [9, 10, 11, 10, 9]
        })
        rsi = ta.momentum.RSIIndicator(df['close']).rsi()
        print("✅ TA-Lib: Technical indicators working")
    except Exception as e:
        print(f"❌ TA-Lib error: {e}")
        return False
    
    print("\n🎉 All ML libraries are working correctly!")
    return True

if __name__ == "__main__":
    success = test_ml_libraries()
    exit(0 if success else 1)
EOF

chmod +x test_ml_functionality.py

print_status "Running ML functionality test..."
python3 test_ml_functionality.py

if [ $? -eq 0 ]; then
    print_success "✅ ML functionality test passed!"
else
    print_error "❌ ML functionality test failed!"
    exit 1
fi

echo ""
print_success "🎉 ML Libraries Installation Complete!"
print_status "Next steps:"
echo "1. Restart your Django application"
echo "2. Check the ML dashboard at /analysis/ml/"
echo "3. Verify that 'Funkcje ML Niedostępne' message is gone"
echo ""
print_warning "If running with Docker, you may need to rebuild the container:"
echo "docker-compose build web && docker-compose restart web"
