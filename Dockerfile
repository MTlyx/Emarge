FROM selenium/standalone-firefox:latest

WORKDIR /app

COPY app/* ./

RUN sudo pip install --no-cache-dir -r requirements.txt --break-system-packages

CMD ["sudo", "--preserve-env=USERNAME,PASSWORD,TOPIC,FORMATION,ANNEE,TP,BLACKLIST,LANG", "bash", "-c", "python3 -u script.py"]
