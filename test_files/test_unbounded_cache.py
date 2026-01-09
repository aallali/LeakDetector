"""
Example: Unbounded Cache Growth
This will leak memory indefinitely as cache grows without cleanup
"""

class DataCache:
    def __init__(self):
        self.cache = {}  # Never cleared!
    
    def get_user(self, user_id):
        if user_id not in self.cache:
            # Simulate expensive operation
            data = {"id": user_id, "name": f"User {user_id}", "metadata": "x" * 10000}
            self.cache[user_id] = data  # Add to cache
        return self.cache[user_id]
    
    def process_batch(self, user_ids):
        results = []
        for uid in user_ids:
            results.append(self.get_user(uid))  # Cache grows linearly
        return results

# Usage that causes leak
cache = DataCache()
for i in range(100000):
    cache.process_batch(range(1000, 2000))  # Each iteration adds 1000 users to cache

# By end: cache has grown to gigabytes, never cleaned