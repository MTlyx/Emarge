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
import re
from datetime import datetime, timedelta

# Set the timezone and allowed days
PARIS_TZ = pytz.timezone("Europe/Paris")

# Set color for better printing
GREEN = "\033[32m"
RED = "\033[31m"
BLUE = "\033[34m"
RESET = "\033[0m"

TIME_SLOTS = [
    ("08:00", "09:30"),
    ("09:45", "11:15"),
    ("11:30", "13:00"),
    ("13:00", "14:30"),
    ("14:45", "16:15"),
    ("16:30", "18:00"),
    ("18:15", "19:45"),
]

NTFY_MARKER_FILE = "ntfy"
BOT_NOTIFICATION_TITLE = "Emarge Bot"

# Set variable with env from docker-compose
FORMATION = os.getenv("FORMATION")
A = os.getenv("ANNEE")
TP = os.getenv("TP")
blacklist = os.getenv("blacklist")
TOPIC = os.getenv("TOPIC")
MODE = os.getenv("MODE")
RECAP = (os.getenv("RECAP") or "non").strip().lower()

if A == "X" or TP == "X" or FORMATION == "X":
    print(f"[{RED}-{RESET}] Vous devez d'abord définir les variables d'environnement A, TP et FORMATION dans le docker-compose.yml")
    time.sleep(5)
    quit()

if MODE == "EMARGEMENT":
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import NoSuchElementException
    from fake_useragent import UserAgent
    from bs4 import BeautifulSoup

    USERNAME = os.getenv("Us")
    PASSWORD = os.getenv("Pa")

    service = Service("/usr/local/bin/chromedriver")

    if USERNAME in {None, "USER"} or PASSWORD in {None, "PASS"}:
        print(f"[{RED}-{RESET}] Vous devez d'abord définir les variables d'environnement USER et PASS dans le docker-compose.yml")
        time.sleep(5)
        quit()

elif MODE == "NOTIFICATION":
    if TOPIC is None or TOPIC == "XXXXXXXXXXX":
        print(f"[{RED}-{RESET}] Utiliser le mode notification sans renseigner de topic est inutile")
        time.sleep(5)
        quit()

if RECAP not in {"oui", "non"}:
    print(f"[{RED}-{RESET}] La variable d'environnement RECAP doit être définie sur 'oui' ou 'non'")
    time.sleep(5)
    quit()

if RECAP == "oui" and MODE != "EMARGEMENT":
    print(f"[{RED}-{RESET}] Le RECAP nécessite l'image emargement car il utilise Selenium")
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

API_URL = "https://planningsup.app/api/plannings"
PLANNING_IDS = []
if A == "3":
    S = 5
    PLANNING_IDS = [
        f"ensibs.{FORMATION}.{A}emeannee.semestre{S}s{S}.tp{TP}",
        f"ensibs.{FORMATION}.{A}emeannee.semestre{S+1}s{S+1}.tp{TP}",
    ]
elif A == "4":
    S = 7
    PLANNING_IDS = [
        f"ensibs.{FORMATION}.{A}emeannee.semestre{S}s{S}.tp{TP}",
        f"ensibs.{FORMATION}.{A}emeannee.semestre{S+1}s{S+1}.tp{TP}",
    ]
elif A == "5":
    if FORMATION == "cyberdata":
        PLANNING_IDS = [f"ensibs.{FORMATION}.{A}emeannee.semestre9s9.tp{TP}"]
    else:
        PLANNING_IDS = [f"ensibs.{FORMATION}.{A}emeannee.tp{TP}"]
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

PENDING_EMARGEMENTS = []
STOP_NEXT_DATE = None
STOP_DAY_DATE = None
NTFY_CURSOR = None
PROCESSED_NTFY_EVENT_IDS = []

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

# Set the last github commit hash
LAST_RELEASE_NAME = get_latest_releases_name()

def ntfy_is_enabled():
    """
    Return True when the topic is configured.
    """
    return TOPIC is not None and TOPIC != "XXXXXXXXXXX"


def send_notification(message, title=BOT_NOTIFICATION_TITLE):
    """
    Send a notification with ntfy.sh if the TOPIC is set
    """
    if not ntfy_is_enabled():
        return

    headers = {"Title": title}

    try:
        requests.post(
            f"https://ntfy.sh/{TOPIC}",
            data=message.encode(),
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as exc:
        logging.error(f"Impossible d'envoyer la notification ntfy : {exc}")


def send_command_notification(message):
    """
    Log and send a response for an inbound ntfy command.
    """
    log_print(message)
    send_notification(message)


def remember_ntfy_event(event_id):
    """
    Keep a short history of processed ntfy event IDs to avoid duplicates.
    """
    if not event_id or event_id in PROCESSED_NTFY_EVENT_IDS:
        return

    PROCESSED_NTFY_EVENT_IDS.append(event_id)
    if len(PROCESSED_NTFY_EVENT_IDS) > 200:
        PROCESSED_NTFY_EVENT_IDS.pop(0)


def reset_daily_controls(reference_time=None):
    """
    Drop one-day command flags once the Paris date changes.
    """
    global STOP_NEXT_DATE, STOP_DAY_DATE

    current_time = reference_time or datetime.now(PARIS_TZ)
    today = current_time.date()

    if STOP_NEXT_DATE is not None and STOP_NEXT_DATE != today:
        STOP_NEXT_DATE = None
    if STOP_DAY_DATE is not None and STOP_DAY_DATE != today:
        STOP_DAY_DATE = None


def is_day_stopped(reference_time=None):
    """
    Return True when /stop d has been requested for the current day.
    """
    current_time = reference_time or datetime.now(PARIS_TZ)
    return STOP_DAY_DATE == current_time.date()


def has_pending_stop_next(reference_time=None):
    """
    Return True when /stop 1 should skip the next emargement today.
    """
    current_time = reference_time or datetime.now(PARIS_TZ)
    return STOP_NEXT_DATE == current_time.date()


def cancel_emargement_entry(entry):
    """
    Cancel a tracked emargement job.
    """
    job = entry.get("job")
    if job is not None:
        schedule.cancel_job(job)
    entry["job"] = None
    entry["cancelled"] = True


def upcoming_emargements(reference_time=None):
    """
    Return all remaining tracked emargements for today.
    """
    current_time = reference_time or datetime.now(PARIS_TZ)
    today = current_time.date()

    return sorted(
        [
            entry for entry in PENDING_EMARGEMENTS
            if entry["scheduled_for"].date() == today
            and not entry["cancelled"]
            and not entry["executed"]
        ],
        key=lambda entry: entry["scheduled_for"],
    )


def format_emargement_entry(entry):
    """
    Format a tracked emargement for notifications.
    """
    return f"- {entry['scheduled_for'].strftime('%H:%M')} : {entry['name']}"


def list_emargements():
    """
    Send the remaining emargements for the day through ntfy.
    """
    now = datetime.now(PARIS_TZ)
    reset_daily_controls(now)

    entries = upcoming_emargements(now)
    if entries:
        lines = [f"Emargements prevus pour le {now.strftime('%d/%m/%Y')} :"]
        lines.extend(format_emargement_entry(entry) for entry in entries)
        send_command_notification("\n".join(lines))
        return

    if is_day_stopped(now):
        send_command_notification(
            f"Aucun emargement restant : l'arret manuel est actif pour le {now.strftime('%d/%m/%Y')}."
        )
        return

    send_command_notification("Aucun emargement prevu pour le reste de la journee.")


def stop_next_emargement():
    """
    Cancel the next remaining emargement, or remember the request for today's first one.
    """
    global STOP_NEXT_DATE

    now = datetime.now(PARIS_TZ)
    reset_daily_controls(now)

    if is_day_stopped(now):
        send_command_notification(
            f"Impossible d'utiliser /stop 1 : l'arret manuel est deja actif pour le {now.strftime('%d/%m/%Y')}."
        )
        return

    entries = upcoming_emargements(now)
    if entries:
        next_entry = entries[0]
        cancel_emargement_entry(next_entry)
        send_command_notification(
            f"Le prochain emargement a {next_entry['scheduled_for'].strftime('%H:%M')} pour "
            f"{next_entry['name']} a ete annule."
        )
        return

    STOP_NEXT_DATE = now.date()
    send_command_notification("Le prochain emargement programme aujourd'hui sera annule.")


def stop_day_emargements():
    """
    Cancel every remaining emargement for today.
    """
    global STOP_DAY_DATE, STOP_NEXT_DATE

    now = datetime.now(PARIS_TZ)
    reset_daily_controls(now)

    if is_day_stopped(now):
        send_command_notification(
            f"L'arret manuel est deja actif pour le {now.strftime('%d/%m/%Y')}."
        )
        return

    STOP_DAY_DATE = now.date()
    STOP_NEXT_DATE = None

    cancelled_count = 0
    for entry in upcoming_emargements(now):
        cancel_emargement_entry(entry)
        cancelled_count += 1

    if cancelled_count:
        send_command_notification(
            f"Arret manuel active pour aujourd'hui : {cancelled_count} emargement(s) restant(s) ont ete annule(s)."
        )
        return

    send_command_notification("Arret manuel active pour aujourd'hui. Aucun emargement restant a annuler.")


def handle_ntfy_command(message):
    """
    Execute supported ntfy commands.
    """
    normalized_message = re.sub(r"\s+", " ", message.strip().lower())

    if normalized_message == "/list":
        list_emargements()
        return
    if normalized_message == "/stop 1":
        stop_next_emargement()
        return
    if normalized_message == "/stop d":
        stop_day_emargements()


def fetch_ntfy_events(since_value):
    """
    Poll the ntfy JSON endpoint and return parsed events.
    """
    if not ntfy_is_enabled():
        return []

    try:
        response = requests.get(
            f"https://ntfy.sh/{TOPIC}/json",
            params={"poll": "1", "since": since_value},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error(f"Impossible de lire les commandes ntfy : {exc}")
        return []

    events = []
    for line in response.text.splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            logging.warning(f"Evenement ntfy invalide ignore : {line}")

    return events


def initialize_ntfy_cursor():
    """
    Skip old cached ntfy messages when the bot starts.
    """
    global NTFY_CURSOR

    if not ntfy_is_enabled() or NTFY_CURSOR is not None:
        return

    latest_events = fetch_ntfy_events("latest")
    if latest_events:
        latest_event = latest_events[-1]
        latest_event_id = latest_event.get("id")
        if latest_event_id:
            remember_ntfy_event(latest_event_id)
            NTFY_CURSOR = latest_event_id
            return

    NTFY_CURSOR = str(int(time.time()))


def check_ntfy_commands():
    """
    Poll the configured ntfy topic for inbound commands.
    """
    global NTFY_CURSOR

    if not ntfy_is_enabled():
        return

    reset_daily_controls()
    initialize_ntfy_cursor()

    for event in fetch_ntfy_events(NTFY_CURSOR):
        event_id = event.get("id")
        if event_id:
            NTFY_CURSOR = event_id

        if event_id in PROCESSED_NTFY_EVENT_IDS:
            continue

        remember_ntfy_event(event_id)

        if event.get("event") != "message":
            continue
        if event.get("title") == BOT_NOTIFICATION_TITLE:
            continue

        message = event.get("message", "")
        if not message:
            continue

        handle_ntfy_command(message)

def ensure_minimum_gap(events):
    """
    Ensure events are mapped to predefined time slots and only one emargement per slot.
    Time slots: 8h-9h30, 9h45-11h15, 11h30-13h00, 13h00-14h30, 14h45-16h15, 16h30-18h00, 18h15-19h45
    """
    if not events:
        return []

    # Sort events by start time
    sorted_events = sorted(events, key=lambda x: x["start"])

    result = []
    used_slots = set()  # Track which slots have been used for emargement

    for event in sorted_events:
        event_start = event["start"]
        event_end = event["end"]

        # Find which time slot(s) this event overlaps with
        overlapping_slots = []

        for i, (slot_start, slot_end) in enumerate(TIME_SLOTS):
            # Convert slot times to datetime objects for comparison
            slot_start_dt = event_start.replace(
                hour=int(slot_start.split(':')[0]),
                minute=int(slot_start.split(':')[1]),
                second=0,
                microsecond=0
            )
            slot_end_dt = event_start.replace(
                hour=int(slot_end.split(':')[0]),
                minute=int(slot_end.split(':')[1]),
                second=0,
                microsecond=0
            )

            # Check if event overlaps with this slot
            if (event_start < slot_end_dt and event_end > slot_start_dt):
                overlapping_slots.append(i)

        # Create emargement events for each overlapping slot that hasn't been used
        for slot_index in overlapping_slots:
            slot_key = (event_start.date(), slot_index)
            if slot_key not in used_slots:
                slot_start, slot_end = TIME_SLOTS[slot_index]

                # Create new event for this slot
                slot_start_dt = event_start.replace(
                    hour=int(slot_start.split(':')[0]),
                    minute=int(slot_start.split(':')[1]),
                    second=0,
                    microsecond=0
                )
                slot_end_dt = event_start.replace(
                    hour=int(slot_end.split(':')[0]),
                    minute=int(slot_end.split(':')[1]),
                    second=0,
                    microsecond=0
                )

                # Create new event for emargement
                emarge_event = event.copy()
                emarge_event["start"] = slot_start_dt
                emarge_event["end"] = slot_end_dt

                result.append(emarge_event)
                used_slots.add(slot_key)

    return result

def filter_events(events):
    """
    Filter the events to only keep the ones we want to emerge
    """
    filtered_events = []
    for event in events:
        if not any(blacklist in event["name"] for blacklist in blacklists):
            filtered_events.append(event)
    return filtered_events

def parse_planningsup_datetime(value):
    """
    Parse PlanningSup timestamps (ISO or ms) and convert to Paris timezone.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=PARIS_TZ)
    if not isinstance(value, str):
        return None
    try:
        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return PARIS_TZ.localize(parsed)
    return parsed.astimezone(PARIS_TZ)


def normalize_planning_event(event):
    """
    Convert a PlanningSup event payload into the internal event shape.
    """
    name = event.get("summary") or event.get("name") or event.get("title")
    start_dt = parse_planningsup_datetime(event.get("startDate") or event.get("start"))
    end_dt = parse_planningsup_datetime(event.get("endDate") or event.get("end"))

    if not name or not start_dt or not end_dt:
        return None

    return {"name": name, "start": start_dt, "end": end_dt}

def fetch_planning_events(planning_id):
    """
    Fetch events for a planning from the PlanningSup API.
    """
    url = f"{API_URL}/{planning_id}"
    try:
        response = requests.get(
            url,
            params={"events": "true"},
            headers={"Accept-Encoding": "gzip, deflate"},
            timeout=20,
        )
    except requests.RequestException as exc:
        logging.error(f"Erreur API PlanningSup pour {planning_id} : {exc}")
        return None

    if response.status_code != 200:
        logging.error(f"Erreur API PlanningSup pour {planning_id} : HTTP {response.status_code}")
        return None

    try:
        data = response.json()
    except json.decoder.JSONDecodeError:
        logging.error(f"Réponse invalide de l'API PlanningSup pour {planning_id}")
        return None

    if not isinstance(data, dict) or "events" not in data:
        logging.error(f"Réponse incomplète de l'API PlanningSup pour {planning_id}")
        return None

    return data.get("events", [])


def collect_planning_events(event_filter):
    """
    Load PlanningSup events for all configured plannings and keep matching events.
    """
    events = []
    successful_plannings = 0
    failed_plannings = []

    for planning_id in PLANNING_IDS:
        planning_events = fetch_planning_events(planning_id)
        if planning_events is None:
            failed_plannings.append(planning_id)
            continue

        successful_plannings += 1

        for raw_event in planning_events:
            event = normalize_planning_event(raw_event)
            if event is None or not event_filter(event):
                continue
            events.append(event)

    if successful_plannings == 0:
        logging.error("Impossible de récupérer les données de l'API PlanningSup, vérifiez votre ANNEE, FORMATION et TP")
        print(f"[{RED}-{RESET}] Impossible de récupérer les données de l'API PlanningSup, vérifiez votre ANNEE, FORMATION et TP")
        quit()

    if failed_plannings:
        logging.warning(f"Plannings inaccessibles: {', '.join(failed_plannings)}")

    return events


def current_week_bounds(reference_time=None):
    """
    Return Monday and Friday dates for the current Paris week.
    """
    current_time = reference_time or datetime.now(PARIS_TZ)
    week_start = current_time.date() - timedelta(days=current_time.weekday())
    week_end = week_start + timedelta(days=4)
    return week_start, week_end


def hours_week():
    """
    Get all PlanningSup events for the current week that would require emargement.
    """
    week_start, week_end = current_week_bounds()

    return collect_planning_events(
        lambda event: (
            week_start <= event["start"].date() <= week_end
            and 8 <= event["start"].hour <= 18
        )
    )


def build_driver(use_random_user_agent=False):
    """
    Build a configured Chrome webdriver instance.
    """
    driver_options = Options()
    driver_options.add_argument("--headless")
    driver_options.add_argument("--no-sandbox")
    driver_options.add_argument("--disable-dev-shm-usage")
    driver_options.add_argument("--window-size=1920,1080")
    driver_options.add_argument("--lang=fr-FR")

    if use_random_user_agent:
        try:
            driver_options.add_argument(f"--user-agent={UserAgent(os='Linux').random}")
        except Exception:
            logging.warning("Impossible de générer un user-agent aléatoire, utilisation du user-agent par défaut")

    return webdriver.Chrome(service=service, options=driver_options)


def open_presence_page(driver, context_label):
    """
    Log in to Moodle and open the attendance activity page.
    """
    driver.get("https://moodle.univ-ubs.fr/")
    time.sleep(10)

    select_element = driver.find_element(By.ID, "idp")
    dropdown = Select(select_element)
    dropdown.select_by_visible_text("Université Bretagne Sud - UBS")
    select_button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(@class, 'btn-primary')]")
    select_button.click()
    time.sleep(10)

    username_input = driver.find_element(By.ID, "username")
    username_input.send_keys(USERNAME)
    password_input = driver.find_element(By.ID, "password")
    password_input.send_keys(PASSWORD)
    login_button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(@class, 'btn-primary')]")
    login_button.click()

    try:
        driver.find_element(By.ID, "loginErrorsPanel")
        raise RuntimeError("Identifiant ou mot de passe incorrect")
    except NoSuchElementException:
        logging.info("Connexion réussie")
    time.sleep(10)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    target_span = soup.find("span", class_="sr-only", string="ENSIBS : Émargement")
    course_link = target_span.find_next("a") if target_span else None
    if course_link is None or not course_link.get("href"):
        raise RuntimeError(f"Impossible de trouver le lien ENSIBS : Émargement pour {context_label}")

    driver.get(course_link.get("href"))
    time.sleep(10)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    for div in soup.find_all("div", class_="activityname"):
        if "Présence" in div.get_text(" ", strip=True):
            link = div.find("a")
            if link and link.get("href"):
                driver.get(link.get("href"))
                time.sleep(5)
                return link.get("href")

    raise RuntimeError(f"Impossible de trouver le lien de présence pour {context_label}")


def parse_moodle_date_range(date_str):
    """
    Parse Moodle attendance rows like '6.04.26 (lun.) 08:00 - 09:30'.
    """
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2}).*?(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})", date_str)
    if not match:
        return None, None

    day, month, year, start_time, end_time = match.groups()
    year = int(f"20{year}")

    start = PARIS_TZ.localize(datetime.strptime(f"{year}-{int(month):02d}-{int(day):02d} {start_time}", "%Y-%m-%d %H:%M"))
    end = PARIS_TZ.localize(datetime.strptime(f"{year}-{int(month):02d}-{int(day):02d} {end_time}", "%Y-%m-%d %H:%M"))

    return start, end


def attendance_is_validated(status_text, points_text):
    """
    Return True when Moodle marks an attendance session as covered.
    """
    normalized_status = status_text.strip().lower()
    if normalized_status in {"", "?", "absent"}:
        return False

    points_match = re.search(r"(\d+)\s*/\s*(\d+)", points_text)
    if points_match:
        scored, total = map(int, points_match.groups())
        return total > 0 and scored > 0

    return True


def recup_emargement():
    """
    Retrieve validated Moodle attendance sessions for the current week.
    """
    driver = build_driver()
    week_start, week_end = current_week_bounds()
    log_print("Ouverture du navigateur Selenium pour récupérer les émargements")

    try:
        attendance_url = open_presence_page(driver, "le récapitulatif d'émargement")
        driver.get(f"{attendance_url}&view=4")
        time.sleep(10)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        table = soup.find("table", class_="generaltable attwidth boxaligncenter")
        if table is None:
            raise RuntimeError("tableau des sessions passées introuvable")

        validated_sessions = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            date_text = cells[0].get_text(" ", strip=True)
            status_text = cells[2].get_text(" ", strip=True)
            points_text = cells[3].get_text(" ", strip=True)
            start, end = parse_moodle_date_range(date_text)

            if start is None or end is None:
                continue
            if not week_start <= start.date() <= week_end:
                continue
            if not attendance_is_validated(status_text, points_text):
                continue

            validated_sessions.append({
                "start": start,
                "end": end,
                "status": status_text,
                "points": points_text,
                "raw_row": row.get_text(" ", strip=True),
            })

        return validated_sessions
    finally:
        driver.quit()
        time.sleep(2)


def event_overlaps(left_event, right_event):
    """
    Return True when two timezone-aware event intervals overlap.
    """
    return left_event["start"] < right_event["end"] and left_event["end"] > right_event["start"]


def find_missing_attendances(expected_slots, validated_sessions):
    """
    Return planned emargement slots that are not covered by a validated Moodle session.
    """
    missing_slots = []

    for slot in expected_slots:
        if any(event_overlaps(slot, session) for session in validated_sessions):
            continue
        missing_slots.append(slot)

    return missing_slots


def check_forget_attendance():
    """
    Build and send the weekly recap notification.
    """
    if RECAP != "oui":
        return

    try:
        weekly_slots = filter_events(ensure_minimum_gap(hours_week()))
        validated_sessions = recup_emargement()
    except Exception as exc:
        log_print(f"Impossible de générer le récapitulatif d'émargement : {exc}", "warning")
        return

    missing_slots = find_missing_attendances(weekly_slots, validated_sessions)
    week_start, week_end = current_week_bounds()
    logging.info(
        "RECAP: %d créneaux planning, %d sessions Moodle validées, %d manquants",
        len(weekly_slots),
        len(validated_sessions),
        len(missing_slots),
    )

    if missing_slots:
        lines = [
            f"Recap emargement du {week_start.strftime('%d/%m/%Y')} au {week_end.strftime('%d/%m/%Y')}",
            "Emargements manquants ou non valides :",
        ]
        for slot in sorted(missing_slots, key=lambda event: event["start"]):
            lines.append(
                f"- {slot['name']} le {slot['start'].strftime('%d/%m/%Y')} "
                f"de {slot['start'].strftime('%H:%M')} a {slot['end'].strftime('%H:%M')}"
            )
        message = "\n".join(lines)
    else:
        message = (
            f"Recap emargement du {week_start.strftime('%d/%m/%Y')} au "
            f"{week_end.strftime('%d/%m/%Y')} : aucun oubli detecte."
        )

    send_notification(message)
    log_print(message)

def hours_Emarge():
    """
    From the API, get each courses and their starting hours for today
    """
    now = datetime.now(PARIS_TZ)
    today_str = now.strftime("%Y-%m-%d")
    return collect_planning_events(
        lambda event: (
            event["start"].strftime("%Y-%m-%d") == today_str
            and event["start"] + timedelta(minutes=15) > now
            and 8 <= event["start"].hour <= 18
        )
    )

def emarge(course_name):
    """
    Perform all the process like a normal student to emerge
    """
    driver = build_driver(use_random_user_agent=True)
    log_print(f"Ouverture du navigateur Selenium pour {course_name}")

    try:
        open_presence_page(driver, course_name)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        try:
            link = soup.find("a", string="Envoyer le statut de présence")
            if link is None:
                raise RuntimeError("lien français introuvable")
            driver.get(link.get("href"))
            time.sleep(5)
            log_print(f"Emargement réussi pour {course_name}", "success")
        except Exception:
            try:
                soup = BeautifulSoup(driver.page_source, "html.parser")
                link = soup.find("a", string="Submit attendance")
                if link is None:
                    raise RuntimeError("lien anglais introuvable")
                driver.get(link.get("href"))
                time.sleep(5)
                log_print(f"Emargement réussi pour {course_name}", "success")
            except Exception:
                log_print(f"Impossible d'émarger pour {course_name}", "warning")
    except Exception as exc:
        log_print(f"Impossible d'émarger pour {course_name} : {exc}", "warning")
    finally:
        driver.quit()
        time.sleep(2)

def run_tracked_emargement(entry):
    """
    Execute a one-shot scheduled emargement entry.
    """
    entry["executed"] = True
    entry["job"] = None

    if MODE == "EMARGEMENT":
        emarge(entry["name"])
    elif MODE == "NOTIFICATION":
        log_print(f"Il faut émarger pour {entry['name']}", "update")

    return schedule.CancelJob


def schedule_tracked_emargement(event, scheduled_for):
    """
    Register a tracked one-shot emargement in the schedule.
    """
    entry = {
        "name": event["name"],
        "course_start": event["start"],
        "scheduled_for": scheduled_for,
        "job": None,
        "cancelled": False,
        "executed": False,
    }

    entry["job"] = schedule.every().day.at(scheduled_for.strftime("%H:%M")).do(run_tracked_emargement, entry)
    PENDING_EMARGEMENTS.append(entry)
    return entry

def schedule_random_times():
    """ 
    Set a date to emarge for each events of today.
    """
    global PENDING_EMARGEMENTS, STOP_NEXT_DATE

    now = datetime.now(PARIS_TZ)
    reset_daily_controls(now)
    check_for_updates(LAST_RELEASE_NAME)
    schedule.clear()
    schedule.every().day.at("07:00").do(schedule_random_times)
    PENDING_EMARGEMENTS = []
    times = []

    if RECAP == "oui" and now.weekday() == 4:
        schedule.every().day.at("20:00").do(check_forget_attendance)

    # Check if current day is weekend (5 = Saturday, 6 = Sunday)
    if now.weekday() >= 5:
        return

    # Get from the API all the courses of the student for today
    events_today = ensure_minimum_gap(hours_Emarge())
    events_filtered = sorted(filter_events(events_today), key=lambda event: event["start"])

    if is_day_stopped(now):
        log_print("Arret manuel actif : aucun emargement ne sera programme aujourd'hui")
        return

    # Add a timedelta
    for event in events_filtered:
        if MODE == "EMARGEMENT":
            scheduled_for = event["start"] + timedelta(minutes=random.randint(5, 10))
        elif MODE == "NOTIFICATION":
            scheduled_for = event["start"]
        else:
            continue

        if has_pending_stop_next(scheduled_for):
            STOP_NEXT_DATE = None
            log_print(
                f"Le prochain emargement a {scheduled_for.strftime('%H:%M')} pour {event['name']} "
                "a ete ignore suite a /stop 1"
            )
            continue

        schedule_tracked_emargement(event, scheduled_for)
        times.append(scheduled_for.strftime("%H:%M"))

    if times:
        times.sort()
        log_print(f"Emargement prévu à {', '.join(times)}")
    else:
        log_print(f"Aucun cours à venir aujourd'hui")

def main():
    """
    Start the script the Emarge bot
    """
    if not os.path.exists(NTFY_MARKER_FILE):
        log_print(f"Démarrage du programme d'émargement...", "first")
        with open(NTFY_MARKER_FILE, "w") as f:
            pass

    schedule_random_times()
    initialize_ntfy_cursor()

    # While loop to check for ntfy commands and pending emargements
    while True:
        check_ntfy_commands()
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    main()
