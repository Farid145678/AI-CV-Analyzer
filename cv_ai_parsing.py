# Quick fix for the database schema issue
# Run this once to update your existing database

import sqlite3


def fix_database_schema(db_path="cv_database.db"):
    """Fix the database schema to match the new categorization system"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # First, backup existing data if any
        print("Checking for existing parsed data...")
        cursor.execute("SELECT COUNT(*) FROM parsed_cvs_enhanced")
        count = cursor.fetchone()[0]
        print(f"Found {count} existing parsed CVs")

        if count > 0:
            # Create backup table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parsed_cvs_backup AS 
                SELECT * FROM parsed_cvs_enhanced
            """)
            print("Created backup table")

        # Drop and recreate the table with correct schema
        cursor.execute('DROP TABLE IF EXISTS parsed_cvs_enhanced')
        cursor.execute('DROP TABLE IF EXISTS cv_certifications_enhanced')

        print("Creating new schema with software/AI/data science categories...")

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

                           -- Updated skill categories focused on software/AI/data science
                           all_technical_skills
                           TEXT,
                           programming_languages
                           TEXT,
                           web_frameworks
                           TEXT,
                           ai_ml_frameworks
                           TEXT,
                           data_science_tools
                           TEXT,
                           databases
                           TEXT,
                           cloud_platforms
                           TEXT,
                           devops_tools
                           TEXT,
                           data_visualization
                           TEXT,
                           big_data_tools
                           TEXT,
                           mobile_development
                           TEXT,
                           desktop_frameworks
                           TEXT,
                           version_control
                           TEXT,
                           operating_systems
                           TEXT,
                           development_tools
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
        print("You can now run the CV processing again.")

    except Exception as e:
        print(f"Error updating schema: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    fix_database_schema()