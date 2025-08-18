import pigpio
import sys
import time
import os
# This is an attempt to create converter from flipper .ir files to work with pigpio
# Tested protocols have OK above them, the test was done using Arduino-IRremote library
# === Configuration ===
GPIO_IR_LED = 17
MAX_PULSES = 5400
# =====================

# Frames for each protocol
#OK
def build_nec_frame(info):
    addr = hex_to_int_le(info.get("address", "00")) & 0xFF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return (
        addr |
        ((~addr & 0xFF) << 8) |
        (cmd << 16) |
        ((~cmd & 0xFF) << 24)
    )

# Probably OK
def build_necext_frame(info):
    addr = hex_to_int_le(info.get("address", "0000")) & 0xFFFF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return (
        addr |
        (cmd << 16) |
        ((~cmd & 0xFF) << 24)
    )

#OK
def build_nec42_frame(info):
    addr = hex_to_int_le(info.get("address", "0000")) & 0x1FFF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return (
        addr |
        ((~addr & 0x1FFF) << 13) |
        (cmd << 26) |
        ((~cmd & 0xFF) << 34)
    )
# Probably OK
def build_nec42ext_frame(info):
    addr = hex_to_int_le(info.get("address", "0000000")) & 0x3FFFFFF
    cmd  = hex_to_int_le(info.get("command", "0000")) & 0xFFFF
    return addr | (cmd << 26)
#OK
def build_samsung_frame(info):
    addr = hex_to_int_le(info.get("address", "0000")) & 0xFFFF
    cmd  = hex_to_int_le(info.get("command", "0000")) & 0xFFFF
    return addr | (cmd << 16)
# Not sure
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

# This is hell, but works
def build_kaseikyo_frame(info):
    vendor = hex_to_int_le(info.get("vendor", "0220")) & 0xFFFF
    address = hex_to_int_le(info.get("address", "0000")) & 0xFFF
    command = hex_to_int_le(info.get("command", "00")) & 0xFF
    # vedor parity
    vendor_parity = vendor ^ (vendor >> 8)
    vendor_parity = (vendor_parity ^ (vendor_parity >> 4)) & 0xF

    # addr+vendor parity
    addr_parity_word = (address << 4) | vendor_parity

    # extracting bytes
    byte2 = addr_parity_word & 0xFF
    byte3 = (addr_parity_word >> 8) & 0xFF

    # cmd
    byte4 = command & 0xFF

    # final parity
    byte5 = command ^ byte2 ^ byte3

    # everything packed together
    return( vendor | (addr_parity_word << 16) | (byte4 << 32) | (byte5 << 40))

# OK
def build_rc5_frame(info):
    toggle = 1
    addr = hex_to_int_le(info.get("address", "00")) & 0x1F
    cmd  =    hex_to_int_le(info.get("command", "00")) & 0x3F
    return (0b11 << 12) | (toggle << 11) | (addr << 6) | cmd
# Not sure
def build_rc5x_frame(info):
    toggle = 1
    addr = hex_to_int_le(info.get("address", "00")) & 0x1F  # 7-bit address
    cmd  = hex_to_int_le(info.get("command", "00")) & 0x7F
    frame = (0b11 << 13) | (toggle << 12) | (addr << 7) | cmd
    frame ^= (1 << 6) # 7th bit inverted
    return frame
# OK
def build_rc6_frame(info):
    toggle = 1
    addr = hex_to_int_le(info.get("address", "00")) & 0xFF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return (1 << 20) | (0b000 << 17) | (toggle << 16) | (addr << 8) | cmd
# Probably OK
def build_rca_frame(info):
    addr = hex_to_int_le(info.get("address", "0")) & 0xF
    cmd  = hex_to_int_le(info.get("command", "00")) & 0xFF
    return  (addr << 20) | (cmd << 12) | ((~addr & 0xF) << 8) | (~cmd & 0xFF)
#OK
def build_sirc_frame(info):
    cmd  = hex_to_int_le(info.get("command", "00")) & 0x7F
    addr = hex_to_int_le(info.get("address", "00")) & 0x1F
    return cmd | (addr << 7)
#OK
def build_sirc15_frame(info):
    cmd  = hex_to_int_le(info.get("command", "00")) & 0x7F
    addr = hex_to_int_le(info.get("address", "00")) & 0xFF
    return cmd | (addr << 7)
#OK
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
        "bit0": [(0, 444), (1, 444)],
        "bit1": [(1, 444), (0, 444)],
        "stop": [],
        "bit_order": "msb",
        "bits": 21
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
        "freq": 37000,
        "header": [(1, 3456), (0, 1728)],
        "bit0": [(1, 432), (0, 432)],
        "bit1": [(1, 432), (0, 1296)],
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

def send_wave_chained(pi, pin, pulses, max_chunk_len=5400, max_chain_length=6):
    pi.set_mode(pin, pigpio.OUTPUT)
    pi.write(pin, 0)
    pi.wave_clear()

    idx = 0
    total_len = len(pulses)

    while idx < total_len:
        wave_ids = []

        for _ in range(max_chain_length):
            if idx >= total_len:
                break

            chunk = pulses[idx:idx + max_chunk_len]
            pi.wave_add_generic(chunk)
            wave_id = pi.wave_create()
            if wave_id < 0:
                raise RuntimeError("No more wave control blocks available")

            wave_ids.append(wave_id)
            idx += len(chunk)

        if wave_ids:
            chain = []
            for wid in wave_ids:
                chain += [255, 0, wid]

            pi.wave_chain(chain)
            while pi.wave_tx_busy():
                pass

            for wid in wave_ids:
                pi.wave_delete(wid)

    pi.write(pin, 0)
    pi.wave_clear()
# ----------------------------------------------------------------------------
def hex_to_int_le(s):
    s = s.strip()
    if " " not in s:
        # treat as full hex number, not bytes
        return int(s, 16)
    return int.from_bytes([int(x, 16) for x in s.split()], "little")

# ----------------------------------------------------------------------------
def send_parsed(info, pi, pin=17, chain_len=6):
    name = info["name"]
    proto = info["protocol"].lower()
    cfg = PROTOCOLS.get(proto)
    if not cfg:
        print(f"Unsupported protocol: {proto}")
        return
    builder = FRAME_BUILDERS.get(proto)
    if not builder:
        print(f"No frame builder for protocol {proto}")
        return

    val = builder(info)
    bits = cfg["bits"]
    if val >= (1 << bits):
        print(f"Warning: frame value 0x{val:X} exceeds expected {bits} bits")

    freq = cfg["freq"]
    cycle_us = 1_000_000 // freq
    on_us = int(cycle_us * 0.33)
    off_us = cycle_us - on_us

    def carrier(d):
        pulses = []
        n = max(1, round(d / cycle_us))
        for _ in range(n):
            pulses.append(pigpio.pulse(1 << pin, 0, on_us))
            pulses.append(pigpio.pulse(0, 1 << pin, off_us))
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
    # Special toggle bit for rc6
    if proto == "rc6":
      unit = 444
      bits = 20
      pulses = []
      pulses += flatten([carrier(2666), space(889)])
      pulses += flatten([carrier(unit), space(unit)])
      for i in range(bits):
        bit = (val >> (bits - 1 - i)) & 1
        t = unit * 2 if i == 3 else unit
        if bit:
            pulses += flatten([carrier(t), space(t)])
        else:
            pulses += flatten([space(t), carrier(t)])

    for i in range(bits):
        bit = (val >> i) & 1 if cfg["bit_order"] == "lsb" else (val >> (bits - 1 - i)) & 1
        pulses += flatten(encode_bit(bit))
    pulses += flatten([carrier(d) if lvl else space(d) for lvl, d in cfg.get("stop", [])])


    print(f"Sending code named {name} via {proto.upper()} protocol with {len(pulses)} pulses")
    send_wave_chained(pi, pin, pulses, MAX_PULSES, chain_len)
# ----------------------------------------------------------------------------
def send_raw(info, pi, pin=17, chain_len=6):
    name = info.get("name", "Unnamed")
    freq = int(info.get("frequency", 38000))
    dc   = float(info.get("duty_cycle", 0.33))
    data = info.get("data", [])

    if not data or len(data) < 2:
        print(f"Raw code '{name}' has no usable data, skipping.")
        return

    cycle_us = 1_000_000 // freq
    on_us = int(cycle_us * dc)
    off_us = cycle_us - on_us

    def carrier(d):
        pulses = []
        n = max(1, round(d / cycle_us))
        for _ in range(n):
            pulses.append(pigpio.pulse(1 << pin, 0, on_us))
            pulses.append(pigpio.pulse(0, 1 << pin, off_us))
        return pulses

    def space(d):
        return [pigpio.pulse(0, 0, d)]

    pulses = []
    level = 1
    for d in data:
        if d <= 0:
            continue
        pulses += carrier(d) if level else space(d)
        level ^= 1

    if not pulses:
        print(f"Raw code '{name}' resulted in no pulses.")
        return

    print(f"Sending raw code named {name} with {len(pulses)} pulses")
    send_wave_chained(pi, pin, pulses, MAX_PULSES, chain_len)
# ----------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Single name: python3 irconv.py /path/to/file.ir <name> <chain_len> <gpio_pin>")
        print("  Bruteforce all: python3 irconv.py /path/to/file.ir <chain_len> <gpio_pin> <delay_ms>")
        print("  Name bruteforce: python3 irconv.py file.ir <name> <chain_len> <gpio_pin> <delay_ms>")
        sys.exit(1)
    delay_ms = 0 # Prevent unbound value
    ir_path = sys.argv[1]
    name_filter = None
    args = sys.argv[2:]

    if args and not args[0].isdigit():
        name_filter = args[0].lower()
        if len(args) >= 2:
            chain_len = int(args[1])
        if len(args) >= 3:
            gpio_pin = int(args[2])
        if len(args) >= 4:
            delay_ms = int(args[3])

    else:
        if len(args) >= 1:
            chain_len = int(args[0])
        if len(args) >= 2:
            gpio_pin = int(args[1])
        if len(args) >= 3:
            delay_ms = int(args[2])
        if delay_ms == 0:
            print("In bruteforce-all mode, you must provide a non-zero delay (ms)")
            sys.exit(1)

    delay_sec = delay_ms / 1000.0 if delay_ms else 0

    entries = parse_ir_file(ir_path)
    pi = pigpio.pi()

    try:
        sent = False
        for entry in entries:
            name = entry.get("name", "").lower()

            if name_filter:
                if delay_ms == 0:
                    if name != name_filter:
                        continue
                else:
                    if name != name_filter:
                        continue

            ir_type = entry.get("type", "").lower()
            if ir_type == "parsed":
                send_parsed(entry, pi, gpio_pin, chain_len)
            elif ir_type == "raw":
                send_raw(entry, pi, gpio_pin, chain_len)
            else:
                print(f"Unknown IR file type in block.")
                continue

            sent = True
            if delay_sec:
                time.sleep(delay_sec)

        if not sent:
            if name_filter:
                print(f"No entry found with name: '{name_filter}'")
            else:
                print("No valid IR entries found in file.")
    finally:
        pi.stop()



if __name__=="__main__":
    try:
        main()
    except KeyboardInterrupt: # Good for bruteforce mode
        print("\nInterrupted by user.")
