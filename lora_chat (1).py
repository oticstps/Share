import serial
import threading
import time
import sys

# === Konfigurasi Sesuai Permintaan ===
BAUDRATE = 2400
TIMEOUT = 2
WRITE_TIMEOUT = 2
ACK_TIMEOUT = 8
MAX_RETRIES = 3

if len(sys.argv) < 3:
    print("Penggunaan: python lora_chat_2400.py <laptop1|laptop2> <port_serial>")
    print("Contoh: python lora_chat_2400.py laptop1 COM4")
    sys.exit(1)

role = sys.argv[1]
serial_port = sys.argv[2]
peer = "laptop2" if role == "laptop1" else "laptop1"

# Buka koneksi serial
try:
    ser = serial.Serial(
        port=serial_port,
        baudrate=BAUDRATE,
        timeout=TIMEOUT,
        write_timeout=WRITE_TIMEOUT
    )
    print(f"[{role}] Terhubung ke LoRa via {serial_port} dengan baudrate {BAUDRATE}")
except Exception as e:
    print(f"[{role}] Gagal membuka port: {e}")
    sys.exit(1)

ack_received = False

def listen_for_messages():
    global ack_received
    buffer = ""
    while True:
        try:
            char = ser.read().decode('utf-8', errors='ignore')
            if char:
                if char == '\n':
                    raw = buffer.strip()
                    buffer = ""
                    if not raw:
                        continue
                    if raw.startswith("ACK:"):
                        msg_id = raw[4:]
                        print(f"[{role}] ✅ ACK diterima untuk pesan ID: {msg_id}")
                        ack_received = True
                    else:
                        print(f"[{role}] 💬 Dari {peer}: {raw}")
                        # Ekstrak ID untuk ACK
                        msg_id = raw.split('|')[0] if '|' in raw else 'unknown'
                        ack_response = f"ACK:{msg_id}"
                        time.sleep(0.15)  # Jeda kecil — penting di baudrate rendah
                        ser.write((ack_response + '\n').encode())
                        print(f"[{role}] ↪️ Kirim ACK: {ack_response}")
                else:
                    buffer += char
            time.sleep(0.01)
        except Exception as e:
            # Abaikan error minor saat baca
            pass

# Jalankan listener di thread terpisah
listener_thread = threading.Thread(target=listen_for_messages, daemon=True)
listener_thread.start()

print(f"\n[{role}] Siap mengirim ke {peer}. Ketik pesan lalu Enter.")
print("Ketik 'exit' untuk keluar.\n")

message_counter = 0
try:
    while True:
        try:
            user_input = input(f"[{role}] ➜ ").strip()
        except EOFError:
            break

        if user_input.lower() == 'exit':
            break
        if not user_input:
            continue

        message_counter += 1
        full_msg = f"{message_counter}|{user_input}"
        ack_received = False
        retry = 0

        while retry < MAX_RETRIES and not ack_received:
            print(f"[{role}] 📤 Kirim: {full_msg}")
            try:
                ser.write((full_msg + '\n').encode())
            except serial.SerialTimeoutException:
                print(f"[{role}] ⚠️ Timeout saat mengirim data.")
                retry += 1
                continue

            # Tunggu ACK
            start_wait = time.time()
            while (time.time() - start_wait < ACK_TIMEOUT) and not ack_received:
                time.sleep(0.1)

            if not ack_received:
                retry += 1
                print(f"[{role}] ⚠️ Tidak ada ACK. Percobaan ke-{retry}/{MAX_RETRIES}")
                if retry < MAX_RETRIES:
                    time.sleep(2)

        if ack_received:
            print(f"[{role}] ✅ Pesan berhasil diterima oleh {peer}!")
        else:
            print(f"[{role}] ❌ Gagal: Tidak ada konfirmasi dari {peer} setelah {MAX_RETRIES} kali.")

except KeyboardInterrupt:
    print(f"\n[{role}] Dihentikan oleh pengguna.")

finally:
    ser.close()
    print(f"[{role}] Port serial ditutup.")