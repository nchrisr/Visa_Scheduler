import time
import json
import os
import random
import requests
import configparser
import pygame
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait as Wait
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from embassy import *

config = configparser.ConfigParser()
config.read('config.ini')

pygame.init()

# Load the sound file
sound = pygame.mixer.Sound("beep_beep.mp3")

# Play the sound
sound.play()

# Wait for the sound to finish playing
while pygame.mixer.get_busy():
    pass

# Personal Info:
# Account and current appointment info from https://ais.usvisa-info.com
USERNAME = config['PERSONAL_INFO']['USERNAME']
PASSWORD = config['PERSONAL_INFO']['PASSWORD']
# Find SCHEDULE_ID in re-schedule page link:
# https://ais.usvisa-info.com/en-am/niv/schedule/{SCHEDULE_ID}/appointment
SCHEDULE_ID = config['PERSONAL_INFO']['SCHEDULE_ID']
# Target Period:
PRIOD_START = config['PERSONAL_INFO']['PRIOD_START']
PRIOD_END = config['PERSONAL_INFO']['PRIOD_END']

# Embassy Section:
EMBASSIES_TO_CHECK = ["en-ca-cal", "en-ca-hal", "en-ca-mon", "en-ca-ott", "en-ca-que", "en-ca-tor", "en-ca-van"]

# Time Section:
minute = 60
hour = 60 * minute
# Time between steps (interactions with forms)
STEP_TIME = 0.5

# Time between check for different embassies.
CHECK_TIME_L_BOUND = config['TIME'].getfloat('CHECK_TIME_L_BOUND')
CHECK_TIME_U_BOUND = config['TIME'].getfloat('CHECK_TIME_U_BOUND')

# Time between retries/checks for available dates (seconds)
RETRY_TIME_L_BOUND = config['TIME'].getfloat('RETRY_TIME_L_BOUND')
RETRY_TIME_U_BOUND = config['TIME'].getfloat('RETRY_TIME_U_BOUND')
# Cooling down after WORK_LIMIT_TIME hours of work (Avoiding Ban)
WORK_LIMIT_TIME = config['TIME'].getfloat('WORK_LIMIT_TIME')
WORK_COOLDOWN_TIME = config['TIME'].getfloat('WORK_COOLDOWN_TIME')
# Temporary Banned (empty list): wait COOLDOWN_TIME hours
BAN_COOLDOWN_TIME = config['TIME'].getfloat('BAN_COOLDOWN_TIME')

# CHROMEDRIVER
# Details for the script to control Chrome
LOCAL_USE = config['CHROMEDRIVER'].getboolean('LOCAL_USE')
# Path to use for Chrome driver
LOCAL_CHROMEDRIVER_PATH = config['CHROMEDRIVER']['DRIVER_PATH']
# Optional: HUB_ADDRESS is mandatory only when LOCAL_USE = False
HUB_ADDRESS = config['CHROMEDRIVER']['HUB_ADDRESS']

JS_SCRIPT = ("var req = new XMLHttpRequest();"
             f"req.open('GET', '%s', false);"
             "req.setRequestHeader('Accept', 'application/json, text/javascript, */*; q=0.01');"
             "req.setRequestHeader('X-Requested-With', 'XMLHttpRequest');"
             f"req.setRequestHeader('Cookie', '_yatri_session=%s');"
             "req.send(null);"
             "return req.responseText;")

LOG_FILE_NAME = "log_" + str(datetime.now().date()) + ".log.txt"
msg = ""

def auto_action(label, find_by, el_type, action, value, sleep_time=0.0):
    print("\t"+ label +":", end="")
    # Find Element By
    find_by_lowercase = find_by.lower()
    if find_by_lowercase == 'id':
        item = driver.find_element(By.ID, el_type)
    elif find_by_lowercase == 'name':
        item = driver.find_element(By.NAME, el_type)
    elif find_by_lowercase == 'class':
        item = driver.find_element(By.CLASS_NAME, el_type)
    elif find_by_lowercase == 'xpath':
        item = driver.find_element(By.XPATH, el_type)
    else:
        return 0

    action_lower_case = action.lower()
    if action_lower_case == 'send':
        item.send_keys(value)
    elif action_lower_case == 'click':
        item.click()
    else:
        return 0

    # Do Action:
    print("\t\tCheck!")
    if sleep_time:
        time.sleep(sleep_time)


def do_login(sign_in_link):
    # Bypass reCAPTCHA
    driver.get(sign_in_link)
    time.sleep(STEP_TIME)
    Wait(driver, 60).until(EC.presence_of_element_located((By.NAME, "commit")))
    auto_action("Click bounce", "xpath", '//a[@class="down-arrow bounce"]', "click", "", STEP_TIME)
    auto_action("Email", "id", "user_email", "send", USERNAME, STEP_TIME)
    auto_action("Password", "id", "user_password", "send", PASSWORD, STEP_TIME)
    auto_action("Privacy", "class", "icheckbox", "click", "", STEP_TIME)
    auto_action("Enter Panel", "name", "commit", "click", "", STEP_TIME)
    Wait(driver, 60).until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(), '" + current_regex_continue + "')]")))
    print("\n\tlogin successful!\n")

def reschedule(date, appointment_url, time_url):
    time = get_time(date, time_url)
    driver.get(appointment_url)
    headers = {
        "User-Agent": driver.execute_script("return navigator.userAgent;"),
        "Referer": appointment_url,
        "Cookie": "_yatri_session=" + driver.get_cookie("_yatri_session")["value"]
    }
    data = {
        "utf8": driver.find_element(by=By.NAME, value='utf8').get_attribute('value'),
        "authenticity_token": driver.find_element(by=By.NAME, value='authenticity_token').get_attribute('value'),
        "confirmed_limit_message": driver.find_element(by=By.NAME, value='confirmed_limit_message').get_attribute('value'),
        "use_consulate_appointment_capacity": driver.find_element(by=By.NAME, value='use_consulate_appointment_capacity').get_attribute('value'),
        "appointments[consulate_appointment][facility_id]": current_facility,
        "appointments[consulate_appointment][date]": date,
        "appointments[consulate_appointment][time]": time,
    }
    r = requests.post(appointment_url, headers=headers, data=data)
    if(r.text.find('Successfully Scheduled') != -1):
        title = "SUCCESS"
        msg = f"Rescheduled Successfully! {date} {time}"
    else:
        title = "FAIL"
        msg = f"Reschedule Failed!!! {date} {time}"
    return [title, msg]


def get_date():
    # Requesting to get the whole available dates
    session = driver.get_cookie("_yatri_session")["value"]
    script = JS_SCRIPT % (str(date_url), session)
    content = driver.execute_script(script)
    return json.loads(content)

def get_time(date, time_url):
    time_url = time_url % date
    session = driver.get_cookie("_yatri_session")["value"]
    script = JS_SCRIPT % (str(time_url), session)
    content = driver.execute_script(script)
    data = json.loads(content)
    time = data.get("available_times")[-1]
    print(f"Got time successfully! {date} {time}")
    return time


def is_logged_in():
    content = driver.page_source
    if(content.find("error") != -1):
        return False
    return True


def get_available_date(dates):
    # Evaluation of different available dates
    def is_in_period(date, PSD, PED):
        new_date = datetime.strptime(date, "%Y-%m-%d")
        result = ( PED > new_date and new_date > PSD )
        # print(f'{new_date.date()} : {result}', end=", ")
        return result
    
    PED = datetime.strptime(PRIOD_END, "%Y-%m-%d")
    PSD = datetime.strptime(PRIOD_START, "%Y-%m-%d")
    for d in dates:
        date = d.get('date')
        if is_in_period(date, PSD, PED):
            return date
    print(f"\n\nNo available dates between ({PSD.date()}) and ({PED.date()})!")


def info_logger(file_path, log):
    # file_path: e.g. "log.txt"
    with open(file_path, "a") as file:
        file.write(str(datetime.now().time()) + ":\n" + log + "\n")


if LOCAL_USE:
    if os.path.exists(LOCAL_CHROMEDRIVER_PATH):
        driver = webdriver.Chrome(executable_path=LOCAL_CHROMEDRIVER_PATH)
    else:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
else:
    driver = webdriver.Remote(command_executor=HUB_ADDRESS, options=webdriver.ChromeOptions())


if __name__ == "__main__":

    #LOG_FILE_NAME = "log_" + str(datetime.now().date()) + ".txt"
    t0 = time.time()
    #do_login()
    request_count = 0
    sign_out_url = ""
    logged_in = False
    while True:

        kill_infinite_loop = False
        found_appointment = False
        # Keep track of the number of embassies checked that returned 0 count for dates. If all embassies return no dates, its possibly a ban.
        empty_dates_count = 0
        for embassy in EMBASSIES_TO_CHECK:
            current_embassy_region = Embassies[embassy][0]
            current_facility = Embassies[embassy][1]
            current_regex_continue = Embassies[embassy][2]

            sign_in_link = f"https://ais.usvisa-info.com/{current_embassy_region}/niv/users/sign_in"
            appointment_url = f"https://ais.usvisa-info.com/{current_embassy_region}/niv/schedule/{SCHEDULE_ID}/appointment"
            date_url = f"https://ais.usvisa-info.com/{current_embassy_region}/niv/schedule/{SCHEDULE_ID}/appointment/days/{current_facility}.json?appointments[expedite]=false"
            time_url = f"https://ais.usvisa-info.com/{current_embassy_region}/niv/schedule/{SCHEDULE_ID}/appointment/times/{current_facility}.json?date=%s&appointments[expedite]=false"
            sign_out_url = f"https://ais.usvisa-info.com/{current_embassy_region}/niv/users/sign_out"

            if not logged_in:
                do_login(sign_in_link)
                logged_in = True
            print("Checking Embassy: " + embassy)
            try:
                msg = "-" * 60 + f"\nRequest count: {request_count}, Log time: {datetime.today()}\n"
                print(msg)
                info_logger(LOG_FILE_NAME, msg)
                dates = get_date()
                if not dates:
                    # Possibly a ban.
                    empty_dates_count += 1
                    msg = f"List of dates is empty."
                    print(msg)
                    info_logger(LOG_FILE_NAME, msg)
                else:
                    # Print available dates.
                    msg = ""
                    for d in dates:
                        msg = msg + "%s" % (d.get('date')) + ", "
                    msg = "Available dates:\n"+ msg
                    print(msg)
                    info_logger(LOG_FILE_NAME, msg)
                    # Check and get a date within the timeframe specified by user.
                    date = get_available_date(dates)
                    if date:
                        # Load the sound file
                        sound = pygame.mixer.Sound("beep_beep.mp3")

                        # Play the sound
                        sound.play()

                        # Wait for the sound to finish playing
                        while pygame.mixer.get_busy():
                            pass
                        # A good date to schedule for
                        # Reschedule.
                        found_appointment = True
                        END_MSG_TITLE, msg = reschedule(date, appointment_url, time_url)
                        print(END_MSG_TITLE)
                        print(msg)
                        break

                    t1 = time.time()
                    total_time = t1 - t0
                    msg = "\nWorking Time:  ~ {:.2f} minutes".format(total_time/minute)
                    print(msg)
                    info_logger(LOG_FILE_NAME, msg)
                    if total_time > WORK_LIMIT_TIME * hour:
                        # Let program rest a little
                        driver.get(sign_out_url)
                        logged_in = False
                        time.sleep(WORK_COOLDOWN_TIME * hour)

                        #Login again and continue after waiting.
                        do_login(sign_in_link)
                        logged_in = True

                wait_time_between_embassy_checks = random.randint(CHECK_TIME_L_BOUND, CHECK_TIME_U_BOUND)
                msg = "Wait time between embassies: " + str(wait_time_between_embassy_checks) + " seconds\n"
                print(msg)
                info_logger(LOG_FILE_NAME, msg)
                time.sleep(wait_time_between_embassy_checks)

            except KeyboardInterrupt:
                kill_infinite_loop = True
                # Exception Occured
                msg = f"Break the loop after exception!\n"
                END_MSG_TITLE = "EXCEPTION"
                break
            except:
                # Exception Occured
                msg = f"Break the loop after exception!\n"
                END_MSG_TITLE = "EXCEPTION"
                break

        if (found_appointment):
            # Load the sound file
            sound = pygame.mixer.Sound("beep_beep.mp3")

            # Play the sound
            sound.play()

            # Wait for the sound to finish playing
            while pygame.mixer.get_busy():
                pass
            print("Found appointment. Now exiting.")
            break

        if empty_dates_count >= len(EMBASSIES_TO_CHECK):
            print("Finished executing, All embassy dates were empty will wait for 5 hours and run again.")
            time.sleep(60*60*5)
        else:
            print("Finished executing, will wait for 5 minutes and run again.")
            time.sleep(60*5)

        if kill_infinite_loop:
            break

    print("Exited loop.")
    print(msg)
    info_logger(LOG_FILE_NAME, msg)
    driver.get(sign_out_url)
    driver.stop_client()
    driver.quit()

# Quit pygame
pygame.quit()
