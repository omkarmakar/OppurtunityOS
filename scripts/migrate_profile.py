import sqlite3

conn = sqlite3.connect('data/opportunity.db')
cur = conn.cursor()

# Add name column if missing
try:
    cur.execute('ALTER TABLE profiles ADD COLUMN name VARCHAR(100) NOT NULL DEFAULT "Profile 1"')
    print('Added name column')
except Exception as e:
    print('name column:', e)

# Drop unique constraint on user_id if it exists
try:
    cur.execute('DROP INDEX IF EXISTS uq_profiles_user_id')
    print('Dropped unique index')
except Exception as e:
    print('unique index:', e)

# Create non-unique index
try:
    cur.execute('CREATE INDEX IF NOT EXISTS ix_profiles_user_id ON profiles(user_id)')
    print('Created non-unique index')
except Exception as e:
    print('index:', e)

# Add profile_id to opportunities
try:
    cur.execute('ALTER TABLE opportunities ADD COLUMN profile_id UUID')
    print('Added profile_id column')
except Exception as e:
    print('profile_id:', e)

conn.commit()
conn.close()
print('Done')