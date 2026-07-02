import websocket
import json
import time
import _thread as thread  # Used to prevent the code from blocking/hanging
from gpiozero import LED, Button

# Force WebSocket to output everything it's doing under the hood
websocket.enableTrace(True)

class ClientNode:
    def __init__(self, client_id, host_addr):
        self.client_id = client_id
        self.current_state = 0 # Track current state locally (0=Idle, 1=Help, 2=Ack)
        
        # --- Hardware Mapping ---
        self.red_led = LED(17)
        self.yellow_led = LED(27)
        self.ack_btn = Button(22)
        self.rst_btn = Button(23)
        
        # Bind physical buttons to functions
        self.ack_btn.when_pressed = self.request_help
        self.rst_btn.when_pressed = self.reset_system
        
        # --- WebSocket Setup ---
        self.ws = websocket.WebSocketApp(host_addr,
            on_message = self.on_message,
            on_error = self.on_error,
            on_close = self.on_close)
        self.ws.on_open = self.on_open

    def request_help(self):
        """Triggered when physical 'Ack' button is pressed (State 1)"""
        print(f"\n[Hardware Alert] 'Ack' button pressed at {self.client_id}!")
        self.send_state(1)

    def reset_system(self):
        """Triggered when physical 'Rst' button is pressed (State 0)"""
        print(f"\n[Hardware Alert] 'Rst' button pressed at {self.client_id}!")
        self.send_state(0)

    def send_state(self, state):
        payload = {"sender": self.client_id, "action": "state_change", "state": state}
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(payload))
            print(f"[Sent] State {state} transmitted to server successfully.")
        else:
            print("[Error] Cannot send data. WebSocket is disconnected!")

    def on_open(self, ws):
        print(f"\n⚡ [Connected] Successfully hooked to Nurse Server as: {self.client_id}")
        # Register ID immediately
        payload = {"sender": self.client_id, "action": "register"}
        self.ws.send(json.dumps(payload))

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            action = data.get("action")
            
            if action == "state_change":
                target = data.get("target") or data.get("sender")
                if target == self.client_id:
                    self.current_state = data.get("state")
                    self.update_hardware_leds()

            elif action == "send_msg" and data.get("target") == self.client_id:
                print(f"\n📬 [MESSAGE FROM NURSE OFFICE]: {data.get('message')}\n")

        except json.JSONDecodeError:
            print(f"[Raw Data Received]: {message}")

    def update_hardware_leds(self):
        """Controls local LEDs safely based on global synchronized state"""
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
        print(f"❌ [WebSocket Error]: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print(f"🔌 [Disconnected]: Connection closed ({close_status_code}: {close_msg})")

    def run(self):
        # Start the network loop in a background thread so it NEVER blocks your terminal execution
        thread.start_new_thread(self.ws.run_forever, ())
        
        # Main Thread Loop: Keeps the script alive and constantly prints status updates
        print("\n--- Starting Active Status Monitor ---")
        state_labels = {0: "🟢 IDLE (All clear)", 1: "🔴 WARNING (Assistance Requested)", 2: "🟡 ACKNOWLEDGED (Nurse on the way)"}
        
        try:
            while True:
                current_label = state_labels.get(self.current_state, "Unknown")
                print(f"[Live Status Update] Node: {self.client_id} | Current Mode: {current_label}", end="\r")
                time.sleep(2) # Refresh status string every 2 seconds without flooding lines
        except KeyboardInterrupt:
            print("\nShutting down client node monitoring...")

if __name__ == "__main__":
    # ---------------------------------------------------------
    # CONFIGURATION: Change this target per Pi!
    # Options: "action_hall", "library", "fabrication"
    # ---------------------------------------------------------
    MY_LOCATION_ID = "action_hall" 
    SERVER_IP = "ws://192.168.1.100:9001/"
    
    node = ClientNode(MY_LOCATION_ID, SERVER_IP)
    node.run()
