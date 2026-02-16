import sqlite3


def fix_database_schema_simplified(db_path="cv_database.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Checking for existing parsed data...")
        cursor.execute("SELECT COUNT(*) FROM parsed_cvs_enhanced")
        count = cursor.fetchone()[0]
        print(f"Found {count} existing parsed CVs")

        if count > 0:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parsed_cvs_backup AS 
                SELECT * FROM parsed_cvs_enhanced
            """)
            print("Created backup table")

        cursor.execute('DROP TABLE IF EXISTS parsed_cvs_enhanced')
        cursor.execute('DROP TABLE IF EXISTS cv_certifications_enhanced')

        print("Creating new simplified schema...")

        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS parsed_cvs_enhanced
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           metadata_id
                           INTEGER,
                           raw_text
                           TEXT,
                           full_name
                           TEXT,
                           email_parsed
                           TEXT,
                           phone_parsed
                           TEXT,
                           location
                           TEXT,
                           linkedin
                           TEXT,
                           github
                           TEXT,
                           website
                           TEXT,
                           highest_degree
                           TEXT,
                           field_of_study
                           TEXT,
                           university_parsed
                           TEXT,
                           graduation_year
                           TEXT,
                           all_technical_skills
                           TEXT,
                           programming_languages
                           TEXT,
                           frameworks
                           TEXT,
                           tools_and_technologies
                           TEXT,
                           soft_skills
                           TEXT,
                           projects
                           TEXT,
                           latest_position
                           TEXT,
                           latest_company
                           TEXT,
                           total_experience_years
                           INTEGER,
                           total_skills_count
                           INTEGER,
                           total_certifications
                           INTEGER,
                           complete_parsed_json
                           TEXT,
                           parsing_status
                           TEXT
                           DEFAULT
                           'pending',
                           parsing_error
                           TEXT,
                           parsed_at
                           TIMESTAMP,
                           tokens_used
                           INTEGER,
                           api_key_used
                           INTEGER,
                           FOREIGN
                           KEY
                       (
                           metadata_id
                       ) REFERENCES cv_metadata
                       (
                           id
                       )
                           )
                       ''')

        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS cv_certifications_enhanced
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           parsed_cv_id
                           INTEGER,
                           certification_name
                           TEXT,
                           issuer
                           TEXT,
                           issue_date
                           TEXT,
                           credential_id
                           TEXT,
                           FOREIGN
                           KEY
                       (
                           parsed_cv_id
                       ) REFERENCES parsed_cvs_enhanced
                       (
                           id
                       )
                           )
                       ''')

        conn.commit()
        print("Database schema updated successfully!")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    fix_database_schema_simplified()