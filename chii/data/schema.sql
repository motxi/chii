CREATE TABLE IF NOT EXISTS custom_roles (
    user_id INTEGER PRIMARY KEY,
    role_id INTEGER NOT NULL,
    role_name TEXT NOT NULL,
    role_color TEXT NOT NULL
);
