import websocket
import json
import time
import _thread as thread 
from gpiozero import LED, Button

# Transparent trace mode forces tracking alerts directly onto your screen
websocket.enableTrace(True)

class ClientNode:
    def __init__(self, client_id, host_addr):
        self.client_id = client_id
        self.current_state = 0 
        
        # --- Hardware Mapping (Standard initialization parameters) ---
        self.red_led = LED(17)
        self.yellow_led = LED(27)
        self.ack_btn = Button(22)
        self.rst_btn = Button(23)
        
        # --- WebSocket Client App Binding ---
        self.ws = websocket.WebSocketApp(host_addr,
            on_message = self.on_message,
            on_error = self.on_error,
            on_close = self.on_close)
        self.ws.on_open = self.on_open

    def request_help(self):
        print(f"\n🚨 [Hardware Input] 'Ack' button pressed at {self.client_id}!")
        self.send_state(1)

    def reset_system(self):
        print(f"\n🔄 [Hardware Input] 'Rst' button pressed at {self.client_id}!")
        self.send_state(0)

    def send_state(self, state):
        payload = {"sender": self.client_id, "action": "state_change", "state": state}
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(payload))
            print(f"[Network Output] State {state} successfully transmitted upstream.")
        else:
            print("❌ [Network Error] Frame dropped. Connection to central server is down!")

    def on_open(self, ws):
        print(f"\n⚡ [Connected] Linked to Central Network Mesh as: {self.client_id}")
        # Identify itself to server routing registry immediately
        payload = {"sender": self.client_id, "action": "register"}
        self.ws.send(json.dumps(payload))

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            action = data.get("action")
            
            # Filter incoming states relevant only to this room's hardware
            if action == "state_change":
                target = data.get("target") or data.get("sender")
                if target == self.client_id:
                    self.current_state = data.get("state")
                    self.update_hardware_leds()

            # Listen for dedicated, targeted text instructions from the Nurse
            elif action == "send_msg" and data.get("target") == self.client_id:
                print(f"\n📬 [MESSAGE FROM NURSE STATION]: {data.get('message')}\n")

        except json.JSONDecodeError:
            pass

    def update_hardware_leds(self):
        """Drives physical outputs cleanly based on internal synchronized state"""
        if self.current_state == 0:
            self.red_led.off()
            self.yellow_led.off()
        elif self.current_state == 1:
            self.red_led.on()
            self.yellow_led.off()
        elif self.current_state == 2:
            self.red_led.off()
            self.yellow_led.on()

    def on_error(self, ws, error):
        print(f"⚠️ [WebSocket Exception]: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print(f"🔌 [Disconnected] Session ended by server topology ({close_msg})")

    def run(self):
        # 1. Run network loop inside an independent background thread (Non-blocking)
        thread.start_new_thread(self.ws.run_forever, ())
        
        print("\n--- Active Live Status Monitor & Button Polling Loop Active ---")
        state_labels = {0: "🟢 IDLE", 1: "🔴 WARNING (Assistance Requested)", 2: "🟡 HANDLED (Nurse En Route)"}
        
        try:
            while True:
                # 2. Sequential Hardware Polling (Foolproof Debounce & Response Isolation)
                if self.rst_btn.is_pressed:
                    self.reset_system()
                    time.sleep(0.4) # Absorbs bounce entirely; no timing precision needed
                    
                if self.ack_btn.is_pressed:
                    self.request_help()
                    time.sleep(0.4) # Absorbs bounce entirely; no timing precision needed
                
                # 3. Persistent Terminal Screen Diagnostics
                label = state_labels.get(self.current_state, "Unknown Mode")
                print(f"[Live Diagnostics] Terminal Location: {self.client_id.upper()} | Current Status: {label} ", end="\r")
                
                time.sleep(0.05) # Tiny constraint ensures CPU remains cold (0% load)
                
        except KeyboardInterrupt:
            print("\nTerminating background device loops...")

if __name__ == "__main__":
    # ---------------------------------------------------------
    # CONFIGURATION: Modify this per physical Raspberry Pi!
    # Valid assignments: "action_hall", "library", "fabrication"
    # ---------------------------------------------------------
    MY_LOCATION_ID = "action_hall" 
    SERVER_IP = "ws://192.168.1.100:9001/" # Put your Nurse Pi's real IP here
    
    node = ClientNode(MY_LOCATION_ID, SERVER_IP)
    node.run()
