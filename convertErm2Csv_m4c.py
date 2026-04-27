import struct
import csv
import glob
import os

# M4C Protocol Metadata
PARAMETERS = {
    "RPM": {"len": 2, "fmt": "<H"},
    "throttlePosition": {"len": 4, "fmt": "<f"},
    "crankPressure": {"len": 1, "fmt": "<B"},
    "ignitionAdvance": {"len": 4, "fmt": "<f"},
    "powerValve": {"len": 1, "fmt": "<B"},
    "coolantTemp": {"len": 2, "fmt": "<h"},
    "ambientTemp": {"len": 2, "fmt": "<h"},
    "ambientPressure": {"len": 1, "fmt": "<B"},
    "batteryVoltage": {"len": 4, "fmt": "<f"},
    "currentMap": {"len": 1, "fmt": "<B"}
}

ENTRIES = {
    2000: ["RPM", "throttlePosition", "crankPressure", "ignitionAdvance", "powerValve"],
    2001: ["coolantTemp", "ambientTemp", "ambientPressure", "batteryVoltage", "currentMap"]
}

def c_to_f(c):
    return (c * 9/5) + 32

def process_file(bin_path):
    # Use a temporary name initially
    temp_csv = bin_path.replace('.bin', '_temp.csv')
    current_state = {name: 0 for name in PARAMETERS.keys()}
    detected_map = None
    rows_written = 0
    
    try:
        with open(bin_path, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"Error opening {bin_path}: {e}")
        return

    start_idx = data.find(b'data')
    if start_idx == -1:
        return

    cursor = start_idx + 4
    
    with open(temp_csv, 'w', newline='') as csvfile:
        headers = ["RPM", "throttlePosition", "crankPressure", "ignitionAdvance", 
                   "powerValve", "coolantTemp_F", "ambientTemp_F", "ambientPressure_kPa", "batteryVoltage"]
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()

        while cursor < len(data) - 20:
            marker = data[cursor]
            
            if marker == 0xD0:
                msg_id = 2000
                payload_ptr = cursor + 2
            elif marker == 0xD1:
                msg_id = 2001
                payload_ptr = cursor + 2
            else:
                cursor += 1
                continue

            try:
                params = ENTRIES.get(msg_id, [])
                for p_name in params:
                    p_meta = PARAMETERS[p_name]
                    val = struct.unpack_from(p_meta["fmt"], data, payload_ptr)[0]
                    current_state[p_name] = val
                    payload_ptr += p_meta["len"]
                
                # Capture the map ID from the Non-Rapid packet
                if msg_id == 2001 and detected_map is None:
                    detected_map = current_state["currentMap"]

                if msg_id == 2000:
                    if 500 < current_state["RPM"] < 10000:
                        row = {
                            "RPM": current_state["RPM"],
                            "throttlePosition": int(round(current_state["throttlePosition"])),
                            "crankPressure": current_state["crankPressure"],
                            "ignitionAdvance": round(current_state["ignitionAdvance"], 2),
                            "powerValve": current_state["powerValve"],
                            "coolantTemp_F": round(c_to_f(current_state["coolantTemp"]), 1),
                            "ambientTemp_F": round(c_to_f(current_state["ambientTemp"]), 1),
                            "ambientPressure_kPa": current_state["ambientPressure"],
                            "batteryVoltage": round(current_state["batteryVoltage"], 2)
                        }
                        writer.writerow(row)
                        rows_written += 1
                
                cursor = payload_ptr
            except Exception:
                cursor += 1

    # Finalize filename based on detected map
    if rows_written > 0:
        map_val = detected_map if detected_map is not None else 0
        final_name = bin_path.replace('.bin', f'_m{map_val}.csv')
        
        # If file already exists (e.g. from a previous run), remove it
        if os.path.exists(final_name):
            os.remove(final_name)
            
        os.rename(temp_csv, final_name)
        print(f"Converted {bin_path} -> {final_name} ({rows_written} rows)")
    else:
        # Cleanup if no data was found
        if os.path.exists(temp_csv):
            os.remove(temp_csv)
        print(f"Skipped {bin_path}: No valid data rows found.")

if __name__ == "__main__":
    files = glob.glob("log*.bin")
    for f in files:
        process_file(f)