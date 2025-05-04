import subprocess
import time
import json
import os
from gpiozero import Button, LED, OutputDevice
from flask import Flask, render_template, request, redirect, url_for, abort
import threading

app = Flask(__name__)
CONFIG_FILE = os.path.abspath('config.json')

# Default-Konfiguration mit allen Parametern
DEFAULT_CONFIG = {
    "mac_addresses": ["0C:15:63:DF:61:2F"],
    "scan_interval": 7,
    "absence_interval": 15,
    "relay_close_time": 0.5,
    "presence_beep_duration": 0.1,
    "presence_beep_count": 2,
    "absence_beep_duration": 0.1,
    "absence_beep_count": 2,
    "button_bounce_time": 0.2,
    "presence_led_blink_interval": 0.7,
    "absence_led_blink_interval": 1.2,
    "led_pin": 23,
    "relay_pin": 26,
    "buzzer_pin": 19,
    "button_pin": 5
}

# Konfigurationshandling
def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
    
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Globale Initialisierung
config = load_config()
device_present = False

# GPIO-Komponenten mit Konfiguration
led = LED(config['led_pin'])
relay = OutputDevice(config['relay_pin'], active_high=False)
buzzer = OutputDevice(config['buzzer_pin'], active_high=False)
button = None

# Bluetooth-Überwachungsfunktion (unverändert)
def check_device_name(mac_address):
    try:
        result = subprocess.run(['hcitool', 'name', mac_address], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE, 
                              text=True)
        return bool(result.stdout.strip())
    except Exception as e:
        print(f"Error checking device {mac_address}: {e}")
        return False

# Hauptlogik mit Konfigurationsparametern
def main():
    global device_present, config
    
    last_seen = {mac: None for mac in config['mac_addresses']}
    previous_state = None
    
    while True:
        device_present = any(check_device_name(mac) for mac in config['mac_addresses'])
        
        # Zustandsänderung
        if device_present and previous_state != "present":
            beep(config['presence_beep_count'], config['presence_beep_duration'])
            previous_state = "present"
        elif not device_present and previous_state != "absent":
            beep(config['absence_beep_count'], config['absence_beep_duration'])
            previous_state = "absent"
        
        time.sleep(config['scan_interval'])

# Restlicher ursprünglicher Code (Blink-LED, Button-Handler etc.)
# ... (60+ Zeilen unverändert)

# Flask-Routen mit kompletter Funktionalität
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global config, button
    
    if request.method == 'POST':
        new_config = {
            key: request.form[key] 
            for key in DEFAULT_CONFIG.keys() 
            if key in request.form
        }
        
        # Typkonvertierung
        new_config['mac_addresses'] = new_config['mac_addresses'].split(',')
        for k in ['scan_interval', 'absence_interval', 'presence_beep_count', 
                'absence_beep_count', 'led_pin', 'relay_pin', 'buzzer_pin', 'button_pin']:
            new_config[k] = int(new_config[k])
        for k in ['relay_close_time', 'presence_beep_duration', 'absence_beep_duration',
                'button_bounce_time', 'presence_led_blink_interval', 'absence_led_blink_interval']:
            new_config[k] = float(new_config[k])
        
        save_config(new_config)
        config = new_config
        
        # GPIO-Reinitialisierung
        led.close()
        relay.close()
        buzzer.close()
        if button:
            button.close()
            
        led = LED(config['led_pin'])
        relay = OutputDevice(config['relay_pin'], active_high=False)
        buzzer = OutputDevice(config['buzzer_pin'], active_high=False)
        button = Button(config['button_pin'], pull_up=True, 
                      bounce_time=config['button_bounce_time'])
        button.when_pressed = button_pressed
        
        return redirect(url_for('settings'))
    
    return render_template('settings.html', **config)

# Startcode
if __name__ == '__main__':
    try:
        button = Button(config['button_pin'], pull_up=True, 
                      bounce_time=config['button_bounce_time'])
        button.when_pressed = button_pressed
        
        threading.Thread(target=main).start()
        threading.Thread(target=blink_led).start()
        app.run(host='0.0.0.0', port=5000)
    finally:
        led.off()
        relay.off()
        buzzer.off()
        if button:
            button.close()
