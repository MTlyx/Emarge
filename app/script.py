import time
import os
import logging
import stat
import time
import pytz
import schedule
import datetime
import random
import requests
import json
from datetime import datetime, timedelta

# Set the timezone and allowed days
PARIS_TZ = pytz.timezone("Europe/Paris")

# Set color for better printing
GREEN = "\033[32m"
RED = "\033[31m"
BLUE = "\033[34m"
RESET = "\033[0m"

# Set variable with env from docker-compose
FORMATION = os.getenv("FORMATION")
A = os.getenv("ANNEE")
TP = os.getenv("TP")
blacklist = os.getenv("blacklist")
TOPIC = os.getenv("TOPIC")
MODE = os.getenv("MODE")

if A == "X" or TP == "X" or FORMATION == "X":
    print(f"[{RED}-{RESET}] Vous devez d'abord définir les variables d'environnement A, TP et FORMATION dans le docker-compose.yml")
    time.sleep(5)
    quit()

if MODE == "EMARGEMENT":
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import NoSuchElementException
    from fake_useragent import UserAgent
    from bs4 import BeautifulSoup

    USERNAME = os.getenv("Us")
    PASSWORD = os.getenv("Pa")

    # Set options for selenium
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')

    if USERNAME == 'USER' or PASSWORD == 'PASS':
        print(f"[{RED}-{RESET}] Vous devez d'abord définir les variables d'environnement USER et PASS dans le docker-compose.yml")
        time.sleep(5)
        quit()

elif MODE == "NOTIFICATION":
    if TOPIC is None and TOPIC == "XXXXXXXXXXX":
        print(f"[{RED}-{RESET}] Utiliser le mode notification sans renseigner de topic est inutile")
        time.sleep(5)
        quit()

TP = int(TP)
if not 1 <= TP <= 6:
    print(f"[{RED}-{RESET}] Votre TP doit être compris entre 1 et 6")
    time.sleep(5)
    quit()

if FORMATION not in {"cyberdefense", "cyberdata", "cyberlog"}:
    print(f"[{RED}-{RESET}] Votre FORMATION doit être cyberdefense, cyberdata ou cyberlog")
    time.sleep(5)
    quit()

API_URL = "https://planningsup.app/api/v1/calendars"
if A == "3":
    S = 5
    URL_PLANNING =  f"{API_URL}?p=ensibs.{FORMATION}.{A}emeannee.semestre{S}s{S}.tp{TP}"
    URL_PLANNING += f",ensibs.{FORMATION}.{A}emeannee.semestre{S+1}s{S+1}.tp{TP}"
elif A == "4":
    S = 7
    URL_PLANNING =  f"{API_URL}?p=ensibs.{FORMATION}.{A}emeannee.semestre{S}s{S}.tp{TP}"
    URL_PLANNING += f",ensibs.{FORMATION}.{A}emeannee.semestre{S+1}s{S+1}.tp{TP}"
elif A == "5":
    URL_PLANNING =  f"{API_URL}?p=ensibs.{FORMATION}.{A}emeannee.tp{TP}"
else:
    print(f"[{RED}-{RESET}] Votre ANNEE doit être 3, 4 ou 5")
    time.sleep(5)
    quit()

if blacklist:
    blacklists = blacklist.split(", ")
else:
    blacklists = []

logging.basicConfig(
    filename='emargement.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)

def get_latest_releases_name():
    """
    Fetch the latest releases from the GitHub repo
    """
    url = f"https://api.github.com/repos/MTlyx/Emarge/releases/latest"
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()["name"]
    
    log_print("Error fetching latest releases")
    return None

def check_for_updates(LAST_RELEASE_NAME):
    """
    Check if the git repo is up to date
    """
    latest_name = get_latest_releases_name()
    
    if latest_name:
        if latest_name != LAST_RELEASE_NAME:
            log_print(f"La nouvelle mise à jour {latest_name} est disponible sur github", "update")
            LAST_RELEASE_NAME = latest_name

# Set the last github commit hash
LAST_RELEASE_NAME = get_latest_releases_name()

def log_print(message, warning="info"):
    """
    Print a message with a specific color, log it and send a notification is needed.
    """
    current_time = datetime.now(PARIS_TZ).strftime("%H:%M")

    if warning == "info":
        print(f"[{BLUE}+{RESET}] {message}")
        logging.info(message)
    elif warning == "warning":
        print(f"[{RED}-{RESET}] {message}")
        logging.warning(message)
        send_notification(f"❌ {message} à {current_time}")
    elif warning == "success":
        print(f"[{GREEN}*{RESET}] {message}")
        logging.info(message)
        send_notification(f"✅ {message} à {current_time}")
    elif warning == "first":
        print(f"[{GREEN}*{RESET}] {message}")
        send_notification(f"⭐ Le programme d'émargement c'est bien lancé pour la premiere fois avec ntfy à {current_time} en mode {MODE}")
    elif warning == "update":
        print(f"[{BLUE}+{RESET}] {message}")
        send_notification(f"🆕 {message}")

def send_notification(message):
    """
    Send a notification with ntfy.sh if the TOPIC is set
    """
    if TOPIC is not None and TOPIC != "XXXXXXXXXXX":
        requests.post(f"https://ntfy.sh/{TOPIC}", data=message.encode())

def filter_events(events):
    """
    Filter the events to only keep the ones we want to emerge
    """
    filtered_events = []
    for event in events:
        if not any(blacklist in event["name"] for blacklist in blacklists):
            filtered_events.append(event)
    return filtered_events

def hours_Emarge():
    """
    From the API, get each courses and their starting hours for today
    """
    response = requests.get(URL_PLANNING)
    try:
        data = response.json()
    except json.decoder.JSONDecodeError:
        logging.error("Impossible de récupérer les données de l'API, vérifiez votre ANNEE, SEMESTRE et TP")
        print(f"[{RED}-{RESET}] Impossible de récupérer les données de l'API, vérifiez votre ANNEE, SEMESTRE et TP")
        quit()

    today_str = datetime.now(PARIS_TZ).strftime("%Y-%m-%d")
    # Extract relevant fields and convert timestamps
    events = [
        {
            "name": event["name"],
            "start": datetime.fromtimestamp(event["start"] / 1000, tz=PARIS_TZ),
            "end": datetime.fromtimestamp(event["end"] / 1000, tz=PARIS_TZ),
        }
        for planning in data.get("plannings", [])
        for event in planning.get("events", [])
        if (datetime.fromtimestamp(event["start"] / 1000, tz=PARIS_TZ)).strftime("%Y-%m-%d") == today_str
        and (datetime.fromtimestamp(event["start"] / 1000, tz=PARIS_TZ)) + timedelta(minutes=15) > datetime.now(PARIS_TZ)
        and 8 <= (datetime.fromtimestamp(event["start"] / 1000, tz=PARIS_TZ)).hour <= 18
    ]

    # Return the list of events of today
    return events

def emarge(course_name):
    """
    Perform all the process like a normal student to emerge
    """
    options.add_argument(f"--user-agent={UserAgent(os='Linux').random}")
    driver = webdriver.Chrome(options=options)
    log_print(f"Ouverture du navigateur Selenium pour {course_name}")

    driver.get("https://moodle.univ-ubs.fr/")
    time.sleep(10)

    # Select UBS on the mir
    select_element = driver.find_element(By.ID, "idp")
    dropdown = Select(select_element)
    dropdown.select_by_visible_text("Université Bretagne Sud - UBS")
    select_button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(@class, 'btn-primary')]")
    select_button.click()
    time.sleep(10)

    # Enter USERNAME / PASSWORD and submit them
    username_input = driver.find_element(By.ID, "username")
    username_input.send_keys(USERNAME)
    password_input = driver.find_element(By.ID, "password")
    password_input.send_keys(PASSWORD)
    login_button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(@class, 'btn-primary')]")
    login_button.click()

    # Check if the mir accepted our credentials
    try:
        driver.find_element(By.ID, "loginErrorsPanel")
        log_print(f"Identifiant ou mot de passe incorrect", "warning")
        driver.quit()
        quit()
    except NoSuchElementException:
        logging.info("Connexion réussie")
    time.sleep(10)

    # Click on the first result that contains "ENSIBS : Émargement"
    try:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        target_span = soup.find('span', class_='sr-only', string='ENSIBS : Émargement')
        link = target_span.find_next('a')
        href = link.get('href')
        driver.get(href)
        time.sleep(10)

    except Exception as e:
        log_print(f"Impossible de trouver le lien d'émargement pour {course_name} : {e}", "warning")
        driver.quit()
        quit()

    # Click on the Présence link on the bottom of the page
    try:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        activity_divs = soup.find_all('div', class_='activityname')
        for div in activity_divs:
            if "Présence" in div.text:
                link = div.find('a')['href']
                driver.get(link)
                time.sleep(5)
                break
    except Exception as e:
        log_print(f"Impossible de trouver le lien d'émargement pour {course_name} : {e}", "warning")
        driver.close()
        driver.quit()
        quit()

    # Click on Envoyer le statut de présence or Submit attendance in english
    try:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        link = soup.find('a', string='Envoyer le statut de présence')
        href = link.get('href')
        driver.get(href)
        time.sleep(5)
        log_print(f"Emargement réussi pour {course_name}", "success")
    except:
        try:
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            link = soup.find('a', string='Submit attendance')
            href = link.get('href')
            driver.get(href)
            time.sleep(5)
            log_print(f"Emargement réussi pour {course_name}", "success")
        except:
            log_print(f"Impossible d'émarger pour {course_name}", "warning")

    driver.quit()
    time.sleep(2)

def schedule_random_times():
    """ 
    Set a date to emarge for each events of today.
    """
    check_for_updates(LAST_RELEASE_NAME)
    schedule.clear()
    schedule.every().day.at("07:00").do(schedule_random_times)
    times = []

    # Check if current day is weekend (5 = Saturday, 6 = Sunday)
    if datetime.now(PARIS_TZ).weekday() >= 5:
        return

    # Get from the API all the courses of the student for today
    events_today = hours_Emarge()
    events_filtered = filter_events(events_today)

    # Add a timedelta
    for event in events_filtered:
        if MODE == "EMARGEMENT":
            start_hour = (event["start"] + timedelta(minutes=random.randint(5, 10))).strftime("%H:%M")
            event_name = event["name"]
            schedule.every().day.at(start_hour).do(emarge, event_name)
        elif MODE == "NOTIFICATION":
            start_hour = event["start"].strftime("%H:%M")
            message = f'Il faut émarger pour {event["name"]}'
            schedule.every().day.at(start_hour).do(log_print, message, "update")
        times.append(f"{start_hour}")

    if times:
        times.sort()
        log_print(f"Emargement prévu à {', '.join(times)}")
    else:
        log_print(f"Aucun cours à venir aujourd'hui")

def main():
    """
    Start the script the Emarge bot
    """
    if not os.path.exists("ntfy"):
        log_print(f"Démarrage du programme d'émargement...", "first")
        with open("ntfy", "w") as f:
            pass

    schedule_random_times()

    # While loop to check every minute if it's the time to emarge
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
