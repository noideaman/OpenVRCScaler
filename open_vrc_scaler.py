import tkinter as tk
from tkinter import ttk
import threading
import math
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
        self.root.geometry("350x450")
        
        # --- State Variables ---
        self.scaling_enabled = False
        self.scaling_allowed = True
        
        self.current_height = 1.0
        self.target_height = 1.0
        
        self.transition_time_total = 0.0  # In seconds (Menu value * 100)
        self.transition_time_remaining = 0.0
        
        # Radial Menu Raw Parameters (0.0 - 1.0)
        self.param_hundreds = 0.0
        self.param_ones = 0.0
        self.param_decimal = 0.0
        
        self.osc_client = SimpleUDPClient(VRCHAT_IP, OSC_SEND_PORT)
        
        self.build_ui()
        self.start_osc_server()
        self.update_loop()

    def build_ui(self):
        # Connection State
        self.lbl_status = ttk.Label(self.root, text=f"OSC Status: Listening on {OSC_RECEIVE_PORT}", foreground="green")
        self.lbl_status.pack(pady=10)
        
        # Height Display
        self.lbl_height = ttk.Label(self.root, text="Current Height: 1.00 m", font=("Helvetica", 14, "bold"))
        self.lbl_height.pack(pady=5)
        
        # Parameters Frame
        frame = ttk.LabelFrame(self.root, text="Current Menu Settings")
        frame.pack(fill="x", padx=15, pady=10)
        
        self.lbl_enabled = ttk.Label(frame, text="Scaling Enabled: False")
        self.lbl_enabled.pack(anchor="w", padx=5, pady=2)
        
        self.lbl_trans = ttk.Label(frame, text="Transition Time: 0.0s")
        self.lbl_trans.pack(anchor="w", padx=5, pady=2)
        
        self.lbl_hundreds = ttk.Label(frame, text="Hundreds: 0.00")
        self.lbl_hundreds.pack(anchor="w", padx=5, pady=2)
        
        self.lbl_ones = ttk.Label(frame, text="Ones: 0.00")
        self.lbl_ones.pack(anchor="w", padx=5, pady=2)
        
        self.lbl_decimal = ttk.Label(frame, text="Decimal: 0.00")
        self.lbl_decimal.pack(anchor="w", padx=5, pady=2)
        
        # Reset Button
        btn_reset = ttk.Button(self.root, text="Reset Height to 1m", command=self.reset_height)
        btn_reset.pack(pady=15)
        
        # GitHub Link
        link = ttk.Label(self.root, text="GitHub Repo", foreground="blue", cursor="hand2")
        link.pack(side="bottom", pady=10)
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
        
        # VRChat default params
        dispatcher.map("/avatar/eyeheight", self.on_eyeheight_changed)
        dispatcher.map("/avatar/eyeheightscalingallowed", self.on_scaling_allowed_changed)
        
        # Menu params
        dispatcher.map("/avatar/parameters/OpenVRCScaler_ScalingEnabled", self.on_enabled_changed)
        dispatcher.map("/avatar/parameters/OpenVRCScaler_TransistionTime", self.on_transition_changed)
        dispatcher.map("/avatar/parameters/OpenVRCScaler_Hundreds", self.on_hundreds_changed)
        dispatcher.map("/avatar/parameters/OpenVRCScaler_Ones", self.on_ones_changed)
        dispatcher.map("/avatar/parameters/OpenVRCScaler_Decimal", self.on_decimal_changed)
        
        self.server = BlockingOSCUDPServer((VRCHAT_IP, OSC_RECEIVE_PORT), dispatcher)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    # --- OSC Callbacks ---
    def on_eyeheight_changed(self, address, args):
        new_height = args
        # If the height was changed externally (by the world) and not by our active transition
        if abs(new_height - self.current_height) > 0.05 and self.transition_time_remaining <= 0:
            self.current_height = new_height
            self.target_height = new_height
            self.decompose_height_to_menu(new_height)
        self.update_height_label()

    def on_scaling_allowed_changed(self, address, args):
        self.scaling_allowed = args

    def on_enabled_changed(self, address, args):
        self.scaling_enabled = args
        self.lbl_enabled.config(text=f"Scaling Enabled: {self.scaling_enabled}")
        self.calculate_target_height()

    def on_transition_changed(self, address, args):
        self.transition_time_total = args * 100 # e.g. 0.05 * 100 = 5.0 seconds
        self.lbl_trans.config(text=f"Transition Time: {self.transition_time_total:.1f}s")

    def on_hundreds_changed(self, address, args):
        if abs(self.param_hundreds - args) > 0.001:
            self.param_hundreds = args
            self.lbl_hundreds.config(text=f"Hundreds: {args:.2f}")
            self.calculate_target_height()

    def on_ones_changed(self, address, args):
        if abs(self.param_ones - args) > 0.001:
            self.param_ones = args
            self.lbl_ones.config(text=f"Ones: {args:.2f}")
            self.calculate_target_height()

    def on_decimal_changed(self, address, args):
        if abs(self.param_decimal - args) > 0.001:
            self.param_decimal = args
            self.lbl_decimal.config(text=f"Decimal: {args:.2f}")
            self.calculate_target_height()

    # --- Core Logic ---
    def calculate_target_height(self):
        if not self.scaling_enabled or not self.scaling_allowed:
            return
            
        raw_height = (self.param_hundreds * 10000) + (self.param_ones * 100) + (self.param_decimal * 1)
        
        # Hard cap at 10,000 meters and correct the radial menu if exceeded
        if raw_height > 10000.0:
            raw_height = 10000.0
            self.decompose_height_to_menu(raw_height)
            
        # Prevent going below a logical minimum height (e.g., 0.1 meters) to prevent game breaks
        if raw_height < 0.1:
            raw_height = 0.1
            self.decompose_height_to_menu(raw_height)

        self.target_height = raw_height
        
        # Start or adjust transition timer without resetting it entirely if already active
        if self.transition_time_remaining <= 0:
            self.transition_time_remaining = self.transition_time_total

    def decompose_height_to_menu(self, height):
        """Breaks a height down into the 0.0-1.0 constraints of the radial dials."""
        h_val = math.floor(height / 100) / 100.0
        o_val = math.floor(height % 100) / 100.0
        d_val = height % 1.0
        
        # Update local UI & State
        self.param_hundreds = h_val
        self.param_ones = o_val
        self.param_decimal = d_val
        
        self.lbl_hundreds.config(text=f"Hundreds: {h_val:.2f}")
        self.lbl_ones.config(text=f"Ones: {o_val:.2f}")
        self.lbl_decimal.config(text=f"Decimal: {d_val:.2f}")
        
        # Send corrected values back to VRChat so the radial menu matches
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
        """Handles smooth scaling over time."""
        if self.scaling_enabled and self.scaling_allowed:
            distance = self.target_height - self.current_height
            
            # If we need to transition and have time remaining
            if abs(distance) > 0.01 and self.transition_time_remaining > 0:
                step_duration = UPDATE_INTERVAL_MS / 1000.0 # 0.05 seconds
                
                # If the remaining time is less than one tick, finish it instantly
                if self.transition_time_remaining <= step_duration:
                    self.set_eyeheight(self.target_height)
                    self.transition_time_remaining = 0
                else:
                    # Calculate how much to scale this tick based on remaining time and distance
                    steps_left = self.transition_time_remaining / step_duration
                    step_size = distance / steps_left
                    
                    self.set_eyeheight(self.current_height + step_size)
                    self.transition_time_remaining -= step_duration
                    
            # If transition time is 0 (instant) or transition is finished
            elif abs(distance) > 0.01 and self.transition_time_remaining <= 0:
                self.set_eyeheight(self.target_height)

        # Loop again
        self.root.after(UPDATE_INTERVAL_MS, self.update_loop)


if __name__ == "__main__":
    root = tk.Tk()
    app = OpenVRCScalerApp(root)
    root.mainloop()