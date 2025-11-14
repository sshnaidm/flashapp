#!/bin/bash

set -e

CONTAINER_RUNTIME="podman"
IMAGE_NAME="flashapp-builder"
CONTAINER_NAME="flashapp-build"

# Directories for caching
CACHE_DIR="$(pwd)/.buildozer-cache"
GRADLE_CACHE_DIR="$(pwd)/.gradle-cache"

# Check if podman or docker is available
if ! command -v podman &> /dev/null; then
    if command -v docker &> /dev/null; then
        CONTAINER_RUNTIME="docker"
    else
        echo "Neither podman nor docker found. Please install one of them."
        exit 1
    fi
fi

echo "Using container runtime: $CONTAINER_RUNTIME"

# Create cache directories if they don't exist
mkdir -p "$CACHE_DIR"
mkdir -p "$GRADLE_CACHE_DIR"

# Clean bin directory to ensure no old APKs remain if build fails
echo "Cleaning bin directory..."
rm -rf "$(pwd)/bin/*apk"
mkdir -p "$(pwd)/bin"

echo "Cache directories:"
echo "  Buildozer cache: $CACHE_DIR"
echo "  Gradle cache: $GRADLE_CACHE_DIR"

# Build the Docker image
echo "Building container image..."
$CONTAINER_RUNTIME build -t $IMAGE_NAME .

# Clean up any existing container
$CONTAINER_RUNTIME rm -f $CONTAINER_NAME 2>/dev/null || true

# Prepare build command based on container runtime
if [ "$CONTAINER_RUNTIME" = "podman" ]; then
    # Podman: use --userns=keep-id to maintain user permissions
    USER_ARGS="--userns=keep-id"
else
    # Docker: run as current user
    USER_ARGS="--user $(id -u):$(id -g)"
fi

# Run buildozer inside container
echo "Running buildozer inside container..."
$CONTAINER_RUNTIME run --name $CONTAINER_NAME \
    $USER_ARGS \
    -v "$(pwd):/src:z" \
    -v "$CACHE_DIR:/home/builduser/.buildozer:z" \
    -v "$GRADLE_CACHE_DIR:/home/builduser/.gradle:z" \
    -w /home/builduser/build \
    -e ANDROID_HOME=/opt/android-sdk \
    -e ANDROID_SDK_ROOT=/opt/android-sdk \
    -e ANDROID_NDK_HOME=/opt/android-ndk-r25b \
    $IMAGE_NAME \
    bash -c '
        # Copy all source files to build directory, excluding build artifacts
        echo "Copying source files..."
        cp -a /src/. .

        # Remove build artifacts and cache directories that should not be copied
        rm -rf .buildozer .buildozer-cache .gradle-cache bin

        # Create fresh bin directory for build output
        mkdir -p bin

        # Run buildozer
        echo "Starting buildozer build..."
        buildozer android debug

        # Copy APK to mounted source directory
        echo "Copying APK to output directory..."
        cp -v bin/*.apk /src/bin/

        # List the result
        echo "Build artifacts:"
        ls -lh /src/bin/*.apk
    '

# Check if APK was created
if [ -d "bin" ] && ls bin/*.apk 1> /dev/null 2>&1; then
    echo ""
    echo "================================"
    echo "Build successful!"
    echo "APK location:"
    ls -lh bin/*.apk
    echo "================================"
    echo ""
    echo "Cache information:"
    echo "  Buildozer cache size: $(du -sh $CACHE_DIR 2>/dev/null | cut -f1)"
    echo "  Gradle cache size: $(du -sh $GRADLE_CACHE_DIR 2>/dev/null | cut -f1)"
    echo ""
    echo "Next builds will be faster thanks to cached dependencies!"
else
    echo ""
    echo "Build failed or APK not found"
    # Don't exit, allow inspection of logs
    echo "Container kept for debugging. Remove with: $CONTAINER_RUNTIME rm $CONTAINER_NAME"
    exit 1
fi

# Clean up container
$CONTAINER_RUNTIME rm -f $CONTAINER_NAME
