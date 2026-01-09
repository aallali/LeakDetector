"""
Example: Resource Leak - File Handles Not Closed
File handles accumulate in memory, file descriptor limit exceeded
"""

class LogProcessor:
    def __init__(self):
        self.files = []
    
    def process_logs(self, filenames):
        for filename in filenames:
            # LEAK: File opened but never closed
            f = open(filename, 'r')
            self.files.append(f)
            
            # Process file
            content = f.read()
            process_data(content)
            
            # BUG: Missing f.close()

class DataAnalyzer:
    def __init__(self):
        self.connections = {}
    
    def connect_db(self, db_name):
        # LEAK: Connection created and stored
        import sqlite3
        conn = sqlite3.connect(db_name)
        self.connections[db_name] = conn
        return conn
    
    def disconnect_all(self):
        # BUG: Never closes connections
        self.connections.clear()  # Just removes reference, doesn't close!

# Usage that causes leak
processor = LogProcessor()
for i in range(10000):
    processor.process_logs([f"log_{i}.txt"])
    # After loop: 10000 file handles open, consuming file descriptors

# Resource leak: OS limit on open files usually 1024-4096
# This code will eventually fail with "Too many open files"

def process_data(content):
    pass