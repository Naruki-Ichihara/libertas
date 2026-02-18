FROM ichiharanaruki/pytop:latest


RUN apt update
RUN apt upgrade -y
RUN apt -y install libglu1 libxcursor-dev libxft2 libxinerama1 libfltk1.3-dev libfreetype6-dev libgl1-mesa-dev libocct-foundation-dev libocct-data-exchange-dev
RUN pip install --upgrade pip

# Clone libertas with submodules (pytop, fullcontrol) and install all
RUN git clone --recurse-submodules https://github.com/Naruki-Ichihara/libertas.git /tmp/libertas && \
    pip install /tmp/libertas/libertas/pytop && \
    pip install /tmp/libertas/libertas/fullcontrol && \
    pip install /tmp/libertas/

WORKDIR /home/
CMD ["/bin/bash"]
