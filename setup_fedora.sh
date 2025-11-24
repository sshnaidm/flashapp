#!/bin/bash

# Exit on error
set -e

echo "Setting up Android development environment on Fedora..."

# Install system packages
echo "Installing system packages..."
sudo dnf install -y \
    python3-pip \
    python3-devel \
    gcc \
    git \
    java-17-openjdk-devel \
    android-tools \
    zlib-devel \
    SDL2-devel \
    SDL2_image-devel \
    SDL2_mixer-devel \
    SDL2_ttf-devel \
    mesa-libGL-devel \
    mesa-libEGL-devel

# Install development tools group
echo "Installing development tools..."
sudo dnf groupinstall -y "Development Tools"

# Create Android SDK directory
ANDROID_SDK_ROOT="$HOME/Android/Sdk"
mkdir -p "$ANDROID_SDK_ROOT"

# Download and install Android Command-line Tools
echo "Downloading Android Command-line Tools..."
CMDLINE_TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip"
TEMP_DIR=$(mktemp -d)
wget "$CMDLINE_TOOLS_URL" -O "$TEMP_DIR/cmdline-tools.zip"
unzip -q "$TEMP_DIR/cmdline-tools.zip" -d "$TEMP_DIR"
mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools"
mv "$TEMP_DIR/cmdline-tools" "$ANDROID_SDK_ROOT/cmdline-tools/latest"
rm -rf "$TEMP_DIR"

# Add Android SDK to PATH
echo "Updating PATH..."
BASHRC="$HOME/.bashrc"
echo 'export ANDROID_SDK_ROOT=$HOME/Android/Sdk' >> "$BASHRC"
echo 'export PATH=$PATH:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin' >> "$BASHRC"
echo 'export PATH=$PATH:$ANDROID_SDK_ROOT/platform-tools' >> "$BASHRC"

# Source the updated bashrc
source "$BASHRC"

# Install Android SDK packages
echo "Installing Android SDK packages..."
yes | sdkmanager --licenses
sdkmanager "platforms;android-35" "build-tools;35.0.0" "platform-tools"

# Install Python packages from requirements file
echo "Installing Python packages..."
pip install --user -r build-requirements.txt

echo "Setup complete! Please restart your terminal or run:"
echo "source ~/.bashrc"