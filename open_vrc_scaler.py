import tkinter as tk
from tkinter import ttk
import threading
import math
import time
import webbrowser
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

# --- Configuration ---
VRCHAT_IP = "127.0.0.1"
OSC_RECEIVE_PORT = 9001
OSC_SEND_PORT = 9000
UPDATE_INTERVAL_MS = 50  # 50ms = 20 ticks per second

class OpenVRCScalerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OpenVRCScaler")
        self.root.geometry("350x380")
        
        # --- State Variables ---
        self.scaling_enabled = False
        self.scaling_allowed = True
        
        self.current_height = 1.0
        self.target_height = 1.0
        
        self.transition_time_total = 0
        self.transition_time_remaining = 0.0
        
        # Radial Menu Raw Parameters
        self.param_hundreds = 0.0
        self.param_ones = 0.0
        self.param_decimal = 0.0
        
        # Connection Tracking
        self.last_osc_time = 0.0
        self.is_connected = False
        
        # Debounce Tracking
        self.debounce_id = None
        self.DEBOUNCE_DELAY_MS = 150
        
        self.osc_client = SimpleUDPClient(VRCHAT_IP, OSC_SEND_PORT)
        
        self.build_ui()
        self.start_osc_server()
        self.update_loop()

    def build_ui(self):
        self.lbl_status = ttk.Label(self.root, text=f"OSC Status: Listening on {OSC_RECEIVE_PORT}", foreground="green")
        self.lbl_status.pack(pady=10)
        
        self.lbl_height = ttk.Label(self.root, text="Current Height: 1.00 m", font=("Helvetica", 14, "bold"))
        self.lbl_height.pack(pady=5)
        
        frame = ttk.LabelFrame(self.root, text="Current Menu Settings")
        frame.pack(fill="x", padx=15, pady=10)
        
        self.lbl_enabled = ttk.Label(frame, text="Scaling Enabled: False")
        self.lbl_enabled.pack(anchor="w", padx=5, pady=2)
        
        self.lbl_trans = ttk.Label(frame, text="Transition Time: 0s")
        self.lbl_trans.pack(anchor="w", padx=5, pady=2)
        
        self.lbl_hundreds = ttk.Label(frame, text="Hundreds: 0.00")
        self.lbl_hundreds.pack(anchor="w", padx=5, pady=2)
        
        self.lbl_ones = ttk.Label(frame, text="Ones: 0.00")
        self.lbl_ones.pack(anchor="w", padx=5, pady=2)
        
        self.lbl_decimal = ttk.Label(frame, text="Decimal: 0.00")
        self.lbl_decimal.pack(anchor="w", padx=5, pady=2)
        
        btn_reset = ttk.Button(self.root, text="Reset Height to 1m", command=self.reset_height)
        btn_reset.pack(pady=15)
        
        link = ttk.Label(self.root, text="GitHub Repo", foreground="blue", cursor="hand2")
        link.pack(pady=(5, 15))
        link.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/SkyeCA/VRChatOscScaler"))

    def reset_height(self):
        self.target_height = 1.0
        self.decompose_height_to_menu(1.0)
        
        if self.transition_time_total <= 0:
            self.set_eyeheight(1.0)
        else:
            self.transition_time_remaining = self.transition_time_total

    def start_osc_server(self):
        dispatcher = Dispatcher()
        
        dispatcher.set_default_handler(self.default_osc_handler)
        dispatcher.map("/avatar/eyeheight", self.on_eyeheight_changed)
        dispatcher.map("/avatar/eyeheightscalingallowed", self.on_scaling_allowed_changed)
        dispatcher.map("/avatar/parameters/OpenVRCScaler_ScalingEnabled", self.on_enabled_changed)
        dispatcher.map("/avatar/parameters/OpenVRCScaler_TransistionTime", self.on_transition_changed)
        dispatcher.map("/avatar/parameters/OpenVRCScaler_Hundreds", self.on_hundreds_changed)
        dispatcher.map("/avatar/parameters/OpenVRCScaler_Ones", self.on_ones_changed)
        dispatcher.map("/avatar/parameters/OpenVRCScaler_Decimal", self.on_decimal_changed)
        
        self.server = BlockingOSCUDPServer((VRCHAT_IP, OSC_RECEIVE_PORT), dispatcher)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    # --- OSC Callbacks ---
    def mark_active(self):
        """Updates the timestamp of the last received OSC message."""
        self.last_osc_time = time.time()

    def default_osc_handler(self, address, *args):
        self.mark_active()

    def on_eyeheight_changed(self, address, args):
        self.mark_active()
        new_height = args
        # If the height was changed externally (by the world) and not by our active transition
        if abs(new_height - self.current_height) > 0.05 and self.transition_time_remaining <= 0:
            self.current_height = new_height
            self.target_height = new_height
            self.decompose_height_to_menu(new_height)
        self.update_height_label()

    def on_scaling_allowed_changed(self, address, args):
        self.mark_active()
        self.scaling_allowed = args

    def on_enabled_changed(self, address, args):
        self.mark_active()
        self.scaling_enabled = args
        self.lbl_enabled.config(text=f"Scaling Enabled: {self.scaling_enabled}")
        self.calculate_target_height()

    def on_transition_changed(self, address, args):
        self.mark_active()
        self.transition_time_total = math.ceil(args * 100)
        self.lbl_trans.config(text=f"Transition Time: {self.transition_time_total}s")

    def on_hundreds_changed(self, address, args):
        self.mark_active()
        if abs(self.param_hundreds - args) > 0.001:
            self.param_hundreds = args
            self.lbl_hundreds.config(text=f"Hundreds: {args:.2f}")
            self.trigger_debounce()

    def on_ones_changed(self, address, args):
        self.mark_active()
        if abs(self.param_ones - args) > 0.001:
            self.param_ones = args
            self.lbl_ones.config(text=f"Ones: {args:.2f}")
            self.trigger_debounce()

    def on_decimal_changed(self, address, args):
        self.mark_active()
        if abs(self.param_decimal - args) > 0.001:
            self.param_decimal = args
            self.lbl_decimal.config(text=f"Decimal: {args:.2f}")
            self.trigger_debounce()

    # --- Core Logic ---
    def trigger_debounce(self):
        """Waits for the user to stop scrolling before calculating the target height."""
        if self.debounce_id is not None:
            self.root.after_cancel(self.debounce_id)
        self.debounce_id = self.root.after(self.DEBOUNCE_DELAY_MS, self.calculate_target_height)

    def calculate_target_height(self):
        if not self.scaling_enabled or not self.scaling_allowed:
            return
            
        raw_height = (self.param_hundreds * 10000) + (self.param_ones * 100) + (self.param_decimal * 1)
        
        if raw_height > 10000.0:
            raw_height = 10000.0
            self.decompose_height_to_menu(raw_height)
            
        if raw_height < 0.1:
            raw_height = 0.1
            self.decompose_height_to_menu(raw_height)

        self.target_height = raw_height
        
        if self.transition_time_remaining <= 0:
            self.transition_time_remaining = self.transition_time_total

    def decompose_height_to_menu(self, height):
        """Breaks a height down into the 0.0-1.0 constraints of the radial dials."""
        h_val = math.floor(height / 100) / 100.0
        o_val = math.floor(height % 100) / 100.0
        d_val = height % 1.0
        
        self.param_hundreds = h_val
        self.param_ones = o_val
        self.param_decimal = d_val
        
        self.lbl_hundreds.config(text=f"Hundreds: {h_val:.2f}")
        self.lbl_ones.config(text=f"Ones: {o_val:.2f}")
        self.lbl_decimal.config(text=f"Decimal: {d_val:.2f}")
        
        self.osc_client.send_message("/avatar/parameters/OpenVRCScaler_Hundreds", h_val)
        self.osc_client.send_message("/avatar/parameters/OpenVRCScaler_Ones", o_val)
        self.osc_client.send_message("/avatar/parameters/OpenVRCScaler_Decimal", d_val)

    def set_eyeheight(self, height):
        self.current_height = height
        self.osc_client.send_message("/avatar/eyeheight", height)
        self.update_height_label()

    def update_height_label(self):
        self.lbl_height.config(text=f"Current Height: {self.current_height:.2f} m")

    def update_loop(self):
        """Handles smooth scaling over time and connection state."""
        
        if time.time() - self.last_osc_time > 5.0:
            if self.is_connected:
                self.is_connected = False
                self.lbl_status.config(text="OSC Status: Disconnected (No data for 5s)", foreground="red")
        else:
            if not self.is_connected:
                self.is_connected = True
                self.lbl_status.config(text=f"OSC Status: Connected on port {OSC_RECEIVE_PORT}", foreground="green")

        if self.scaling_enabled and self.scaling_allowed:
            distance = self.target_height - self.current_height
            
            if abs(distance) > 0.01 and self.transition_time_remaining > 0:
                step_duration = UPDATE_INTERVAL_MS / 1000.0
                
                if self.transition_time_remaining <= step_duration:
                    self.set_eyeheight(self.target_height)
                    self.transition_time_remaining = 0
                else:
                    steps_left = self.transition_time_remaining / step_duration
                    step_size = distance / steps_left
                    
                    self.set_eyeheight(self.current_height + step_size)
                    self.transition_time_remaining -= step_duration
                    
            elif abs(distance) > 0.01 and self.transition_time_remaining <= 0:
                self.set_eyeheight(self.target_height)

        self.root.after(UPDATE_INTERVAL_MS, self.update_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = OpenVRCScalerApp(root)
    root.mainloop()