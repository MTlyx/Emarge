FROM debian:latest AS emargement

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

RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /usr/share/keyrings/google-linux-signing-key.gpg

RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-key.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list

RUN apt-get update && apt-get install -y google-chrome-stable && rm -rf /var/lib/apt/lists/*

RUN CHROME_VERSION="$(google-chrome --product-version)" && \
    CHROME_MAJOR_VERSION="${CHROME_VERSION%%.*}" && \
    DRIVER_VERSION="$(curl -fsSL "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR_VERSION}")" && \
    wget -q -P /tmp/ "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" && \
    unzip -q /tmp/chromedriver-linux64.zip -d /tmp/ && \
    mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver-linux64.zip /tmp/chromedriver-linux64

WORKDIR /app

COPY app/requirements* ./

RUN pip install --no-cache-dir -r requirements.txt -r requirements-selenium.txt --break-system-packages

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
