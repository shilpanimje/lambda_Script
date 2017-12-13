FROM python:3.6

RUN useradd -s /bin/bash -m -d /home/jenkins jenkins

RUN apt-get update && apt-get -y install zip

RUN pip install virtualenv

COPY build.sh /home/jenkins/build.sh
