FROM ichiharanaruki/pytop:latest


RUN apt update
RUN apt upgrade -y
RUN apt -y install libglu1 libxcursor-dev libxft2 libxinerama1 libfltk1.3-dev libfreetype6-dev libgl1-mesa-dev libocct-foundation-dev libocct-data-exchange-dev
RUN pip install --upgrade pip

RUN pip install fullcontrol git+https://github.com/Naruki-Ichihara/pytop.git && \
    pip install git+https://github.com/Naruki-Ichihara/libertas.git

WORKDIR /home/
CMD ["/bin/bash"]
