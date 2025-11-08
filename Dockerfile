FROM ubuntu:22.04

# Version variables for easy updates
ARG CMDLINE_TOOLS_VERSION=9477386_latest
ARG ANDROID_NDK_VERSION=r25b
ARG ANDROID_API_LEVEL=35
ARG ANDROID_BUILD_TOOLS_VERSION=35.0.0

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    git \
    openjdk-17-jdk \
    wget \
    unzip \
    zip \
    autoconf \
    libtool \
    pkg-config \
    zlib1g-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libtinfo5 \
    cmake \
    libffi-dev \
    libssl-dev \
    ccache \
    && rm -rf /var/lib/apt/lists/*

# Set Java 17 as default
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH=$JAVA_HOME/bin:$PATH

# Install buildozer and dependencies
RUN pip3 install --upgrade pip && \
    pip3 install buildozer==1.5.0 cython==3.0.12

# Install Android SDK
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
RUN mkdir -p ${ANDROID_HOME}/cmdline-tools && \
    cd ${ANDROID_HOME}/cmdline-tools && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS_VERSION}.zip && \
    unzip commandlinetools-linux-${CMDLINE_TOOLS_VERSION}.zip && \
    mv cmdline-tools latest && \
    rm commandlinetools-linux-${CMDLINE_TOOLS_VERSION}.zip

ENV PATH=${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:$PATH

# Accept licenses and install SDK packages
RUN yes | sdkmanager --licenses || true
RUN sdkmanager "platform-tools" "platforms;android-${ANDROID_API_LEVEL}" "build-tools;${ANDROID_BUILD_TOOLS_VERSION}"

# Install Android NDK
RUN cd /opt && \
    wget -q https://dl.google.com/android/repository/android-ndk-${ANDROID_NDK_VERSION}-linux.zip && \
    unzip -q android-ndk-${ANDROID_NDK_VERSION}-linux.zip && \
    rm android-ndk-${ANDROID_NDK_VERSION}-linux.zip

ENV ANDROID_NDK_HOME=/opt/android-ndk-${ANDROID_NDK_VERSION}

# Create a non-root user
RUN useradd -m -u 1000 builduser && \
    chown -R builduser:builduser /opt/android-sdk /opt/android-ndk-${ANDROID_NDK_VERSION} && \
    mkdir -p /home/builduser/build && \
    chown -R builduser:builduser /home/builduser/build

USER builduser
WORKDIR /home/builduser/build

CMD ["/bin/bash"]
