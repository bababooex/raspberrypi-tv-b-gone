import pigpio
import time
import json
import os
#Python script, that sends universal TV codes with external IR led
# === Configuration ===
GPIO_IR_LED = 17  # I use this pin for TX
CODES_FILE = "old_codes.txt"
# =====================

pi = pigpio.pi()

def send_ir_code(code_data):
    freq = code_data.get("freq", 38000)
    repeat = code_data.get("repeat", 1)
    repeat_delay = code_data.get("repeat_delay", 0)
    delay_after = code_data.get("delay", 0)

    table = code_data["table"]
    index = code_data["index"]

    
    pulses = []
    for i in index:
        pulses += table[i]
    if len(pulses) % 2 != 0:
        pulses = pulses[:-1]

    carrier_period = 1_000_000 / freq  
    carrier_on = int(carrier_period / 3)
    carrier_off = int(carrier_period - carrier_on)

    for _ in range(repeat):
        wf = []
        for i in range(0, len(pulses), 2):
            on_us = pulses[i]
            off_us = pulses[i+1]

            cycles = int(on_us / carrier_period)
            for _ in range(cycles):
                wf.append(pigpio.pulse(1 << GPIO_IR_LED, 0, carrier_on))
                wf.append(pigpio.pulse(0, 1 << GPIO_IR_LED, carrier_off))

            wf.append(pigpio.pulse(0, 0, off_us))  

        pi.set_mode(GPIO_IR_LED, pigpio.OUTPUT)
        pi.wave_clear()
        pi.wave_add_generic(wf)
        wave_id = pi.wave_create()
        if wave_id >= 0:
            pi.wave_send_once(wave_id)
            while pi.wave_tx_busy():
                time.sleep(0.01)
            pi.wave_delete(wave_id)
        time.sleep(repeat_delay)

    time.sleep(delay_after)

def load_and_send(file_path):
    with open(file_path, "r") as f:
        for line in f:
            try:
                code = eval(line.strip()) 
                print(f"Sending code: {code.get('freq')}Hz")
                send_ir_code(code)
            except Exception as e:
                print("Error:", e)
                
def send_micropython_format(codes):
    for name, *pulses in codes:
        print(f"Sending {name} with 38kHz")
        send_ir_code({
            "freq": 38000,
            "repeat": 1,
            "repeat_delay": 0,
            "delay": 0.1,
            "table": [pulses[i:i+2] for i in range(0, len(pulses), 2)], 
            "index": list(range(len(pulses)//2)),
        })


# === Main ===
if __name__ == "__main__":
    try:
        load_and_send(CODES_FILE)  
        import new_codes
        send_micropython_format(new_codes.CODES)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        pi.stop()

