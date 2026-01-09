"""
Example: Global Data Accumulation
Global variable stores data that grows indefinitely
"""

# GLOBAL LEAK: Never cleared
request_log = []
session_cache = {}
temp_data = []

class RequestHandler:
    def process_request(self, request):
        # Every request appended to global log
        request_log.append({
            'timestamp': get_time(),
            'path': request['path'],
            'headers': request['headers'],
            'body': request['body']  # Could be large
        })
        
        # Session stored globally, never cleaned
        session_id = request['session_id']
        session_cache[session_id] = {
            'user': request['user'],
            'data': 'x' * 100000,  # Large payload
            'nested': get_large_object()
        }
        
        return f"Processed {request['path']}"

class DataProcessor:
    def process_batch(self, items):
        for item in items:
            # Accumulates temporary data in global list
            temp_data.append({
                'item': item,
                'processed': expensive_transform(item),
                'metadata': 'x' * 50000
            })
        
        # BUG: Never clears temp_data
        # After 1000 batches of 100 items = 100k global objects

# Simulate server receiving requests
handler = RequestHandler()
processor = DataProcessor()

for hour in range(24):
    for minute in range(60):
        # Per minute request
        handler.process_request({
            'session_id': f'session_{hour}_{minute}',
            'path': '/api/data',
            'headers': {'X-User': 'test'},
            'body': 'x' * 10000,
            'user': f'user_{hour}'
        })
        
        # Per minute batch processing
        processor.process_batch(range(100))

# After 24 hours:
# - request_log: 1440 requests
# - session_cache: 1440 sessions
# - temp_data: 144000 temp items
# All accumulated globally, never cleaned

print(f"Request log size: {len(request_log)}")
print(f"Session cache size: {len(session_cache)}")
print(f"Temp data size: {len(temp_data)}")

def get_time():
    return "2024-01-01T00:00:00"

def get_large_object():
    return {'data': 'x' * 1000000}

def expensive_transform(item):
    return {'result': 'x' * 100000}