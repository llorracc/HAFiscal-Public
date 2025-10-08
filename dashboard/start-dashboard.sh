#!/bin/bash
# HANK-SAM Dashboard Startup Script for GitHub Codespaces

echo "🏦 Starting HANK-SAM Dashboard in GitHub Codespaces..."

# Activate conda environment
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate hafiscal-dashboard

# Verify environment
echo "📋 Checking environment..."
python -c "
import sys
sys.path.insert(0, 'dashboard')
import hank_sam as hs
import hafiscal
print('✅ All imports successful!')
"

echo ""
echo "🚀 Starting Voila dashboard..."
echo "   → Dashboard will be available on port 8866"
echo "   → Codespaces will auto-forward the port"
echo "   → Click the 'Ports' tab to access the dashboard URL"
echo ""

# Start the dashboard
voila dashboard/app.ipynb --no-browser --port=8866 --Voila.ip='0.0.0.0' --enable_nbextensions=True
