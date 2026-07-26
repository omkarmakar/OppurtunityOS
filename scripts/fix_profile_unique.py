import sqlite3

conn = sqlite3.connect('data/opportunity.db')
cur = conn.cursor()

# Get existing profiles data
cur.execute('SELECT id, user_id, name, display_name, avatar_url, bio, education, experience, skills, preferred_locations, salary_expectations, target_companies, keywords, resume_path, linkedin_url, github_url, portfolio, projects, preferences, created_at, updated_at FROM profiles')
rows = cur.fetchall()

print(f"Backing up {len(rows)} profiles")

# Drop and recreate without unique constraint
cur.execute('DROP TABLE IF EXISTS profiles_backup')
cur.execute('''
    CREATE TABLE profiles_backup (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL,
        name VARCHAR(100) NOT NULL DEFAULT 'Profile 1',
        display_name VARCHAR(100),
        avatar_url VARCHAR(500),
        bio TEXT,
        education JSON,
        experience JSON,
        skills JSON,
        preferred_locations JSON,
        salary_expectations VARCHAR(200),
        target_companies JSON,
        keywords JSON,
        resume_path VARCHAR(500),
        linkedin_url VARCHAR(500),
        github_url VARCHAR(500),
        portfolio VARCHAR(500),
        projects JSON,
        preferences JSON,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
''')

# Copy data - include all 22 columns
for row in rows:
    cur.execute('''
        INSERT INTO profiles_backup 
        (id, user_id, name, display_name, avatar_url, bio, education, experience, skills, preferred_locations, salary_expectations, target_companies, keywords, resume_path, linkedin_url, github_url, portfolio, projects, preferences, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', row)

print("Data backed up")

# Drop old table and rename
cur.execute('DROP TABLE profiles')
cur.execute('ALTER TABLE profiles_backup RENAME TO profiles')

# Create non-unique index
cur.execute('CREATE INDEX IF NOT EXISTS ix_profiles_user_id ON profiles(user_id)')

conn.commit()
conn.close()
print("Migration complete - unique constraint removed")