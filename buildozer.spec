[app]
title = Flashcard App
package.name = flashcardapp
package.domain = org.flashcard

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
# Include all files with extensions listed above from source.dir
# Note: Commenting out include_patterns to allow all files with matching extensions
# source.include_patterns = main.py,flashcard_app.py

version = 1.0

# Remove 'android' from requirements as it's not a Python package
# IMPORTANT: DO NOT list 'kivy' in requirements!
# When kivy is listed here, pip installs x86_64 wheels from PyPI BEFORE
# python-for-android can build it from source, causing architecture mismatch errors.
# The SDL2 bootstrap automatically includes Kivy and builds it correctly for ARM.
# See: ANDROID_FIX_SUMMARY.md and ARCHITECTURE_FIX.md for details
requirements = python3,kivy,docutils,pygments,pillow

# Android specific
# READ_EXTERNAL_STORAGE: Required for file import functionality
# Note: On Android 11+ (API 30+), this permission has limited effect due to scoped storage.
# File browsing may be restricted. For full file access on Android 11+, consider:
# 1. Using Android's file picker Intent (Storage Access Framework)
# 2. Requesting MANAGE_EXTERNAL_STORAGE (only for file manager apps)
# 3. Limiting imports to app-specific directories or Downloads folder
android.permissions = READ_EXTERNAL_STORAGE
android.api = 35
android.minapi = 21
android.ndk = 25b
android.sdk = 35
android.presplash.filename = %(source.dir)s/presplash.png
android.icon.filename = %(source.dir)s/icon.png
android.accept_sdk_license = True
android.gradle_dependencies = androidx.core:core:1.7.0, androidx.appcompat:appcompat:1.5.1, com.google.android.material:material:1.8.0
android.enable_androidx = True

# Explicitly set SDL2 bootstrap for better graphics stability
p4a.bootstrap = sdl2

# (bool) If True, then skip trying to update the Android sdk
# This can be useful to avoid excess Internet downloads or save time
# when an update is due and you just want to test/build your package
android.skip_update = False

# (str) Android logcat filters to use
# Changed to *:D for full debugging output to diagnose crashes
android.logcat_filters = *:D

# (bool) Copy library instead of making a libpymodules.so
android.copy_libs = 1

# (str) The Android arch to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
# Building for both 32-bit and 64-bit ARM to support all devices and comply with Play Store requirements
android.archs = arm64-v8a, armeabi-v7a

# Target API 35 (Android 15) - REQUIRED for Play Store as of August 31, 2025

# (int) overrides automatic versionCode computation (used in build.gradle)
# this is not the same as app version and should only be edited if you know what you're doing
# android.numeric_version = 1

[buildozer]
# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

# (str) Path to build artifact storage, absolute or relative to spec file
# Use absolute path to match the container mount point for caching
build_dir = /home/builduser/.buildozer

# (str) Path to build output (i.e. .apk, .aab, .ipa) storage
bin_dir = ./bin
