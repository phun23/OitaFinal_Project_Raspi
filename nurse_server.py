import json
import logging
import time
from websocket_server import WebsocketServer
from gpiozero import LED, Button

# --- 1. Hardware State Trackers & Pin Mapping ---
locations = {
    "action_hall": {"led": LED(17), "btn": Button(22), "state": 0, "last_press": 0},
    "library":     {"led": LED(27), "btn": Button(23), "state": 0, "last_press": 0},
    "fabrication": {"led": LED(24), "btn": Button(25), "state": 0, "last_press": 0}
}

# Lookup table to map connection streams to Client IDs
connected_clients = {}

def update_server_leds(loc_id):
    """Controls server-side physical indicator lights based on current states"""
    state = locations[loc_id]["state"]
    led = locations[loc_id]["led"]
    
    if state == 0:     # Idle
        led.off()
    elif state == 1:   # Emergency (Flashing)
        led.blink(on_time=0.5, off_time=0.5)
    elif state == 2:   # Handled / Acknowledged (Solid On)
        led.on()

# --- 2. Server Physical Button Callback ---
def nurse_button_pressed(loc_id):
    """Fires when the Nurse presses a physical button on the main panel"""
    current_time = time.time()
    
    # Software bounce guard for the server buttons (400ms cooldown)
    if (current_time - locations[loc_id]["last_press"]) < 0.4:
        return
    locations[loc_id]["last_press"] = current_time

    # Nurse can only advance state if assistance is actively requested (State 1)
    if locations[loc_id]["state"] == 1:
        locations[loc_id]["state"] = 2
        update_server_leds(loc_id)
        
        # Build payload to synchronize Web UI dashboard and the specific physical client
        payload = json.dumps({"sender": "server", "action": "state_change", "state": 2, "target": loc_id})
        server.send_message_to_all(payload) 
        
        if loc_id in connected_clients:
            server.send_message(connected_clients[loc_id], payload)
        print(f"[Server Hardware] Nurse acknowledged {loc_id} using physical panel.")

# Bind events safely to server buttons
locations["action_hall"]["btn"].when_pressed = lambda: nurse_button_pressed("action_hall")
locations["library"]["btn"].when_pressed     = lambda: nurse_button_pressed("library")
locations["fabrication"]["btn"].when_pressed = lambda: nurse_button_pressed("fabrication")

# --- 3. WebSocket Protocol & Network Routine ---
def new_client(client, server_obj):
    print(f"New network connection established: ID {client['id']}")

def client_left(client, server_obj):
    for loc_id, c in list(connected_clients.items()):
        if c['id'] == client['id']:
            del connected_clients[loc_id]
            print(f"🔌 Node '{loc_id}' disconnected from the network topology.")

def message_received(client, server_obj, message):
    try:
        data = json.loads(message)
        sender = data.get("sender")
        action = data.get("action")
        
        # Handle Node Registrations
        if action == "register":
            connected_clients[sender] = client
            print(f"✅ Route registered for endpoint: '{sender}'")
            
        # Handle System-wide State Synchronization
        elif action == "state_change":
            target = data.get("target") or sender
            locations[target]["state"] = data["state"]
            update_server_leds(target)
            
            # Broadcast globally so Web Dashboards mirror the change instantly
            server_obj.send_message_to_all(message)
            
            # If state 2 was triggered by the HTML Web UI, pass it downstream to physical Pi
            if sender == "server" and data["state"] == 2 and target in connected_clients:
                server_obj.send_message(connected_clients[target], message)

        # Handle Target-Specific Text Transmissions from Nurse Station
        elif action == "send_msg" and sender == "server_ui":
            target = data.get("target")
            if target in connected_clients:
                server_obj.send_message(connected_clients[target], message)
                print(f"✉️ Target-routed message sent to {target}: '{data.get('message')}'")
                
    except json.JSONDecodeError:
        pass

# --- 4. Bind and Spin Up Server Engine ---
IP_ADDR = "192.168.1.100"  # Verify this matches your Server Pi's actual IP address
PORT = 9001

server = WebsocketServer(port=PORT, host=IP_ADDR, loglevel=logging.INFO)
server.set_fn_new_client(new_client)
server.set_fn_client_left(client_left)
server.set_fn_message_received(message_received)

print(f"🏥 Nurse Server Engine actively running on ws://{IP_ADDR}:{PORT}")
server.run_forever()
