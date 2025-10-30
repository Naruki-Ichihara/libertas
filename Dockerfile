FROM ichiharanaruki/pytop:latest

# Build argument to control Claude Code installation
ARG INSTALL_CLAUDE=true
ARG INSTALL_FENICS=false

RUN apt update
RUN apt upgrade -y
RUN apt -y install libglu1 libxcursor-dev libxft2 libxinerama1 libfltk1.3-dev libfreetype6-dev libgl1-mesa-dev libocct-foundation-dev libocct-data-exchange-dev
RUN pip install --upgrade pip
RUN pip install git+https://github.com/Naruki-Ichihara/pytop.git@main

# Install Node.js and Claude Code (if enabled)
RUN if [ "$INSTALL_CLAUDE" = "true" ]; then \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt install -y nodejs && \
    npm install -g @anthropic-ai/claude-code; \
    fi

# Install FENICS
RUN if [ "$INSTALL_FENICS" = "true" ]; then \
    apt install -y software-properties-common && \
    add-apt-repository ppa:fenics-packages/fenics -y && \
    apt updata && \
    apt install -y fenics \
    fi

WORKDIR /home/
CMD ["/bin/bash"]
