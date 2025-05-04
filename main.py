import subprocess
import time
import json
import os
from gpiozero import Button, LED, OutputDevice
from flask import Flask, render_template, request, redirect, url_for
import threading

# Konfigurationsdatei
CONFIG_FILE = os.path.abspath('config.json')

# Default-Konfiguration
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

# Konfiguration laden
def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
    
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Globale Variablen
config = load_config()
device_present = False
app = Flask(__name__)

# GPIO Initialisierung
led = LED(config['led_pin'])
relay = OutputDevice(config['relay_pin'], active_high=False)
buzzer = OutputDevice(config['buzzer_pin'], active_high=False)
button = None

# Funktionen
def button_pressed():
    global device_present
    print("Taster gedrückt!")
    if device_present:
        print("Aktiviere Relais...")
        relay.on()
        time.sleep(config['relay_close_time'])
        relay.off()

def check_device(mac):
    try:
        result = subprocess.run(['hcitool', 'name', mac],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               text=True,
                               timeout=5)
        return bool(result.stdout.strip())
    except Exception as e:
        print(f"Fehler bei {mac}: {str(e)}")
        return False

def beep(times, duration):
    for _ in range(times):
        buzzer.on()
        time.sleep(duration)
        buzzer.off()
        time.sleep(duration)

def blink_led():
    global device_present, config
    while True:
        if device_present:
            led.blink(on_time=config['presence_led_blink_interval'],
                     off_time=config['presence_led_blink_interval'])
        else:
            led.blink(on_time=config['absence_led_blink_interval'],
                     off_time=config['absence_led_blink_interval'])
        time.sleep(0.1)

def main_loop():
    global device_present, config
    last_seen = {mac: None for mac in config['mac_addresses']}
    previous_state = None
    
    while True:
        current_presence = any(check_device(mac) for mac in config['mac_addresses'])
        print(f"Scanning... Gefundene Geräte: {current_presence}")
        
        if current_presence != device_present:
            device_present = current_presence
            if device_present:
                beep(config['presence_beep_count'], config['presence_beep_duration'])
            else:
                beep(config['absence_beep_count'], config['absence_beep_duration'])
        
        time.sleep(config['scan_interval'])

# Flask-Routen
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global config, button
    
    if request.method == 'POST':
        new_config = {
            'mac_addresses': request.form['mac_addresses'].split(','),
            'scan_interval': int(request.form['scan_interval']),
            'absence_interval': int(request.form['absence_interval']),
            'relay_close_time': float(request.form['relay_close_time']),
            'presence_beep_duration': float(request.form['presence_beep_duration']),
            'presence_beep_count': int(request.form['presence_beep_count']),
            'absence_beep_duration': float(request.form['absence_beep_duration']),
            'absence_beep_count': int(request.form['absence_beep_count']),
            'button_bounce_time': float(request.form['button_bounce_time']),
            'presence_led_blink_interval': float(request.form['presence_led_blink_interval']),
            'absence_led_blink_interval': float(request.form['absence_led_blink_interval'])
        }
        
        save_config(new_config)
        config.update(new_config)
        
        # GPIO neu initialisieren
        button.close() if button else None
        button = Button(config['button_pin'], 
                      pull_up=True, 
                      bounce_time=config['button_bounce_time'])
        button.when_pressed = button_pressed
        
        return redirect(url_for('settings'))
    
    return render_template('settings.html',
                         mac_addresses=",".join(config['mac_addresses']),
                         **{k: v for k, v in config.items() if k != 'mac_addresses'})

@app.route('/activate_relay')
def activate_relay():
    relay.on()
    time.sleep(config['relay_close_time'])
    relay.off()
    return "Relais aktiviert!"

if __name__ == '__main__':
    # Wichtig: use_reloader=False verhindert Doppelausführung
    button = Button(config['button_pin'], 
                  pull_up=True, 
                  bounce_time=config['button_bounce_time'])
    button.when_pressed = button_pressed
    
    threading.Thread(target=main_loop, daemon=True).start()
    threading.Thread(target=blink_led, daemon=True).start()
    
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
