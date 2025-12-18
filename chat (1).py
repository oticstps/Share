import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import serial
import threading
import time
import re
from datetime import datetime
import queue
import random

# === Konfigurasi Default ===
DEFAULT_BAUDRATE = 2400
ACK_TIMEOUT = 8
MAX_RETRIES = 3
TIMEOUT = 2
WRITE_TIMEOUT = 2


class LoRaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LoRa Communication Interface")
        self.root.geometry("1000x650")
        self.root.minsize(900, 600)
        self.root.configure(bg="#ffffff")  # white base

        # === Palet Warna Sesuai Preferensi ===
        self.bg_color = "#ffffff"
        self.header_bg = "#e6f2ff"      # light blue header
        self.sidebar_bg = "#f0f8ff"     # very light blue sidebar
        self.chat_bg = "#fafafa"
        self.text_fg = "#333333"
        self.border_color = "#cccccc"

        self.button_primary = "#0d6efd"   # blue (kirim)
        self.button_danger = "#dc3545"    # red (disconnect)
        self.button_success = "#198754"   # green (simulasi)
        self.button_secondary = "#6c757d" # gray

        # Serial state
        self.ser = None
        self.is_connected = False
        self.role = "laptop1"
        self.peer = "laptop2"
        self.message_counter = 0
        self.ack_received = False
        self.ack_event = threading.Event()

        # Thread & queue
        self.listener_thread = None
        self.message_queue = queue.Queue()
        self.running = True
        self.is_simulating = False

        self.setup_styles()
        self.create_widgets()
        self.setup_listener()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Button
        style.configure("Primary.TButton", background=self.button_primary, foreground="white", font=("Arial", 10, "bold"), relief="flat")
        style.map("Primary.TButton", background=[("active", "#0b5ed7")])
        
        style.configure("Danger.TButton", background=self.button_danger, foreground="white", font=("Arial", 10, "bold"))
        style.map("Danger.TButton", background=[("active", "#bd2130")])
        
        style.configure("Success.TButton", background=self.button_success, foreground="white", font=("Arial", 9))
        style.map("Success.TButton", background=[("active", "#157347")])
        
        style.configure("Secondary.TButton", background=self.button_secondary, foreground="white", font=("Arial", 9))
        style.map("Secondary.TButton", background=[("active", "#5c636a")])

        # Combobox
        style.configure("TCombobox", fieldbackground="white", background="white")

        # Frame / LabelFrame
        style.configure("Card.TLabelframe", background=self.sidebar_bg, relief="flat", borderwidth=0)
        style.configure("Card.TLabelframe.Label", background=self.sidebar_bg, font=("Arial", 10, "bold"), foreground="#0d47a1")

    def create_widgets(self):
        # === Header ===
        header = tk.Frame(self.root, bg=self.header_bg, height=60)
        header.pack(fill=tk.X, padx=15, pady=(10, 5))
        header.pack_propagate(False)

        title = tk.Label(header, text="📡 LoRa Communication Interface", font=("Arial", 16, "bold"), bg=self.header_bg, fg="#0d47a1")
        title.pack(side=tk.LEFT, padx=10)

        status_frame = tk.Frame(header, bg=self.header_bg)
        status_frame.pack(side=tk.RIGHT, padx=10)
        tk.Label(status_frame, text="Status:", bg=self.header_bg, font=("Arial", 10, "bold"), fg="#555").pack(side=tk.LEFT)
        self.status_label = tk.Label(status_frame, text="Disconnected", bg=self.header_bg, fg="#dc3545", font=("Arial", 10))
        self.status_label.pack(side=tk.LEFT, padx=(5, 15))

        self.connect_btn = ttk.Button(
            header,
            text="🔌 Connect",
            command=self.toggle_connection,
            style="Primary.TButton"
        )
        self.connect_btn.pack(side=tk.RIGHT, padx=10)

        # === Main Layout: Sidebar (30%) + Chat (70%) ===
        main_frame = tk.Frame(self.root, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # Sidebar
        sidebar = tk.Frame(main_frame, bg=self.sidebar_bg, width=280, relief="solid", bd=1, highlightbackground=self.border_color, highlightthickness=1)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        sidebar.pack_propagate(False)

        # Serial Config Card
        config_frame = ttk.LabelFrame(sidebar, text="⚙️ Serial Configuration", style="Card.TLabelframe")
        config_frame.pack(fill=tk.X, padx=15, pady=15)

        # Port
        tk.Label(config_frame, text="Port:", bg=self.sidebar_bg, font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=5)
        self.port_var = tk.StringVar(value="COM4")
        port_entry = tk.Entry(config_frame, textvariable=self.port_var, width=20, font=("Arial", 10), relief="solid", bd=1)
        port_entry.grid(row=0, column=1, pady=5, padx=(5, 0))

        # Baudrate
        tk.Label(config_frame, text="Baudrate:", bg=self.sidebar_bg, font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=5)
        self.baud_var = tk.IntVar(value=DEFAULT_BAUDRATE)
        baud_combo = ttk.Combobox(config_frame, textvariable=self.baud_var, width=18, state="readonly", font=("Arial", 10))
        baud_combo['values'] = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]
        baud_combo.grid(row=1, column=1, pady=5, padx=(5, 0))

        # Role
        tk.Label(config_frame, text="Role:", bg=self.sidebar_bg, font=("Arial", 10)).grid(row=2, column=0, sticky="w", pady=5)
        self.role_var = tk.StringVar(value="laptop1")
        role_combo = ttk.Combobox(config_frame, textvariable=self.role_var, width=18, state="readonly", font=("Arial", 10))
        role_combo['values'] = ["laptop1", "laptop2"]
        role_combo.grid(row=2, column=1, pady=5, padx=(5, 0))
        role_combo.bind("<<ComboboxSelected>>", self.on_role_change)

        # Sensor Simulation Card
        sensor_frame = ttk.LabelFrame(sidebar, text="🌡️ Sensor Data", style="Card.TLabelframe")
        sensor_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        self.temp_var = tk.StringVar(value="—")
        self.hum_var = tk.StringVar(value="—")
        self.status_var = tk.StringVar(value="—")

        tk.Label(sensor_frame, text="Temperature:", bg=self.sidebar_bg, font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=3)
        tk.Label(sensor_frame, textvariable=self.temp_var, bg=self.sidebar_bg, font=("Arial", 10, "bold")).grid(row=0, column=1, sticky="w", pady=3)

        tk.Label(sensor_frame, text="Humidity:", bg=self.sidebar_bg, font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=3)
        tk.Label(sensor_frame, textvariable=self.hum_var, bg=self.sidebar_bg, font=("Arial", 10, "bold")).grid(row=1, column=1, sticky="w", pady=3)

        tk.Label(sensor_frame, text="Status:", bg=self.sidebar_bg, font=("Arial", 10)).grid(row=2, column=0, sticky="w", pady=3)
        tk.Label(sensor_frame, textvariable=self.status_var, bg=self.sidebar_bg, font=("Arial", 10, "bold")).grid(row=2, column=1, sticky="w", pady=3)

        self.simulate_btn = ttk.Button(
            sensor_frame,
            text="▶️ Start Simulation",
            command=self.toggle_simulation,
            style="Success.TButton"
        )
        self.simulate_btn.grid(row=3, column=0, columnspan=2, pady=(10, 5), sticky="ew", padx=5)

        # Image Upload Card
        image_frame = ttk.LabelFrame(sidebar, text="🖼️ Send Image Info", style="Card.TLabelframe")
        image_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        self.image_path_var = tk.StringVar(value="")
        path_entry = tk.Entry(image_frame, textvariable=self.image_path_var, width=25, font=("Arial", 9), state="readonly", relief="solid", bd=1)
        path_entry.pack(pady=5, padx=5, fill=tk.X)

        ttk.Button(image_frame, text="📂 Browse", command=self.browse_image, style="Secondary.TButton").pack(pady=3, padx=5, fill=tk.X)
        ttk.Button(image_frame, text="📤 Send Image Info", command=self.send_image_info, style="Primary.TButton").pack(pady=(5, 10), padx=5, fill=tk.X)

        # === Chat Area ===
        chat_frame = tk.Frame(main_frame, bg=self.chat_bg, relief="solid", bd=1, highlightbackground=self.border_color, highlightthickness=1)
        chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Chat display
        self.chat_display = tk.Text(
            chat_frame, 
            state=tk.DISABLED, 
            wrap=tk.WORD, 
            font=("Consolas", 10), 
            bg=self.chat_bg, 
            fg=self.text_fg,
            padx=10,
            pady=10,
            relief="flat"
        )
        chat_scroll = tk.Scrollbar(chat_frame, orient=tk.VERTICAL, command=self.chat_display.yview)
        self.chat_display.configure(yscrollcommand=chat_scroll.set)
        self.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 0), pady=(0, 0))
        chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Input area
        input_frame = tk.Frame(chat_frame, bg=self.bg_color)
        input_frame.pack(fill=tk.X, pady=8, padx=10)

        self.input_var = tk.StringVar()
        input_entry = tk.Entry(input_frame, textvariable=self.input_var, font=("Arial", 11), relief="solid", bd=1)
        input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        input_entry.bind("<Return>", lambda e: self.send_message())

        ttk.Button(input_frame, text="📤 Send LoRa", command=self.send_message, style="Primary.TButton").pack(side=tk.RIGHT)
        ttk.Button(input_frame, text="🗑️ Clear", command=self.clear_chat, style="Secondary.TButton").pack(side=tk.RIGHT, padx=(5, 0))

    # --- Fungsi lainnya tetap sama ---
    def on_role_change(self, event=None):
        self.role = self.role_var.get()
        self.peer = "laptop2" if self.role == "laptop1" else "laptop1"
        self.update_title()
        self.append_to_chat(f"[INFO] Role changed to {self.role}. Peer is {self.peer}.")

    def update_title(self):
        self.root.title(f"LoRa - {self.role.upper()}")

    def toggle_connection(self):
        if not self.is_connected:
            self.connect_serial()
        else:
            self.disconnect_serial()

    def connect_serial(self):
        port = self.port_var.get().strip()
        if not port:
            messagebox.showerror("Error", "Please enter a serial port!")
            return

        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=self.baud_var.get(),
                timeout=TIMEOUT,
                write_timeout=WRITE_TIMEOUT
            )
            self.is_connected = True
            self.connect_btn.config(text="🔌 Disconnect", style="Danger.TButton")
            self.status_label.config(text="Connected", fg=self.button_success)
            self.role = self.role_var.get()
            self.peer = "laptop2" if self.role == "laptop1" else "laptop1"
            self.update_title()
            self.append_to_chat(f"[{self.role}] Connected to {port} at {self.baud_var.get()} baud.")
        except Exception as e:
            messagebox.showerror("Serial Error", f"Failed to open {port}:\n{str(e)}")
            self.status_label.config(text="Error", fg="#dc3545")

    def disconnect_serial(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.is_connected = False
        self.connect_btn.config(text="🔌 Connect", style="Primary.TButton")
        self.status_label.config(text="Disconnected", fg="#666")
        self.append_to_chat(f"[{self.role}] Serial port closed.")

    def append_to_chat(self, message, sender="system"):
        self.chat_display.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        if sender == "peer":
            prefix = f"[{self.peer}]"
            color = "#0d6efd"
        elif sender == "self":
            prefix = f"[{self.role}]"
            color = "#198754"
        else:
            prefix = "[INFO]"
            color = "#6c757d"

        full_msg = f"{timestamp} {prefix} {message}\n"
        self.chat_display.insert(tk.END, full_msg)
        self.chat_display.tag_add("color", "end-{}c".format(len(full_msg)), "end-1c")
        self.chat_display.tag_config("color", foreground=color)

        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def send_message(self):
        if not self.is_connected or not self.ser:
            messagebox.showwarning("Not Connected", "Please connect to a serial port first.")
            return

        text = self.input_var.get().strip()
        if not text:
            return

        self.input_var.set("")
        self.message_counter += 1
        msg_id = str(self.message_counter)
        full_msg = f"{msg_id}|{text}"

        success = self.send_with_ack(full_msg, msg_id)
        if success:
            self.append_to_chat(f"Sent: {text}", sender="self")
        else:
            self.append_to_chat(f"Failed: {text} (no ACK)", sender="self")

    def send_with_ack(self, full_msg, msg_id):
        retry = 0
        while retry < MAX_RETRIES:
            try:
                self.ser.write((full_msg + '\n').encode())
                self.append_to_chat(f"📤 Sending: {full_msg}", sender="self")
            except serial.SerialTimeoutException:
                retry += 1
                time.sleep(2)
                continue

            self.ack_received = False
            start = time.time()
            while (time.time() - start < ACK_TIMEOUT) and not self.ack_received:
                time.sleep(0.1)

            if self.ack_received:
                return True
            else:
                retry += 1
                if retry < MAX_RETRIES:
                    time.sleep(2)
        return False

    def send_sensor_data(self):
        temp = random.randint(15, 65)
        hum = random.randint(30, 70)
        status = random.choice(["Normal", "Warning", "Critical"])
        self.temp_var.set(f"{temp}°C")
        self.hum_var.set(f"{hum}%")
        self.status_var.set(status)
        msg = f"SENSOR: Temp={temp}°C, Hum={hum}%, Status={status}"
        self.send_message_direct(msg)

    def send_message_direct(self, text):
        if not self.is_connected or not self.ser:
            return
        self.message_counter += 1
        msg_id = str(self.message_counter)
        full_msg = f"{msg_id}|{text}"
        self.ser.write((full_msg + '\n').encode())
        self.append_to_chat(f"Auto-sent: {text}", sender="self")

    def browse_image(self):
        file_path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        if file_path:
            self.image_path_var.set(file_path)

    def send_image_info(self):
        path = self.image_path_var.get()
        if not path:
            messagebox.showwarning("No Image", "Please select an image first.")
            return
        filename = path.split("/")[-1].split("\\")[-1]
        msg = f"[IMAGE] {filename}"
        self.send_message_direct(msg)
        self.image_path_var.set("")

    def toggle_simulation(self):
        self.is_simulating = not self.is_simulating
        if self.is_simulating:
            self.simulate_btn.config(text="⏹️ Stop Simulation")
            self.run_sensor_simulation()
        else:
            self.simulate_btn.config(text="▶️ Start Simulation")

    def run_sensor_simulation(self):
        if self.is_simulating and self.is_connected:
            self.send_sensor_data()
            self.root.after(3000, self.run_sensor_simulation)

    def clear_chat(self):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def serial_listener(self):
        buffer = ""
        while self.running:
            if self.ser and self.ser.is_open:
                try:
                    char = self.ser.read().decode('utf-8', errors='ignore')
                    if char:
                        if char == '\n':
                            raw = buffer.strip()
                            buffer = ""
                            if raw:
                                self.message_queue.put(raw)
                        else:
                            buffer += char
                    time.sleep(0.01)
                except:
                    pass
            else:
                time.sleep(0.1)

    def process_incoming_messages(self):
        try:
            while True:
                raw = self.message_queue.get_nowait()
                if raw.startswith("ACK:"):
                    msg_id = raw[4:]
                    self.ack_received = True
                    self.append_to_chat(f"✅ ACK for ID: {msg_id}", sender="self")
                else:
                    parts = raw.split('|', 1)
                    msg_id = parts[0] if len(parts) > 1 else 'unknown'
                    message_text = parts[1] if len(parts) > 1 else raw
                    self.append_to_chat(message_text, sender="peer")
                    ack_response = f"ACK:{msg_id}"
                    time.sleep(0.15)
                    if self.ser and self.ser.is_open:
                        self.ser.write((ack_response + '\n').encode())
        except queue.Empty:
            pass
        self.root.after(50, self.process_incoming_messages)

    def setup_listener(self):
        self.listener_thread = threading.Thread(target=self.serial_listener, daemon=True)
        self.listener_thread.start()
        self.root.after(100, self.process_incoming_messages)

    def on_closing(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = LoRaApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

