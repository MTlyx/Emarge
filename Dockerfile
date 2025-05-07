FROM ubuntu:22.04 AS emargement

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y \
      curl \
      gnupg \
      jq \
      less \
      python3-pip \
      tree \
      unzip \
      vim \
      wget \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list && \
    apt-get -y update && \
    apt-get -y install google-chrome-stable 

RUN CHROME_VERSION="$( google-chrome --product-version )" && \
    wget -q --continue -P /tmp/ "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" && \
    unzip -q /tmp/chromedriver*.zip -d /usr/local/bin && \
    rm /tmp/chromedriver*.zip

WORKDIR /app

COPY app/requirements* ./

RUN pip install --no-cache-dir -r requirements.txt -r requirements-selenium.txt

COPY app/* ./

ENV MODE=EMARGEMENT

CMD ["python3", "-u", "script.py"]



FROM python:3 AS notification

WORKDIR /app

COPY app/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY app/* ./

ENV MODE=NOTIFICATION

CMD ["python3", "-u", "script.py"]
