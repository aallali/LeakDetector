"""
Example: Event Listener Memory Leak
Listeners never removed, accumulate in memory
"""

class EventEmitter:
    def __init__(self):
        self.listeners = {}
    
    def on(self, event, callback):
        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append(callback)
    
    def emit(self, event, data):
        if event in self.listeners:
            for callback in self.listeners[event]:
                callback(data)

class WebSocketHandler:
    def __init__(self):
        self.emitter = EventEmitter()
    
    def on_connection(self):
        # LEAK: New listener registered every connection, never removed
        def handle_message(data):
            print(f"Message: {data}")
        
        self.emitter.on('message', handle_message)
        
        # If this connection handler is called 1000 times,
        # listeners list grows to 1000 with same handler
    
    def on_disconnect(self):
        # BUG: Never removes listener
        pass

# Simulate connections
handler = WebSocketHandler()
for i in range(10000):
    handler.on_connection()
    # After 10k connections, listeners dict has 10k duplicate handlers

print(f"Total listeners: {len(handler.emitter.listeners['message'])}")  # 10000!