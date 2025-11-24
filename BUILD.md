# Building Flashcard App

This guide explains how to build the Flashcard App for Android using the provided containerized build system. This ensures a consistent environment and avoids "works on my machine" issues.

## Prerequisites

You need a machine with a container runtime installed:
- **Podman** (Recommended on Linux/Fedora)
- **Docker** (Works on all platforms)

No other dependencies (Python, Kivy, Android SDK/NDK) are needed on your host machine; they are all handled inside the container.

## How to Build

### 1. First Build / Clean Build
If you are building for the first time or want to ensure a completely fresh build (useful if you changed architecture settings or major dependencies):

```bash
./clean_and_rebuild.sh
```
*This script removes all cache directories (`.buildozer-cache`, `.gradle-cache`, `bin/`) before starting the build.*

### 2. Standard Build (With Cache)
For regular development, use the main build script. This leverages the persistent cache to significantly speed up the build process (reusing compiled python packages, SDK downloads, etc.):

```bash
./build_container.sh
```

**Note:** The cache is stored in your project directory in:
- `.buildozer-cache/` (Buildozer artifacts, Python distribution)
- `.gradle-cache/` (Android Gradle dependencies)

### 3. Deploy to Device
Once the build is complete, the APK will be in the `bin/` directory. To install and run it on a connected Android device:

```bash
./test_on_android.sh
```

## Troubleshooting

### Architecture Mismatch (x86_64 vs ARM64)
If the app crashes on startup with an error like `ImportError: dlopen failed: ... is for EM_X86_64`, it means a desktop version of a library was installed instead of the Android version.
**Fix:** Run `./clean_and_rebuild.sh` to clear the bad cache. Ensure `buildozer.spec` does not pin specific versions of Kivy (e.g., use `kivy` instead of `kivy==2.2.1`).

### Cache Issues
If builds are failing with mysterious errors after changing dependencies, try cleaning the cache:
```bash
./clean_and_rebuild.sh
```

