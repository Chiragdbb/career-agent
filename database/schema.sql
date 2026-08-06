CREATE TABLE companies (
     id SERIAL PRIMARY KEY,
     name TEXT NOT NULL,
     url TEXT,
     created_at TIMESTAMP DEFAULT now()
   );

   CREATE TABLE jobs (
     id SERIAL PRIMARY KEY,
     company_id INTEGER REFERENCES companies(id),
     title TEXT NOT NULL,
     url TEXT,
     description TEXT,
     posted_at TIMESTAMP,
     created_at TIMESTAMP DEFAULT now()
   );

   CREATE TABLE applications (
     id SERIAL PRIMARY KEY,
     job_id INTEGER REFERENCES jobs(id),
     status TEXT DEFAULT 'not_applied',
     applied_at TIMESTAMP,
     created_at TIMESTAMP DEFAULT now()
   );