import time
import json
import os
import threading
import requests
import subprocess
import platform
import logging
from logging.handlers import RotatingFileHandler
import pystray
from PIL import Image, ImageDraw
from yeelight import Bulb, Flow, RGBTransition

# Constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "pikud_config.json")
API_URL = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
HEADERS = {
    "Referer": "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
RELEASE_TIMEOUT_SECONDS = 600  # 10 Minutes official release time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "pikud_alerts.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Setup verbose API logger
api_logger = logging.getLogger("api_updates")
api_logger.setLevel(logging.INFO)
api_handler = RotatingFileHandler(
    os.path.join(BASE_DIR, "API_updates.log"),
    maxBytes=10*1024*1024,  # 10 MB limit per file
    backupCount=5,          # Keep up to 5 old log files
    encoding='utf-8'
)
api_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
api_logger.propagate = False  # Prevent these logs from bleeding into the main pikud_alerts.log
api_logger.addHandler(api_handler)

class AlertSystem:
    def __init__(self):
        self.config = self.load_config()
        self.bulb_state = None
        self.active_siren = False
        self.last_early_warning_time = 0
        self.release_timer = None
        self.monitor_thread = threading.Thread(target=self.monitor_api, daemon=True)
        self.running = True

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"ip": "", "location": "", "verbose_api_log": False}

    def save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def get_bulb(self):
        if not self.config.get("ip"):
            return None
        try:
            return Bulb(self.config["ip"])
        except Exception as e:
            logging.error(f"Failed to initialize bulb at {self.config.get('ip')}: {e}")
            return None

    def save_bulb_state(self):
        bulb = self.get_bulb()
        if bulb:
            try:
                self.bulb_state = bulb.get_properties()
            except Exception as e:
                logging.error(f"Failed to get bulb state: {e}")

    def restore_bulb_state(self):
        if not self.bulb_state:
            return
            
        bulb = self.get_bulb()
        if not bulb:
            return

        try:
            if self.bulb_state.get('power') == 'off':
                bulb.turn_off()
                return
            
            bulb.turn_on()
            color_mode = self.bulb_state.get('color_mode')
            
            # Restore based on previous color mode (1: RGB, 2: Color Temp, 3: HSV)
            if color_mode == '1' and self.bulb_state.get('rgb'):
                rgb = int(self.bulb_state.get('rgb'))
                r = (rgb >> 16) & 0xFF
                g = (rgb >> 8) & 0xFF
                b = rgb & 0xFF
                bulb.set_rgb(r, g, b)
            elif color_mode == '2' and self.bulb_state.get('ct'):
                bulb.set_color_temp(int(self.bulb_state.get('ct')))
                
            if self.bulb_state.get('current_brightness'):
                bulb.set_brightness(int(self.bulb_state.get('current_brightness')))
                
        except Exception as e:
            logging.error(f"Failed to restore bulb state: {e}")

    def trigger_early_warning(self):
        bulb = self.get_bulb()
        if not bulb: return
        
        logging.info("Notification (התרעה מקדימה) received. Triggering Early Warning (Blinking Blue)...")
        # Yeelight's Flow with "recover" action naturally restores the bulb's previous state
        flow = Flow(
            count=10, 
            action=Flow.actions.recover,
            transitions=[
                RGBTransition(0, 0, 255, duration=500, brightness=100),
                RGBTransition(0, 0, 255, duration=500, brightness=1)
            ]
        )
        try:
            if bulb.get_properties().get('power') == 'off':
                bulb.turn_on()
            bulb.start_flow(flow)
        except Exception as e:
            logging.error(f"Error starting flow: {e}")

    def trigger_siren(self):
        if not self.active_siren:
            logging.info("Siren received. Triggering Siren (Red)...")
            self.save_bulb_state()
            self.active_siren = True

        bulb = self.get_bulb()
        if bulb:
            try:
                bulb.turn_on()
                bulb.set_rgb(255, 0, 0)
                bulb.set_brightness(100)
            except Exception as e:
                logging.error(f"Error turning bulb red: {e}")

    def handle_release(self):
        logging.info("Official release time reached. Restoring bulb state.")
        self.active_siren = False
        self.restore_bulb_state()

    def monitor_api(self):
        siren_in_api = False
        api_connected = False
        while self.running:
            if not self.config.get("location"):
                time.sleep(5)
                continue

            try:
                response = requests.get(API_URL, headers=HEADERS, timeout=5)

                # Pikud Ha'Oref API sometimes returns just a BOM (\ufeff) when there are no alerts.
                clean_text = response.text.replace('\ufeff', '').strip()
                data = {}
                if response.status_code == 200 and clean_text:
                    data = json.loads(clean_text)

                    if self.config.get("verbose_api_log"):
                        api_logger.info(json.dumps(data, ensure_ascii=False))

                if response.status_code == 200 and not api_connected:
                    logging.info("Successfully connected to Pikud Ha'Oref API. Monitoring active.")
                    api_connected = True

                if data:
                    alerts = data.get("data", [])
                    title = data.get("title", "")
                    desc = data.get("desc", "")

                    # The message targets our exact configured location OR our location is mentioned in the text
                    location_matched = self.config["location"] in alerts or self.config["location"] in desc or self.config["location"] in title

                    if location_matched:
                        if "מקדימה" in title or "מקדימה" in desc:
                            # Trigger only if we aren't already in a full red alert and haven't triggered in the last 2 minutes
                            if not self.active_siren and (time.time() - self.last_early_warning_time > 120):
                                self.last_early_warning_time = time.time()
                                self.trigger_early_warning()
                        elif "הסתיים" in title or "הסתיים" in desc:
                            if self.active_siren:
                                logging.info("Received official 'All Clear' (האירוע הסתיים). Releasing early.")
                                if self.release_timer:
                                    self.release_timer.cancel()
                                    self.release_timer = None
                                self.handle_release()
                                siren_in_api = False
                        else:
                            self.trigger_siren()
                            siren_in_api = True
                            # Cancel release timer if it was running (in case of a new alert)
                            if self.release_timer:
                                self.release_timer.cancel()
                                self.release_timer = None
                        
                        time.sleep(2)
                        continue
                
                # If we were in a siren but the location is no longer in the API alerts
                if self.active_siren and siren_in_api:
                    logging.info(f"Alert removed from API. Waiting {RELEASE_TIMEOUT_SECONDS} seconds for official release.")
                    siren_in_api = False
                    self.release_timer = threading.Timer(RELEASE_TIMEOUT_SECONDS, self.handle_release)
                    self.release_timer.start()

            except Exception as e:
                if api_connected:
                    logging.warning(f"Lost connection to Pikud Ha'Oref API: {e}. Retrying in background...")
                    api_connected = False
            
            time.sleep(2)

    def test_connection(self):
        logging.info("Testing connection to Yeelight bulb...")
        # Automatically reload the config before testing
        self.config = self.load_config()
        bulb = self.get_bulb()
        if not bulb:
            logging.error(f"Test failed: Bulb IP '{self.config.get('ip')}' not configured or unreachable.")
            return
            
        try:
            # Flashes green 3 times to indicate success
            flow = Flow(
                count=3, 
                action=Flow.actions.recover,
                transitions=[
                    RGBTransition(0, 255, 0, duration=500, brightness=100),
                    RGBTransition(0, 255, 0, duration=500, brightness=1)
                ]
            )
            if bulb.get_properties().get('power') == 'off':
                bulb.turn_on()
            bulb.start_flow(flow)
            logging.info("Test successful: Bulb flashed green.")
        except Exception as e:
            logging.error(f"Test failed: Error communicating with bulb: {e}")

    def start(self):
        self.monitor_thread.start()

    def stop(self):
        self.running = False
        if self.release_timer:
            self.release_timer.cancel()

# --- System Tray Setup ---

def create_image():
    # Creates a target icon with a transparent background
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    
    # Outer ring
    dc.ellipse((4, 4, 60, 60), outline=(255, 0, 0, 255), width=6)
    # Inner dot
    dc.ellipse((24, 24, 40, 40), fill=(255, 0, 0, 255))
    # Crosshairs
    dc.line((32, 0, 32, 20), fill=(255, 0, 0, 255), width=4)
    dc.line((32, 44, 32, 64), fill=(255, 0, 0, 255), width=4)
    dc.line((0, 32, 20, 32), fill=(255, 0, 0, 255), width=4)
    dc.line((44, 32, 64, 32), fill=(255, 0, 0, 255), width=4)
    return image

def edit_config(icon, item):
    # Ensure config file exists before opening
    if not os.path.exists(CONFIG_FILE):
        alert_system.save_config()
        
    # Open the file in the default text editor
    if platform.system() == 'Windows':
        os.startfile(CONFIG_FILE)
    elif platform.system() == 'Darwin':
        subprocess.call(('open', CONFIG_FILE))
    else:
        subprocess.call(('xdg-open', CONFIG_FILE))

def reload_config(icon, item):
    alert_system.config = alert_system.load_config()
    logging.info("Configuration reloaded.")

def test_config(icon, item):
    alert_system.test_connection()

def quit_app(icon, item):
    alert_system.stop()
    icon.stop()

if __name__ == "__main__":
    alert_system = AlertSystem()
    alert_system.start()

    # Define system tray menu
    menu = pystray.Menu(
        pystray.MenuItem("Edit Configuration", edit_config),
        pystray.MenuItem("Reload Configuration", reload_config),
        pystray.MenuItem("Test Configuration", test_config),
        pystray.MenuItem("Quit", quit_app)
    )

    icon = pystray.Icon("PikudMonitor", create_image(), "Pikud Ha'Oref Monitor", menu)
    
    # icon.run() blocks the main thread and keeps the background process alive
    icon.run()
