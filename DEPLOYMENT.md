# ANPR System Deployment Guide

This guide will help you deploy the ANPR (Automatic Number Plate Recognition) system on your Raspberry Pi.

## Prerequisites

- Raspberry Pi 3 or 4 with Raspberry Pi OS installed
- USB webcam
- Internet connection
- Python 3.7+ installed

## Installation Steps

### 1. Set up a virtual environment

```bash
# Install required system packages
sudo apt update
sudo apt install -y tesseract-ocr libtesseract-dev python3-full python3-venv

# Create a project directory
mkdir -p ~/anpr_system
cd ~/anpr_system

# Create a virtual environment
python3 -m venv anpr_env

# Activate the virtual environment
source anpr_env/bin/activate

