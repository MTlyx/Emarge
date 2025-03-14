import os
import sys
import json
import re
import random
import time
import logging
import requests
import pytz
import schedule
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException
from fake_useragent import UserAgent
from bs4 import BeautifulSoup

# Constantes
PARIS_TZ = pytz.timezone("Europe/Paris")
EMARGEMENT_TIMERANGES = {
    "08:00": "09:30",
    "09:45": "11:15",
    "11:30": "13:00",
    "13:00": "14:30",
    "14:45": "16:15",
    "16:30": "18:00",
    "18:15": "19:45",
}
DELTA_START_TIME, DELTA_END_TIME = 1, 7
LOG_FILE = "emargement.log"
MOODLE_URL = "https://moodle.univ-ubs.fr/"

# Codes couleurs pour l'affichage
GREEN = "\033[32m"
RED = "\033[31m"
BLUE = "\033[34m"
RESET = "\033[0m"

# Variables d'environnement
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
FORMATION = os.getenv("FORMATION")
ANNEE = os.getenv("ANNEE")
TP = os.getenv("TP")
BLACKLIST = os.getenv("BLACKLIST", "").split(", ") if os.getenv("BLACKLIST") else []
LANG = os.getenv("LANG", "FR")
TOPIC = os.getenv("TOPIC")

# Textes selon la langue
if LANG == "FR":
    ATTENDANCE_TEXT = "Envoyer le statut de présence"
    ORACLE_ATTENDANCE_SUCCESSFUL = "Votre présence à cette session a été enregistrée."
elif LANG == "EN":
    ATTENDANCE_TEXT = "Submit attendance"
    ORACLE_ATTENDANCE_SUCCESSFUL = "Your attendance in this session has been recorded."

# Variables globales pour le planning
previous_events = []
scheduled_times = {}
emargement_times = {}

# Configuration de Selenium
options = Options()
options.add_argument("--headless")


def init_logging():
    """Initialise la configuration des logs."""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        filemode="a",
    )


def validate_config():
    """Vérifie que les variables d'environnement nécessaires sont définies et valides."""
    global TP
    if any(var is None for var in [USERNAME, PASSWORD, FORMATION, ANNEE, TP]):
        msg = "Veuillez compléter les variables USERNAME, PASSWORD, FORMATION, ANNEE et TP dans le fichier docker-compose.yml."
        logging.error(msg)
        print(f"[{RED}ERROR{RESET}] {msg}")
        sys.exit(1)
    try:
        TP_int = int(TP)
    except ValueError:
        logging.error("TP doit être un entier.")
        print(f"[{RED}ERROR{RESET}] TP doit être un entier.")
        sys.exit(1)
    TP = TP_int
    if TP not in range(1, 7):
        msg = "TP doit être entre 1 et 6."
        logging.error(msg)
        print(f"[{RED}ERROR{RESET}] {msg}")
        sys.exit(1)
    if FORMATION not in {"cyberdefense", "cyberdata", "cyberlog"}:
        msg = "FORMATION doit être parmi: cyberdefense, cyberdata, cyberlog."
        logging.error(msg)
        print(f"[{RED}ERROR{RESET}] {msg}")
        sys.exit(1)
    if ANNEE not in {"3", "4", "5"}:
        msg = "ANNEE doit être 3, 4, ou 5."
        logging.error(msg)
        print(f"[{RED}ERROR{RESET}] {msg}")
        sys.exit(1)
    if LANG not in {"FR", "EN"}:
        msg = "LANG doit être FR ou EN."
        logging.error(msg)
        print(f"[{RED}ERROR{RESET}] {msg}")
        sys.exit(1)


def get_url_planning():
    """Détermine l'URL de l'API PlanningSup en fonction de l'année, de la formation et du TP."""
    if ANNEE in {"3", "4"}:
        S = 5 if ANNEE == "3" else 7
        url = (
            f"https://planningsup.app/api/v1/calendars?p=ensibs.{FORMATION}.{ANNEE}emeannee.semestre{S}s{S}.tp{TP},"
            f"ensibs.{FORMATION}.{ANNEE}emeannee.semestre{S+1}s{S+1}.tp{TP}"
        )
    elif ANNEE == "5":
        url = f"https://planningsup.app/api/v1/calendars?p=ensibs.{FORMATION}.{ANNEE}emeannee.tp{TP}"
    return url


def send_notification(message):
    """Envoie une notification via ntfy.sh si TOPIC est défini."""
    if TOPIC is not None:
        requests.post(f"https://ntfy.sh/{TOPIC}", data=message.encode())


def fetch_lessons():
    """Récupère les cours de la journée en interrogeant l'API PlanningSup."""
    url_planning = get_url_planning()
    response = requests.get(url_planning)
    try:
        data = response.json()
    except json.decoder.JSONDecodeError as e:
        msg = "Erreur lors de la communication avec l'API. Vérifier les variables ANNEE, SEMESTRE, et TP."
        logging.error(msg)
        logging.error(e)
        print(f"[{RED}ERROR{RESET}] {msg}")
        sys.exit(1)
    today_str = datetime.now(PARIS_TZ).strftime("%Y-%m-%d")
    lessons = []
    for planning in data.get("plannings", []):
        for event in planning.get("events", []):
            event_date = datetime.fromtimestamp(event["start"] / 1000, tz=PARIS_TZ)
            if event_date.strftime("%Y-%m-%d") == today_str and (
                datetime.fromtimestamp(event["start"] / 1000, tz=PARIS_TZ)
            ) + timedelta(minutes=15) > datetime.now(PARIS_TZ):
                lessons.append(
                    {
                        "name": event["name"],
                        "start": event_date,
                        "end": datetime.fromtimestamp(event["end"] / 1000, tz=PARIS_TZ),
                    }
                )
    return lessons


def filter_events(events):
    """Filtre les cours dont le nom contient un élément de la blacklist."""
    return [event for event in events if not any(b in event["name"] for b in BLACKLIST)]


def get_event_timeranges(event_start, event_end):
    """
    Renvoie la liste des créneaux horaires correspondant aux plages d'émargement durant lesquelles le cours se déroule.
    """
    timeranges = []
    event_date = event_start.date()
    for start_str, end_str in EMARGEMENT_TIMERANGES.items():
        start_dt = PARIS_TZ.localize(
            datetime.combine(event_date, datetime.strptime(start_str, "%H:%M").time())
        )
        end_dt = PARIS_TZ.localize(
            datetime.combine(event_date, datetime.strptime(end_str, "%H:%M").time())
        )
        if event_start <= end_dt and event_end >= start_dt:
            timeranges.append((start_dt, end_dt))
    return timeranges


def schedule_emargement_for_event(event):
    """
    Calcule une heure d'émargement pour l'événement en fonction des plages disponibles.
    """
    timeranges = get_event_timeranges(event["start"], event["end"])
    if not timeranges:
        return None
    candidate_times = []
    for range_start, range_end in timeranges:
        delay = timedelta(minutes=random.randint(DELTA_START_TIME, DELTA_END_TIME))
        candidate = max(range_start, event["start"]) + delay
        if candidate <= range_end:
            candidate_times.append(candidate)
    if not candidate_times:
        return None
    return min(candidate_times)


def schedule_emargement():
    """
    Récupère et filtre les cours de la journée, puis planifie l'émargement pour chaque événement non encore programmé.
    Après avoir planifié tous les événements, ils sont affichés dans l'ordre trié.
    """
    global previous_events, scheduled_times
    new_events = filter_events(fetch_lessons())
    if new_events == previous_events:
        return
    previous_events = new_events
    today = datetime.now(PARIS_TZ).date()

    for event in new_events:
        if event["start"].date() != today:
            continue

        event_key = (
            event["name"],
            event["start"].strftime("%H:%M"),
            event["end"].strftime("%H:%M"),
        )
        if event_key in scheduled_times:
            continue

        # On vérifie si un temps d'émargement est déjà enregistré dans l'une des plages horaires du cours
        timeranges = get_event_timeranges(event["start"], event["end"])
        already_scheduled = False
        for recorded_start, emarg_time_str in emargement_times.items():
            if recorded_start.date() != event["start"].date():
                continue
            scheduled_dt = PARIS_TZ.localize(
                datetime.combine(
                    event["start"].date(),
                    datetime.strptime(emarg_time_str, "%H:%M").time(),
                )
            )
            for start_dt, end_dt in timeranges:
                if start_dt <= scheduled_dt <= end_dt:
                    already_scheduled = True
                    break
            if already_scheduled:
                break

        if already_scheduled:
            continue

        scheduled_time = schedule_emargement_for_event(event)
        if scheduled_time is None:
            continue
        scheduled_time_str = scheduled_time.strftime("%H:%M")
        schedule.every().day.at(scheduled_time_str, PARIS_TZ).do(
            lambda e=event, t=scheduled_time_str: perform_emargement(e, t)
        )
        scheduled_times[event_key] = scheduled_time

    # Après avoir planifié tous les événements, on trie et on affiche les résultats
    sorted_times = sorted(scheduled_times.items(), key=lambda x: x[1])
    for event, emargement_time in sorted_times:
        event_name = event[0]
        start_time = event[1]
        end_time = event[2]
        time_str = emargement_time.strftime("%H:%M")
        logging.info(
            f"Émargement planifié pour {event_name} ({start_time} - {end_time}) à {time_str}."
        )
        print(
            f"[{BLUE}INFO{RESET}] Émargement planifié pour {event_name} ({start_time} - {end_time}) à {time_str}."
        )


def login_to_moodle(driver):
    """
    Sélectionne le fournisseur d'identité puis effectue l'authentification sur Moodle.
    """
    driver.get(MOODLE_URL)
    time.sleep(10)
    try:
        # Sélection du fournisseur d'identité
        select_element = driver.find_element(By.ID, "idp")
        dropdown = Select(select_element)
        dropdown.select_by_visible_text("Université Bretagne Sud - UBS")
        select_button = driver.find_element(
            By.XPATH, "//button[@type='submit' and contains(@class, 'btn-primary')]"
        )
        select_button.click()
        time.sleep(10)
    except Exception as e:
        msg = "Erreur lors de la sélection du fournisseur d'identité"
        logging.error(f"{msg}: {e}")
        print(f"[{RED}ERROR{RESET}] {msg}")
        driver.quit()
        sys.exit(1)

    try:
        # Authentification
        username_input = driver.find_element(By.ID, "username")
        username_input.send_keys(USERNAME)
        password_input = driver.find_element(By.ID, "password")
        password_input.send_keys(PASSWORD)
        login_button = driver.find_element(
            By.XPATH, "//button[@type='submit' and contains(@class, 'btn-primary')]"
        )
        login_button.click()
        time.sleep(10)
    except Exception as e:
        msg = "Erreur lors de l'authentification"
        logging.error(f"{msg}: {e}")
        print(f"[{RED}ERROR{RESET}] {msg}")
        driver.quit()
        sys.exit(1)

    # Vérification du succès de la connexion
    try:
        driver.find_element(By.ID, "loginErrorsPanel")
        msg = "Login incorrect. Vérifier les variables USERNAME et PASSWORD."
        logging.error(msg)
        logging.info(BeautifulSoup(driver.page_source, "html.parser").html)
        print(f"[{RED}ERROR{RESET}] {msg}")
        driver.quit()
        sys.exit(1)
    except NoSuchElementException:
        msg = "Login réussi."
        logging.info(msg)
        print(f"[{GREEN}SUCCESS{RESET}] {msg}")


def submit_attendance(driver, event):
    """
    Navigue vers la page d'émargement, soumet la présence et vérifie le résultat.
    """
    driver.get(MOODLE_URL + "mod/attendance/view.php?id=433339")
    time.sleep(10)
    try:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        link = soup.find("a", string=re.compile(ATTENDANCE_TEXT))
        if not link:
            raise Exception("Lien d'émargement non trouvé")
        href = link.get("href")
        driver.get(href)
        time.sleep(10)
    except Exception as e:
        msg = f"Échec lors de la soumission de la présence pour {event['name']} ({event['start'].strftime('%H:%M')} - {event['end'].strftime('%H:%M')})."
        logging.warning(msg)
        logging.info(driver.page_source)
        print(f"[{RED}ERROR{RESET}] {msg}")
        send_notification(f"❌ {msg}")
        return False

    soup = BeautifulSoup(driver.page_source, "html.parser")
    if soup.find(string=re.compile(ORACLE_ATTENDANCE_SUCCESSFUL)):
        msg = f"Émargement réussi pour {event['name']} ({event['start'].strftime('%H:%M')} - {event['end'].strftime('%H:%M')})."
        logging.info(msg)
        print(f"[{GREEN}SUCCESS{RESET}] {msg}")
        send_notification(f"✅ {msg}")
        return True
    else:
        msg = f"Échec lors de la procédure d'émargement pour {event['name']} ({event['start'].strftime('%H:%M')} - {event['end'].strftime('%H:%M')})."
        logging.warning(msg)
        logging.info(driver.page_source)
        print(f"[{RED}ERROR{RESET}] {msg}")
        send_notification(f"❌ {msg}")
        return False


def perform_emargement(event, scheduled_time_str):
    """
    Effectue l'émargement pour l'événement à l'heure programmée.
    """
    options.set_preference(
        "general.useragent.override", f"{UserAgent(os='Linux').random}"
    )
    driver = webdriver.Firefox(options=options, service=Service("geckodriver"))
    current_time = datetime.now(PARIS_TZ).strftime("%H:%M")
    msg = f"Démarrage de l'émargement pour : {event['name']} ({event['start'].strftime('%H:%M')} - {event['end'].strftime('%H:%M')}) à {current_time}."
    logging.info(msg)
    print(f"[{BLUE}INFO{RESET}] {msg}")
    emargement_times[event["start"]] = scheduled_time_str

    login_to_moodle(driver)
    success = submit_attendance(driver, event)
    driver.quit()
    return success


def main():
    init_logging()
    validate_config()
    print(f"[{BLUE}INFO{RESET}] Démarrage du programme d'émargement...")
    schedule.every(15).minutes.do(schedule_emargement)
    schedule_emargement()
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
