FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# Install dependencies for mise and common tools
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    curl \
    git \
    sudo \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    llvm \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    librdkafka-dev \
    apt-transport-https \
    ca-certificates \
    gnupg

# Install Google Cloud CLI (Stable Method)
RUN curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    apt-get update && apt-get install -y google-cloud-cli

# Set up the vscode user
USER vscode
WORKDIR /home/vscode

# Install mise as the vscode user
RUN curl https://mise.jdx.dev/install.sh | sh

# Add mise to the path for the vscode user
ENV PATH="/home/vscode/.local/share/mise/shims:$PATH"

# Set up shell activation (using absolute paths for reliability)
RUN echo 'eval "$(/home/vscode/.local/bin/mise activate bash)"' >> ~/.bashrc
RUN echo 'eval "$(/home/vscode/.local/bin/mise activate zsh)"' >> ~/.zshrc



WORKDIR /workspaces/BrandGuard


