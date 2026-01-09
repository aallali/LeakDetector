"""
Example: Circular Reference Memory Leak
Objects reference each other, preventing garbage collection
"""

class User:
    def __init__(self, name, company=None):
        self.name = name
        self.company = company
        if company:
            # LEAK: User references Company AND Company references User
            company.users.append(self)

class Company:
    def __init__(self, name):
        self.name = name
        self.users = []

# Create circular reference
company = Company("TechCorp")
users = []

for i in range(1000):
    user = User(f"User_{i}", company)
    users.append(user)

# Circular references:
# User -> Company -> List[User] -> User (cycle!)
# 
# Even if we delete company reference, users list keeps company alive
# And company.users keeps users alive
# GC can't clean because of cycle

del company  # Still in memory! Users keep reference via company.users
del users    # Still in memory! Company keeps reference via users list

# Result: ~1000 User objects + 1 Company object stuck in memory