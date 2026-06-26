import json
import logging
from websocket_server import WebsocketServer
from gpiozero import LED, Button

# --- 1. Hardware Initialization ---
locations = {
    "action_hall": {"led": LED(17), "btn": Button(22), "state": 0},
    "library":     {"led": LED(27), "btn": Button(23), "state": 0},
    "fabrication": {"led": LED(24), "btn": Button(25), "state": 0}
}

# Dictionary to map connected websockets to client IDs
connected_clients = {}

def update_server_leds(loc_id):
    """Updates the physical server LEDs based on the current state."""
    state = locations[loc_id]["state"]
    led = locations[loc_id]["led"]
    
    if state == 0:     # Idle
        led.off()
    elif state == 1:   # Client requested help (Flashing)
        led.blink(on_time=0.5, off_time=0.5)
    elif state == 2:   # Nurse acknowledged (Solid)
        led.on()

# --- 2. Hardware Button Callbacks ---
def nurse_button_pressed(loc_id):
    """Triggered when the Nurse presses a physical button on the Server Pi."""
    if locations[loc_id]["state"] == 1:
        locations[loc_id]["state"] = 2
        update_server_leds(loc_id)
        
        # Notify the specific client and the Server web UI
        payload = json.dumps({"sender": "server", "action": "state_change", "state": 2, "target": loc_id})
        server.send_message_to_all(payload) # Server UI catches this to update its dashboard
        if loc_id in connected_clients:
            server.send_message(connected_clients[loc_id], payload)

locations["action_hall"]["btn"].when_pressed = lambda: nurse_button_pressed("action_hall")
locations["library"]["btn"].when_pressed     = lambda: nurse_button_pressed("library")
locations["fabrication"]["btn"].when_pressed = lambda: nurse_button_pressed("fabrication")

# --- 3. WebSocket Callbacks ---
def new_client(client, server_obj):
    print(f"New connection: ID {client['id']}")

def client_left(client, server_obj):
    # Remove client from our routing dictionary if they disconnect
    for loc_id, c in list(connected_clients.items()):
        if c['id'] == client['id']:
            del connected_clients[loc_id]
            print(f"{loc_id} disconnected.")

def message_received(client, server_obj, message):
    try:
        data = json.loads(message)
        sender = data.get("sender")
        action = data.get("action")
        
        # 1. Registration: When a client first connects, it registers its ID
        if action == "register":
            connected_clients[sender] = client
            print(f"Registered: {sender}")
            
        # 2. State Change: A client pressed ACK (state 1) or RST (state 0)
        elif action == "state_change":
            locations[sender]["state"] = data["state"]
            update_server_leds(sender)
            # Broadcast to update the Server HTML dashboard
            server_obj.send_message_to_all(message)

        # 3. Message Routing: Server Web UI sends a message to a specific client
        elif action == "send_msg" and sender == "server_ui":
            target = data.get("target")
            if target in connected_clients:
                server_obj.send_message(connected_clients[target], message)
                
    except json.JSONDecodeError:
        print("Received non-JSON message.")

# --- 4. Start Server ---
IP_ADDR = "192.168.1.100"
PORT = 9001
server = WebsocketServer(port=PORT, host=IP_ADDR, loglevel=logging.INFO)
server.set_fn_new_client(new_client)
server.set_fn_client_left(client_left)
server.set_fn_message_received(message_received)

print(f"Nurse Server running on ws://{IP_ADDR}:{PORT}")
server.run_forever()