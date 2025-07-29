#!/usr/bin/env python
import pigpio
import time
import sys
import os
import argparse
# This is an attempt to create converter from flipper .ir files to work with pigpio
# I dont have oscilloscope or something to test this, so this is more for inspiration 
# === Configuration ===
GPIO_IR_LED = 17
MAX_PULSES = 5400
# =====================

# Frames for each protocol
def build_nec_frame(info):
    addr = hex_to_int_le(info.get("address", "00")) & 0xFF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return (
        addr |
        ((~addr & 0xFF) << 8) |
        (cmd << 16) |
        ((~cmd & 0xFF) << 24)
    )


def build_necext_frame(info):
    addr = hex_to_int_le(info.get("address", "0000")) & 0xFFFF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return (
        addr |
        (cmd << 16) |
        ((~cmd & 0xFF) << 24)
    )


def build_nec42_frame(info):
    addr = hex_to_int_le(info.get("address", "0000")) & 0x1FFF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return (
        addr |
        ((~addr & 0x1FFF) << 13) |
        (cmd << 26) |
        ((~cmd & 0xFF) << 34)
    )

def build_nec42ext_frame(info):
    addr = hex_to_int_le(info.get("address", "0000000")) & 0x3FFFFFF
    cmd  = hex_to_int_le(info.get("command", "0000")) & 0xFFFF
    return addr | (cmd << 26)

def build_samsung_frame(info):
    addr = hex_to_int_le(info.get("address", "0000")) & 0xFFFF
    cmd  = hex_to_int_le(info.get("command", "0000")) & 0xFFFF
    return addr | (cmd << 16)

def build_pioneer_frame(info):
    addr = hex_to_int_le(info.get("address", "00")) & 0xFF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return (
        addr |
        ((~addr & 0xFF) << 8) |
        (cmd << 16) |
        ((~cmd & 0xFF) << 24) |
        (1 << 32)  # Stop bit always there
    )
# Currently not supported
def build_kaseikyo_frame(info):
    addr = hex_to_int_le(info.get("address", "00")) & 0xFF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return (
        addr |
        ((~addr & 0xFF) << 8) |
        (cmd << 16) |
        ((~cmd & 0xFF) << 24) |
        (1 << 32)  # Stop bit always there
    )
# ======================
# Not sure about these, need to verify
def build_rc5_frame(info):
    toggle = 1  
    addr = hex_to_int_le(info.get("address", "00")) & 0x1F
    cmd  = hex_to_int_le(info.get("command", "00")) & 0x3F
    return (0b11 << 12) | (toggle << 11) | (addr << 6) | cmd

def build_rc5x_frame(info):
    toggle = 1
    addr = hex_to_int_le(info.get("address", "00")) & 0x7F  # 7-bit address
    cmd  = hex_to_int_le(info.get("command", "00")) & 0x3F

    start1 = 1
    start2 = (addr >> 6) & 0x1
    addr6 = addr & 0x3F

    return (start1 << 14) | (start2 << 13) | (toggle << 12) | (addr6 << 6) | cmd

def build_rc6_frame(info):
    toggle = 1
    addr = hex_to_int_le(info.get("address", "00")) & 0xFF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return (1 << 19) | (0b000 << 16) | (toggle << 15) | (addr << 7) | cmd
# =====================================
def build_rca_frame(info):
    addr = hex_to_int_le(info.get("address", "0")) & 0xF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return (
        addr |
        (cmd << 4) |
        ((~addr & 0xF) << 12) |
        ((~cmd & 0xFF) << 16)
    )
def build_sirc_frame(info):
    cmd  = hex_to_int_le(info.get("command", "00")) & 0x7F   
    addr = hex_to_int_le(info.get("address", "00")) & 0x1F   
    return cmd | (addr << 7)

def build_sirc15_frame(info):
    cmd  = hex_to_int_le(info.get("command", "00")) & 0x7F  
    addr = hex_to_int_le(info.get("address", "00")) & 0xFF 
    return cmd | (addr << 7)


def build_sirc20_frame(info):
    cmd  = hex_to_int_le(info.get("command", "00")) & 0x7F   
    addr = hex_to_int_le(info.get("address", "00")) & 0x1FFF 
    return cmd | (addr << 7)


# Protocol types
PROTOCOLS = {
    # NEC variants
    "nec": {
        "freq": 38000,
        "header": [(1, 9000), (0, 4500)],
        "bit0": [(1, 560), (0, 560)],
        "bit1": [(1, 560), (0, 1690)],
        "stop": [(1, 560)],
        "bit_order": "lsb",
        "bits": 32
    },
    "necext": {  # NEC extended (same timings, 16+8+8 bits)
        **{},  # same as "nec"
        **{"bits": 32}
    },
    "nec42": {  # NEC42: 42-bit frame, same base timings
        **{}, **{"bits": 42}
    },
    "nec42ext": {
        **{}, **{"bits": 42}# num of bits probably same, but different frame
    },
    # Samsung32 (also called Samsung SIRCS)
    "samsung32": {
        "freq": 38000,
        "header": [(1, 4500), (0, 4500)],
        "bit0": [(1, 550), (0, 550)],
        "bit1": [(1, 550), (0, 1690)],
        "stop": [(1, 550)],
        "bit_order": "lsb",
        "bits": 32
    },
    # RC5 and RC5X 
    "rc5": {
        "freq": 36000,
        "header": [],  # Manchester uses no separate header, but bits infront
        "bit0": [(1, 889), (0, 889)],
        "bit1": [(0, 889), (1, 889)],
        "stop": [],
        "bit_order": "msb",
        "bits": 14
    },
    "rc5x": {
        **{}, **{"bits": 15}  # extended, 15 bits total
    },
    # RC6 
    "rc6": {
        "freq": 36000,
        "header": [(1, 2666), (0, 889)],
        "bit0": [(0, 889), (1, 889)],
        "bit1": [(1, 889), (0, 889)],
        "stop": [],
        "bit_order": "msb",
        "bits": 20
    },
    # RCA
    "rca": {
        "freq": 56000,
        "header": [(1, 4000), (0, 4000)],
        "bit0": [(1, 500), (0, 1000)],
        "bit1": [(1, 500), (0, 2000)],
        "stop": [],
        "bit_order": "msb",
        "bits": 24
    },
    # Kaseikyo
    "kaseikyo": {
        "freq": 38000,
        "header": [(1, 1650), (0, 3360)],
        "bit0": [(1, 432), (0, 432)],
        "bit1": [(1, 432), (0, 1269)],
        "stop": [(1, 432)],
        "bit_order": "lsb",
        "bits": 48
    },
    # Pioneer
    "pioneer": {
        "freq": 40000,
        "header": [(1, 8500), (0, 4225)],
        "bit0": [(1, 500), (0, 500)],
        "bit1": [(1, 500), (0, 1500)],
        "stop": [],
        "bit_order": "lsb",
        "bits": 33
    },
    # Sony SIRC 12/15/20-bit
    "sirc": {
        "freq": 40000,
        "header": [(1, 2400), (0, 600)],
        "bit0": [(1, 600), (0, 600)],
        "bit1": [(1, 1200), (0, 600)],
        "stop": [],
        "bit_order": "lsb",
        "bits": 12
    },
    "sirc15": { **{}, **{"bits": 15} },
    "sirc20": { **{}, **{"bits": 20} },
}

FRAME_BUILDERS = {
    "nec": build_nec_frame,
    "necext": build_necext_frame,
    "nec42": build_nec42_frame,
    "nec42ext": build_nec42ext_frame,
    "samsung32": build_samsung_frame,
    "pioneer": build_pioneer_frame,
    "rc5": build_rc5_frame,
    "rc5x": build_rc5x_frame,
    "rc6": build_rc6_frame,
    "rca": build_rca_frame,
    "kaseikyo": build_kaseikyo_frame,
    "sirc": build_sirc_frame,
    "sirc15": build_sirc15_frame,
    "sirc20": build_sirc20_frame,
}

INHERITS = {
    "necext": "nec",
    "nec42": "nec",
    "nec42ext": "nec",
    "sirc15": "sirc",
    "sirc20": "sirc",
    "rc5x" : "rc5"
}

for key, base in INHERITS.items():
    inherited = PROTOCOLS[base].copy()
    inherited.update(PROTOCOLS[key])  # preserve overrides
    PROTOCOLS[key] = inherited
# ----------------------------------------------------------------------------
# Parse Flipper .ir file
def parse_ir_file(path):
    with open(path, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    entries = []
    current = {}
    in_data = False

    for line in lines:
        if line.startswith("#"):
            if current:
                if "type" in current and ("protocol" in current or "data" in current):
                    entries.append(current)
                current = {}
                in_data = False
            continue

        if in_data:
            try:
                current["data"].extend([int(x) for x in line.split() if x.isdigit()])
            except ValueError:
                pass
            continue

        if ":" in line:
            k, v = map(str.strip, line.split(":", 1))
            k = k.lower()

            if k == "data":
                current["data"] = []
                try:
                    current["data"].extend([int(x) for x in v.split() if x.isdigit()])
                except ValueError:
                    pass
                in_data = True
            else:
                current[k] = v

    # Catch last block
    if current and "type" in current and ("protocol" in current or "data" in current):
        entries.append(current)

    return entries

# ----------------------------------------------------------------------------
def hex_to_int_le(s):
    return int.from_bytes([int(x, 16) for x in s.split()], "little")

# ----------------------------------------------------------------------------
def send_parsed(info, pi, GPIO_IR_LED=17):
    name = info["name"]
    proto = info["protocol"].lower()
    cfg = PROTOCOLS.get(proto)
    if not cfg:
        print(f"[-] Unsupported protocol: {proto}")
        return
    builder = FRAME_BUILDERS.get(proto)
    if not builder:
        print(f"[-] No frame builder for protocol {proto}")
        return

    val = builder(info)
    bits = cfg["bits"]
    # Frame error handler if bits dont fit
    if val >= (1 << bits):
        print(f"[!] Warning: frame value 0x{val:X} exceeds expected {bits} bits")

    freq = cfg["freq"]
    cycle_us = 1_000_000 // freq
    on_us = int(cycle_us * 0.33)
    off_us = cycle_us - on_us

    def carrier(d):
        pulses = []
        n = max(1, round(d / cycle_us))
        for _ in range(n):
            pulses.append(pigpio.pulse(1<<GPIO_IR_LED, 0, on_us))
            pulses.append(pigpio.pulse(0, 1<<GPIO_IR_LED, off_us))
        return pulses

    def space(d):
        return [pigpio.pulse(0, 0, d)]

    def encode_bit(b):
        key = f"bit{b}"
        seq = cfg[key]
        return [carrier(t) if lvl else space(t) for lvl, t in seq]

    def flatten(lst):
        out = []
        for x in lst:
            if isinstance(x, list):
                out.extend(flatten(x))
            else:
                out.append(x)
        return out

    pulses = flatten([carrier(d) if lvl else space(d) for lvl, d in cfg["header"]])
    #bit order LSB or MSB 
    for i in range(bits):
        bit = (val >> i) & 1 if cfg["bit_order"] == "lsb" else (val >> (bits - 1 - i)) & 1
        pulses += flatten(encode_bit(bit))

    pulses += flatten([carrier(d) if lvl else space(d) for lvl, d in cfg.get("stop", [])])

    pi.set_mode(GPIO_IR_LED, pigpio.OUTPUT)
    pi.wave_add_new()
    if len(pulses) > MAX_PULSES:
      print(f"[!] Truncating raw '{name}' to first {MAX_PULSES} pulses")
      pulses = pulses[:MAX_PULSES]
    pi.wave_add_generic(pulses)
    wid = pi.wave_create()
    if wid >= 0:
        print(f"[+] Sending code: {name} ({proto.upper()})")
        pi.wave_send_once(wid)
        while pi.wave_tx_busy():
            time.sleep(0.001)
        pi.wave_delete(wid)
    else:
        print("[-] Wave creation failed")
# ----------------------------------------------------------------------------
def send_raw(info, pi, GPIO_IR_LED=17):
    name = info.get("name", "Unnamed")
    freq = int(info.get("frequency", 38000))
    dc   = float(info.get("duty_cycle", 0.33))
    data = info.get("data", [])

    if not data or len(data) < 2:
        print(f"[-] Raw code '{name}' has no usable data, skipping.")
        return

    cycle_us = 1_000_000 // freq
    on_us = int(cycle_us * dc)
    off_us = cycle_us - on_us

    def carrier(d):
        pulses = []
        n = max(1, round(d / cycle_us))
        for _ in range(n):
            pulses.append(pigpio.pulse(1 << GPIO_IR_LED, 0, on_us))
            pulses.append(pigpio.pulse(0, 1 << GPIO_IR_LED, off_us))
        return pulses

    def space(d):
        return [pigpio.pulse(0, 0, d)]

    pulses = []
    level = 1  # Start with carrier ON
    for d in data:
        if d <= 0:
            continue  # Skip nonsense
        pulses += carrier(d) if level else space(d)
        level ^= 1

    if not pulses:
        print(f"[-] Raw code '{name}' resulted in no pulses.")
        return

    pi.set_mode(GPIO_IR_LED, pigpio.OUTPUT)
    pi.wave_add_new()
    if len(pulses) > MAX_PULSES:
      print(f"[!] Truncating raw '{name}' to first {MAX_PULSES} pulses")
      pulses = pulses[:MAX_PULSES]
    pi.wave_add_generic(pulses)
    wid = pi.wave_create()
    if wid >= 0:
        print(f"[+] Sending raw code: {name}")
        pi.wave_send_once(wid)
        while pi.wave_tx_busy():
            time.sleep(0.001)
        pi.wave_delete(wid)
    else:
        print(f"[-] Wave creation failed for: {name}")


# ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Send IR codes from Flipper .ir file using pigpio")
    parser.add_argument("file", help="Path to the .ir file")
    parser.add_argument("name", nargs="?", help="Optional: send only code with this name")
    parser.add_argument("--list", action="store_true", help="List all available IR code names")
    parser.add_argument("--delay", type=int, default=0, help="Delay between codes when sending all (in milliseconds)")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"[-] File not found: {args.file}")
        return

    entries = parse_ir_file(args.file)
    if args.list:
        print("Available entries:")
        for entry in entries:
            print(f" - {entry.get('name', 'Unnamed')}")
        return

    name_filter = args.name.lower() if args.name else None
    delay_sec = args.delay / 1000.0 if args.delay else 0

    pi = pigpio.pi()
    if not pi.connected:
        print("[-] pigpiod not running?")
        return

    try:
        sent = False
        for entry in entries:
            name = entry.get("name", "").lower()
            if name_filter and name != name_filter:
                continue

            ir_type = entry.get("type", "").lower()
            if ir_type == "parsed":
                send_parsed(entry, pi)
            elif ir_type == "raw":
                send_raw(entry, pi)
            else:
                print(f"[-] Unknown IR file type in block: {name}")
                continue

            sent = True
            if delay_sec:
                time.sleep(delay_sec)

        if not sent:
            if name_filter:
                print(f"[-] No entry found with name: '{name_filter}'")
            else:
                print("[-] No valid IR entries found in file.")
    finally:
        pi.stop()


if __name__=="__main__":
    main()
