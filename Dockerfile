FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
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
RUN pip3 install --upgrade pip
RUN pip3 install buildozer==1.5.0 cython==3.0.12

# Install Android SDK
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
RUN mkdir -p ${ANDROID_HOME}/cmdline-tools && \
    cd ${ANDROID_HOME}/cmdline-tools && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip && \
    unzip commandlinetools-linux-9477386_latest.zip && \
    mv cmdline-tools latest && \
    rm commandlinetools-linux-9477386_latest.zip

ENV PATH=${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:$PATH

# Accept licenses and install SDK packages
RUN yes | sdkmanager --licenses || true
RUN sdkmanager "platform-tools" "platforms;android-33" "build-tools;33.0.0"

# Install Android NDK
RUN cd /opt && \
    wget -q https://dl.google.com/android/repository/android-ndk-r25b-linux.zip && \
    unzip -q android-ndk-r25b-linux.zip && \
    rm android-ndk-r25b-linux.zip

ENV ANDROID_NDK_HOME=/opt/android-ndk-r25b

# Create a non-root user
RUN useradd -m -u 1000 builduser && \
    chown -R builduser:builduser /opt/android-sdk /opt/android-ndk-r25b && \
    mkdir -p /home/builduser/build && \
    chown -R builduser:builduser /home/builduser/build

USER builduser
WORKDIR /home/builduser/build

CMD ["/bin/bash"]
