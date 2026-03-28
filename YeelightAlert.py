import time
import json
import os
import threading
import requests
import subprocess
import platform
import logging
import pystray
from PIL import Image, ImageDraw
from yeelight import Bulb, Flow, RGBTransition

# Constants
CONFIG_FILE = "pikud_config.json"
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
        logging.FileHandler("pikud_alerts.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class AlertSystem:
    def __init__(self):
        self.config = self.load_config()
        self.bulb_state = None
        self.active_siren = False
        self.release_timer = None
        self.monitor_thread = threading.Thread(target=self.monitor_api, daemon=True)
        self.running = True

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"ip": "", "location": ""}

    def save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def get_bulb(self):
        if not self.config.get("ip"):
            return None
        try:
            return Bulb(self.config["ip"])
        except Exception:
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
        while self.running:
            if not self.config.get("location"):
                time.sleep(5)
                continue

            try:
                response = requests.get(API_URL, headers=HEADERS, timeout=5)
                # API returns HTTP 200 with empty text when there are no alerts
                if response.status_code == 200 and response.text.strip():
                    data = response.json()
                    alerts = data.get("data", [])
                    title = data.get("title", "")

                    if self.config["location"] in alerts:
                        if "התרעה מקדימה" in title:
                            # Trigger only if we aren't already in a full red alert
                            if not self.active_siren:
                                self.trigger_early_warning()
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
                # Silently catch network errors to keep the background thread alive
                pass
            
            time.sleep(2)

    def test_connection(self):
        logging.info("Testing connection to Yeelight bulb...")
        bulb = self.get_bulb()
        if not bulb:
            logging.error("Test failed: Bulb IP not configured or invalid.")
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
