import subprocess
import time
from gpiozero import Button, LED, OutputDevice
from flask import Flask, render_template, request, redirect, url_for
import threading

BUTTON_PIN = 5
LED_PIN = 23
RELAY_PIN = 26
BUZZER_PIN = 19

mac_addresses = ["0C:15:63:DF:61:2F"]
scan_interval = 7
absence_interval = 15
relay_close_time = 0.5
presence_beep_duration = 0.1
presence_beep_count = 2
absence_beep_duration = 0.1
absence_beep_count = 2
button_bounce_time = 0.2
presence_led_blink_interval = 0.7
absence_led_blink_interval = 1.2

app = Flask(__name__)
device_present = False

led = LED(LED_PIN)
relay = OutputDevice(RELAY_PIN, active_high=False)
buzzer = OutputDevice(BUZZER_PIN, active_high=False)
button = None

def button_pressed():
    global device_present
    if device_present:
        relay.on()
        time.sleep(relay_close_time)
        relay.off()

def check_device_name(mac_address):
    try:
        result = subprocess.run(['hcitool', 'name', mac_address], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        return bool(result.stdout.strip())
    except Exception as e:
        print(f"Error checking {mac_address}: {e}")
        return False

def beep(times, duration):
    for _ in range(times):
        buzzer.on()
        time.sleep(duration)
        buzzer.off()
        time.sleep(duration)

def blink_led():
    global device_present
    while True:
        if device_present:
            led.blink(on_time=presence_led_blink_interval, 
                     off_time=presence_led_blink_interval)
        else:
            led.blink(on_time=absence_led_blink_interval, 
                     off_time=absence_led_blink_interval)
        time.sleep(0.1)

def main():
    global device_present
    last_seen = {mac: None for mac in mac_addresses}
    previous_state = None
    
    while True:
        current_presence = any(check_device_name(mac) for mac in mac_addresses)
        
        if current_presence != device_present:
            device_present = current_presence
            if device_present:
                beep(presence_beep_count, presence_beep_duration)
            else:
                beep(absence_beep_count, absence_beep_duration)
        
        time.sleep(scan_interval)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global mac_addresses, scan_interval, absence_interval, relay_close_time
    global presence_beep_duration, presence_beep_count, absence_beep_count
    global button_bounce_time, presence_led_blink_interval, absence_led_blink_interval
    
    if request.method == 'POST':
        mac_addresses = request.form.get('mac_addresses', '').split(',')
        scan_interval = int(request.form.get('scan_interval', 7))
        absence_interval = int(request.form.get('absence_interval', 15))
        relay_close_time = float(request.form.get('relay_close_time', 0.5))
        presence_beep_duration = float(request.form.get('presence_beep_duration', 0.1))
        presence_beep_count = int(request.form.get('presence_beep_count', 2))
        absence_beep_duration = float(request.form.get('absence_beep_duration', 0.1))
        absence_beep_count = int(request.form.get('absence_beep_count', 2))
        button_bounce_time = float(request.form.get('button_bounce_time', 0.2))
        presence_led_blink_interval = float(request.form.get('presence_led_blink_interval', 0.7))
        absence_led_blink_interval = float(request.form.get('absence_led_blink_interval', 1.2))

        if button:
            button.close()
        button = Button(BUTTON_PIN, pull_up=True, bounce_time=button_bounce_time)
        button.when_pressed = button_pressed
        
        return redirect(url_for('settings'))
    
    return render_template('settings.html',
                         mac_addresses=",".join(mac_addresses),
                         scan_interval=scan_interval,
                         absence_interval=absence_interval,
                         relay_close_time=relay_close_time,
                         presence_beep_duration=presence_beep_duration,
                         presence_beep_count=presence_beep_count,
                         absence_beep_duration=absence_beep_duration,
                         absence_beep_count=absence_beep_count,
                         button_bounce_time=button_bounce_time,
                         presence_led_blink_interval=presence_led_blink_interval,
                         absence_led_blink_interval=absence_led_blink_interval)

@app.route('/activate_relay')
def activate_relay():
    relay.on()
    time.sleep(relay_close_time)
    relay.off()
    return "Relay activated!"

if __name__ == '__main__':
    try:
        button = Button(BUTTON_PIN, pull_up=True, bounce_time=button_bounce_time)
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
