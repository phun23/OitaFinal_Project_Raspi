import websocket
import json
from gpiozero import LED, Button

class ClientNode:
    def __init__(self, client_id, host_addr):
        self.client_id = client_id
        
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
            on_open = self.on_open)

    # --- Button Actions ---
    def request_help(self):
        """Triggered when physical 'Ack' button is pressed (State 1)"""
        print("Help requested! Sending to server...")
        self.send_state(1)

    def reset_system(self):
        """Triggered when physical 'Rst' button is pressed (State 0)"""
        print("System reset. Sending to server...")
        self.send_state(0)

    def send_state(self, state):
        """Builds JSON payload and sends to Nurse Server"""
        payload = {"sender": self.client_id, "action": "state_change", "state": state}
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(payload))

    # --- WebSocket Actions ---
    def on_open(self, ws):
        print(f"Connected to Nurse Server as: {self.client_id}")
        # Register this client's ID with the server immediately upon connecting
        payload = {"sender": self.client_id, "action": "register"}
        self.ws.send(json.dumps(payload))

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            action = data.get("action")
            
            # 1. Handle State Changes (Controls the local physical LEDs)
            if action == "state_change":
                # Check if this broadcast is meant for this specific client
                target = data.get("target") or data.get("sender")
                if target == self.client_id:
                    state = data.get("state")
                    
                    if state == 0:   # Idle / Reset
                        self.red_led.off()
                        self.yellow_led.off()
                        print("[Status]: Idle")
                    elif state == 1: # Help Requested
                        self.red_led.on()
                        self.yellow_led.off()
                        print("[Status]: Warning Alert (Red)")
                    elif state == 2: # Nurse Acknowledged
                        self.red_led.off()
                        self.yellow_led.on()
                        print("[Status]: Nurse is on the way (Yellow)")

            # 2. Handle Text Messages sent specifically to this location
            elif action == "send_msg" and data.get("target") == self.client_id:
                msg = data.get("message")
                print(f"\n============================")
                print(f"MESSAGE FROM NURSE: {msg}")
                print(f"============================\n")

        except json.JSONDecodeError:
            pass

    def run(self):
        # Keeps the connection open and listens for physical button presses
        self.ws.run_forever()

if __name__ == "__main__":
    # ---------------------------------------------------------
    # CONFIGURATION: Change this for each Pi before running!
    # Valid options: "action_hall", "library", "fabrication"
    # ---------------------------------------------------------
    MY_LOCATION_ID = "action_hall" 
    SERVER_IP = "ws://192.168.1.100:9001/"
    
    node = ClientNode(MY_LOCATION_ID, SERVER_IP)
    node.run()