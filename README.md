# Simplest Flashcard app

This is a simple flashcard app built with Python and Kivy. It allows you to create and study flashcards.

## Building for Android

### Quick Start

To build the Android APK:

```bash
./build_container.sh
```

The APK will be created in the `bin/` directory.

### How it Works

The build script uses Docker/Podman to create a containerized build environment with:
- Java 17 (required for Android Gradle plugin)
- Android SDK API 33
- Android NDK r25b
- Python 3 and buildozer

### Caching

The build system uses persistent caches to speed up subsequent builds:
- `.buildozer-cache/` - Contains downloaded Android SDK, NDK, and compiled Python recipes
- `.gradle-cache/` - Contains Gradle build cache

**First build:** ~15-30 minutes (downloads and compiles everything)
**Subsequent builds:** ~2-5 minutes (uses cached dependencies)

### Cleaning Cache

If you encounter build issues, you can clean the caches:

```bash
rm -rf .buildozer-cache .gradle-cache
```

Then run the build again.

### Requirements

- Docker or Podman installed
- At least 10GB of free disk space
- Internet connection for first build
