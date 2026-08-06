CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    title TEXT NOT NULL,
    url TEXT,
    description TEXT,
    posted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE applications (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    status TEXT,
    applied_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE contacts (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    name TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE resumes (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    name TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    title TEXT,
    description TEXT,
    status TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE interviews (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    title TEXT,
    status TEXT,
    created_at TIMESTAMP DEFAULT now()
);
