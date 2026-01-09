"""
Example: N+1 Query Pattern
Loop executes query for each item instead of batch - memory pressure
"""

class UserRepository:
    def __init__(self):
        self.db = MockDatabase()
    
    def get_users_with_posts(self, user_ids):
        """LEAK: 1 + N queries instead of 2"""
        users = []
        
        # Query 1: Get all users
        for uid in user_ids:
            # BUG: Query in loop instead of batch
            user = self.db.query("SELECT * FROM users WHERE id = ?", [uid])
            
            # Query 2+N: Get posts for each user
            posts = self.db.query("SELECT * FROM posts WHERE user_id = ?", [uid])
            user['posts'] = posts
            
            users.append(user)
        
        return users

class PostProcessor:
    def __init__(self):
        self.data = []
    
    def process_items(self, items):
        # LEAK: Loop makes API calls sequentially
        for item in items:
            # Each call holds response in memory before processing
            response = self.call_api(f"/api/item/{item['id']}")
            
            # Process response
            processed = self.expensive_processing(response)
            self.data.append(processed)  # Accumulates
        
        return self.data

# Usage causing memory pressure
repo = UserRepository()
user_ids = range(10000)

# This executes 10001 queries instead of 2:
# 1 query to get users
# 10000 queries to get posts (one per user)
users = repo.get_users_with_posts(user_ids)

# Memory accumulates because:
# - Each query result held in memory
# - All results combined at end
# - Could result in GBs of data

def mock_api_call():
    pass

class MockDatabase:
    def query(self, sql, params):
        return {"id": params[0], "data": "x" * 1000}