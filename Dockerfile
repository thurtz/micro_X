# Use Debian Trixie (current testing) for more modern packages and Python 3.13
FROM debian:trixie-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8
ENV COLORTERM=truecolor

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.13 \
    python3.13-venv \
    python3-pip \
    git \
    tmux \
    lynx \
    curl \
    ca-certificates \
    gnupg \
    build-essential \
    util-linux \
    locales \
    && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.13 /usr/bin/python3 && ln -sf /usr/bin/python3.13 /usr/bin/python

# In development/breakout mode, we will mount the host directory.
# We pre-install requirements into a global-ish venv within the image
# so that the shell is ready even without a local .venv.
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/micro_x_venv
ENV PATH="/opt/micro_x_venv/bin:$PATH"
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# The ENTRYPOINT will execute the mounted micro_X.sh
ENTRYPOINT ["./micro_X.sh"]
