# Schema notes

Postgres stores job and application data for the career agent (finding jobs, tailoring resumes, tracking applications). Exposed via MCP; Cursor is the interface.

## Tables

companies - employers you find or apply to (name, url)
jobs - roles at a company (title, url, description, posted_at)
applications - application status and applied_at for a job
contacts - people at a company (recruiters, hiring managers)
resumes - tailored resume versions for applications
emails - outreach / correspondence tied to an application
interviews - interview rounds tied to an application
