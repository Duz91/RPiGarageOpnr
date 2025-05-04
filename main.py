import subprocess
import time
import json
import os
import re
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf.csrf import CSRFProtect
from gpiozero import Button, LED, OutputDevice
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

# Flask Initialisierung
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Autogenerierter Schlüssel
csrf = CSRFProtect(app)

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

# Globale Variablen
config = load_config()
device_present = False

# GPIO Initialisierung
led = LED(config['led_pin'])
relay = OutputDevice(config['relay_pin'], active_high=False)
buzzer = OutputDevice(config['buzzer_pin'], active_high=False)
button = None

# Funktionen
def button_pressed():
    global device_present
    if device_present:
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
    while True:
        current_presence = any(check_device(mac) for mac in config['mac_addresses'])
        
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
    return render_template('index.html', 
                         device_present=device_present,
                         config=config)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global config, button
    
    if request.method == 'POST':
        try:
            new_config = {
                "mac_addresses": [m.strip() for m in request.form['mac_addresses'].split(',')],
                "scan_interval": int(request.form.get('scan_interval', 7)),
                "absence_interval": int(request.form.get('absence_interval', 15)),
                "relay_close_time": float(request.form.get('relay_close_time', 0.5)),
                "presence_beep_duration": float(request.form.get('presence_beep_duration', 0.1)),
                "presence_beep_count": int(request.form.get('presence_beep_count', 2)),
                "absence_beep_duration": float(request.form.get('absence_beep_duration', 0.1)),
                "absence_beep_count": int(request.form.get('absence_beep_count', 2)),
                "button_bounce_time": float(request.form.get('button_bounce_time', 0.2)),
                "presence_led_blink_interval": float(request.form.get('presence_led_blink_interval', 0.7)),
                "absence_led_blink_interval": float(request.form.get('absence_led_blink_interval', 1.2)),
                "led_pin": int(request.form.get('led_pin', 23)),
                "relay_pin": int(request.form.get('relay_pin', 26)),
                "buzzer_pin": int(request.form.get('buzzer_pin', 19)),
                "button_pin": int(request.form.get('button_pin', 5))
            }
        except ValueError as e:
            flash(f"Ungültige Eingabe: {str(e)}", "error")
            return redirect(url_for('settings'))
        
        # MAC-Adressen validieren
        mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
        for mac in new_config['mac_addresses']:
            if not mac_pattern.match(mac):
                flash(f"Ungültige MAC-Adresse: {mac}", "error")
                return redirect(url_for('settings'))
        
        save_config(new_config)
        config = new_config
        
        # GPIO neu initialisieren
        led.close()
        relay.close()
        buzzer.close()
        if button:
            button.close()
        
        led = LED(config['led_pin'])
        relay = OutputDevice(config['relay_pin'], active_high=False)
        buzzer = OutputDevice(config['buzzer_pin'], active_high=False)
        button = Button(config['button_pin'], 
                      pull_up=True, 
                      bounce_time=config['button_bounce_time'])
        button.when_pressed = button_pressed
        
        flash("Einstellungen erfolgreich gespeichert!", "success")
        return redirect(url_for('settings'))
    
    return render_template('settings.html',
                         mac_addresses=", ".join(config['mac_addresses']),
                         **config)

@app.route('/activate_relay')
def activate_relay():
    relay.on()
    time.sleep(config['relay_close_time'])
    relay.off()
    return "Relais aktiviert!"

if __name__ == '__main__':
    # GPIO Initialisierung
    button = Button(config['button_pin'], 
                  pull_up=True, 
                  bounce_time=config['button_bounce_time'])
    button.when_pressed = button_pressed
    
    # Threads starten
    threading.Thread(target=main_loop, daemon=True).start()
    threading.Thread(target=blink_led, daemon=True).start()
    
    # Webserver starten
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
