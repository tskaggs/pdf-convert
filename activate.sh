#!/bin/bash
# Activation script for the PDF converter virtual environment

source .venv/bin/activate
echo "Virtual environment activated!"
echo "Python version: $(python --version)"
echo ""
echo "To start the server, run:"
echo "  python main.py"
echo ""
echo "Or:"
echo "  uvicorn main:app --host 0.0.0.0 --port 8000"
echo ""
echo "To deactivate, run:"
echo "  deactivate"

