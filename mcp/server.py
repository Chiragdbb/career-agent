from mcp.server.fastmcp import FastMCP

from db import get_connection

mcp = FastMCP("career-agent")


@mcp.tool()
def save_company(name: str, url: str = "") -> str:
    """Insert a company into the companies table and return confirmation with its id."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO companies (name, url) VALUES (%s, %s) RETURNING id",
            (name, url or None),
        )
        company_id = cur.fetchone()[0]
        conn.commit()
        return f"Saved company '{name}' with id {company_id}"
    finally:
        cur.close()
        conn.close()


@mcp.tool()
def save_job(
    title: str, company: str, url: str = "", description: str = ""
) -> str:
    """Look up or create a company, insert a job linked to it, return confirmation with job id."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM companies WHERE name = %s", (company,))
        row = cur.fetchone()
        if row:
            company_id = row[0]
        else:
            cur.execute(
                "INSERT INTO companies (name) VALUES (%s) RETURNING id",
                (company,),
            )
            company_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO jobs (company_id, title, url, description)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (company_id, title, url or None, description or None),
        )
        job_id = cur.fetchone()[0]
        conn.commit()
        return f"Saved job '{title}' with id {job_id}"
    finally:
        cur.close()
        conn.close()


@mcp.tool()
def list_jobs() -> list[dict]:
    """Return the 20 most recent jobs with id, title, and company_id."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, title, company_id
            FROM jobs
            ORDER BY created_at DESC
            LIMIT 20
            """
        )
        return [
            {"id": row[0], "title": row[1], "company_id": row[2]}
            for row in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


@mcp.tool()
def save_application(job_id: int, status: str = "not_applied") -> str:
    """Insert an application for a job and return confirmation with its id."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO applications (job_id, status) VALUES (%s, %s) RETURNING id",
            (job_id, status),
        )
        application_id = cur.fetchone()[0]
        conn.commit()
        return f"Saved application with id {application_id}"
    finally:
        cur.close()
        conn.close()


@mcp.tool()
def list_applications() -> list[dict]:
    """Return the 20 most recent applications with id, job_id, and status."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, job_id, status
            FROM applications
            ORDER BY created_at DESC
            LIMIT 20
            """
        )
        return [
            {"id": row[0], "job_id": row[1], "status": row[2]}
            for row in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    mcp.run()
