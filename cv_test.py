# Multi-API Key CV Parser with Automatic Rotation
# Rotates between multiple Gemini API keys when limits are hit

import sqlite3
import pandas as pd
import requests
import io
import PyPDF2
import google.generativeai as genai
from datetime import datetime, timedelta
import json
import re
import time
import os
from typing import Dict, Optional, Tuple, List
import logging
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MultiAPIKeyParser:
    def __init__(self, api_keys: List[str], db_path: str = "cv_database.db"):
        """
        Multi-API Key CV Parser with automatic rotation

        Args:
            api_keys: List of Gemini API keys
            db_path: Database path
        """
        self.api_keys = api_keys
        self.db_path = db_path
        self.current_key_index = 0
        self.key_usage = {}  # Track usage for each key
        self.failed_keys = set()  # Track failed keys

        # Initialize all API keys and test them
        self.working_keys = []
        self._test_all_keys()

        if not self.working_keys:
            logger.error("No working API keys found!")
            self.model = None
        else:
            self._set_current_key(self.working_keys[0])

        self.init_database()

    def _test_all_keys(self):
        """Test all API keys to see which ones work"""
        print(f"Testing {len(self.api_keys)} API keys...")

        for i, api_key in enumerate(self.api_keys):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.0-flash-exp')

                # Test with a simple request
                response = model.generate_content("Hello",
                                                  generation_config=genai.types.GenerationConfig(max_output_tokens=10))

                if response and response.text:
                    self.working_keys.append(i)
                    self.key_usage[i] = 0
                    print(f"API Key {i + 1}: Working")
                else:
                    print(f"API Key {i + 1}: No response")

            except Exception as e:
                print(f"API Key {i + 1}: Failed - {str(e)[:100]}")
                self.failed_keys.add(i)

        print(f"Working keys: {len(self.working_keys)} out of {len(self.api_keys)}")

    def _set_current_key(self, key_index: int):
        """Set the current API key"""
        self.current_key_index = key_index
        genai.configure(api_key=self.api_keys[key_index])
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        logger.info(f"Using API Key {key_index + 1}")

    def _rotate_to_next_key(self) -> bool:
        """Rotate to next available API key"""
        if len(self.working_keys) <= 1:
            return False

        current_pos = self.working_keys.index(self.current_key_index)
        next_pos = (current_pos + 1) % len(self.working_keys)
        next_key = self.working_keys[next_pos]

        # Remove current key from working keys if it's exhausted
        if self.current_key_index in self.working_keys:
            self.working_keys.remove(self.current_key_index)
            self.failed_keys.add(self.current_key_index)

        if self.working_keys:
            self._set_current_key(self.working_keys[0])
            print(f"Rotated to API Key {self.current_key_index + 1}")
            return True

        return False

    def _is_quota_error(self, error_msg: str) -> bool:
        """Check if error indicates quota/rate limit exceeded"""
        error_lower = error_msg.lower()
        quota_indicators = [
            'quota', 'limit', 'exceeded', '429', 'rate limit',
            'too many requests', 'usage limit', 'daily limit'
        ]
        return any(indicator in error_lower for indicator in quota_indicators)

    def safe_api_call(self, prompt: str, max_tokens: int = 1000, max_retries: int = None) -> Optional[str]:
        """Make API call with automatic key rotation on quota exceeded"""

        if not self.working_keys:
            logger.error("No working API keys available")
            return None

        if max_retries is None:
            max_retries = len(self.working_keys)

        for attempt in range(max_retries):
            try:
                generation_config = genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=max_tokens,
                )

                response = self.model.generate_content(prompt, generation_config=generation_config)

                if response and response.text:
                    self.key_usage[self.current_key_index] += 1
                    return response.text

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"API Key {self.current_key_index + 1} error: {error_msg[:200]}")

                if self._is_quota_error(error_msg):
                    print(f"API Key {self.current_key_index + 1} quota exceeded. Rotating...")

                    if not self._rotate_to_next_key():
                        logger.error("All API keys exhausted")
                        return None

                    # Brief pause before retry
                    time.sleep(2)
                    continue
                else:
                    # Other error, wait a bit and retry with same key
                    time.sleep(1)
                    if attempt < max_retries - 1:
                        continue
                    else:
                        logger.error(f"Non-quota error after {max_retries} attempts: {error_msg}")
                        return None

        return None

    def extract_json_with_fixed_parsing(self, response_text: str):
        """Fixed JSON extraction"""
        response_text = response_text.strip()

        # Remove markdown formatting
        if "```json" in response_text:
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1).strip()
        elif "```" in response_text:
            json_match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1).strip()

        # Handle both JSON objects and arrays
        if '[' in response_text and ']' in response_text:
            start = response_text.find('[')
            bracket_count = 0
            end = -1
            for i, char in enumerate(response_text[start:], start):
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end = i + 1
                        break
            if start != -1 and end > start:
                response_text = response_text[start:end]

        elif '{' in response_text and '}' in response_text:
            start = response_text.find('{')
            brace_count = 0
            end = -1
            for i, char in enumerate(response_text[start:], start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            if start != -1 and end > start:
                response_text = response_text[start:end]

        # Clean up
        response_text = re.sub(r',\s*}', '}', response_text)
        response_text = re.sub(r',\s*]', ']', response_text)
        response_text = response_text.strip()

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            return None

    def init_database(self):
        """Initialize database with comprehensive schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create cv_metadata table if it doesn't exist
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS cv_metadata
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           name
                           TEXT,
                           email
                           TEXT,
                           phone
                           TEXT,
                           university
                           TEXT,
                           specialization
                           TEXT,
                           field_of_interest
                           TEXT,
                           drive_link
                           TEXT,
                           upload_timestamp
                           TEXT
                       )
                       ''')

        # Drop and recreate enhanced table
        cursor.execute('DROP TABLE IF EXISTS parsed_cvs_enhanced')
        cursor.execute('DROP TABLE IF EXISTS cv_certifications_enhanced')

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
                           cybersecurity_tools
                           TEXT,
                           programming_languages
                           TEXT,
                           frameworks_libraries
                           TEXT,
                           devops_tools
                           TEXT,
                           operating_systems
                           TEXT,
                           networking_tools
                           TEXT,
                           monitoring_tools
                           TEXT,
                           cloud_platforms
                           TEXT,
                           databases
                           TEXT,
                           version_control
                           TEXT,
                           virtualization
                           TEXT,
                           security_concepts
                           TEXT,
                           soft_skills
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
        conn.close()
        logger.info("Database initialized")

    def extract_file_id_from_drive_link(self, drive_link: str) -> Optional[str]:
        """Extract file ID from Google Drive link"""
        if not drive_link or "drive.google.com" not in drive_link:
            return None

        try:
            if "/open?id=" in drive_link:
                return drive_link.split("/open?id=")[1].split("&")[0]
            elif "/file/d/" in drive_link:
                return drive_link.split("/file/d/")[1].split("/")[0]
            return None
        except:
            return None

    def download_and_extract_text(self, drive_link: str) -> Tuple[Optional[str], str]:
        """Download and extract text from Google Drive"""
        file_id = self.extract_file_id_from_drive_link(drive_link)
        if not file_id:
            return None, "Could not extract file ID"

        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(download_url, headers=headers, timeout=20)

            if response.status_code == 200 and len(response.content) > 1000:
                file_content = io.BytesIO(response.content)

                try:
                    pdf_reader = PyPDF2.PdfReader(file_content)
                    text = ""
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"

                    if len(text.strip()) > 50:
                        return text.strip(), "PDF extracted successfully"
                except:
                    pass

            return None, "Could not extract text"
        except Exception as e:
            return None, f"Download error: {str(e)}"

    def extract_personal_info(self, cv_text: str) -> Dict:
        """Extract personal information using multi-API approach"""
        prompt = f"""Extract personal information from this CV. Return ONLY a JSON object:

{{
  "name": "full name",
  "email": "email address", 
  "phone": "phone number",
  "location": "city, country",
  "linkedin": "LinkedIn URL if found",
  "github": "GitHub URL if found"
}}

CV Text: {cv_text[:2000]}

JSON:"""

        response = self.safe_api_call(prompt, 500)
        if response:
            json_data = self.extract_json_with_fixed_parsing(response)
            if json_data and isinstance(json_data, dict):
                return json_data
        return {}

    def extract_all_skills(self, cv_text: str) -> List[str]:
        """Extract all skills using multi-API approach"""
        prompt = f"""Find EVERY skill, tool, technology, programming language, framework, platform, and technical ability mentioned in this CV.

Extract everything including:
- Programming languages (Python, Java, JavaScript, etc.)
- Cybersecurity tools (Kali Linux, Nmap, Burp Suite, Metasploit, etc.)
- Frameworks and libraries
- Operating systems
- Networking technologies
- Cloud platforms
- Databases
- DevOps tools
- Monitoring tools
- Security concepts
- Any other technical skills

Return as a JSON array of strings. Include EVERYTHING you find:

["skill1", "skill2", "skill3", ...]

CV Text: {cv_text}

JSON Array:"""

        response = self.safe_api_call(prompt, 1500)
        if response:
            json_data = self.extract_json_with_fixed_parsing(response)
            if json_data and isinstance(json_data, list):
                return json_data
        return []

    def extract_certifications_fixed(self, cv_text: str) -> List[Dict]:
        """Extract certifications using multi-API approach"""
        # Find certification section
        cert_section = ""
        lines = cv_text.split('\n')
        in_cert_section = False

        for line in lines:
            line_lower = line.lower().strip()
            if any(keyword in line_lower for keyword in ['license', 'certification', 'certificate', 'credential']):
                in_cert_section = True
                cert_section += line + "\n"
            elif in_cert_section:
                if any(keyword in line_lower for keyword in
                       ['honor', 'award', 'language', 'skill', 'experience']) and not any(
                    cert_keyword in line_lower for cert_keyword in ['certificate', 'certification']):
                    break
                cert_section += line + "\n"

        prompt = f"""Extract ALL certifications from this CV text.

Look for certificate names, issuing organizations, and dates.

{cert_section if cert_section else cv_text}

Return as JSON array:
[
  {{
    "name": "certification name",
    "issuer": "issuing organization", 
    "date": "issue date"
  }}
]

Include EVERY certification mentioned. JSON Array:"""

        response = self.safe_api_call(prompt, 1000)
        if response:
            json_data = self.extract_json_with_fixed_parsing(response)
            if json_data and isinstance(json_data, list):
                return json_data
        return []

    def extract_education_experience(self, cv_text: str) -> Dict:
        """Extract education and experience using multi-API approach"""
        prompt = f"""Extract education and work experience from this CV. Return ONLY JSON:

{{
  "education": {{
    "degree": "highest degree",
    "field": "field of study",
    "university": "university name",
    "graduation_year": "year"
  }},
  "latest_job": {{
    "position": "job title",
    "company": "company name",
    "duration": "employment period"
  }}
}}

CV Text: {cv_text[:3000]}

JSON:"""

        response = self.safe_api_call(prompt, 800)
        if response:
            json_data = self.extract_json_with_fixed_parsing(response)
            if json_data and isinstance(json_data, dict):
                return json_data
        return {}

    def categorize_skills(self, all_skills: List[str]) -> Dict[str, List[str]]:
        """Categorize skills into specific groups"""
        categories = {
            'cybersecurity_tools': [],
            'programming_languages': [],
            'frameworks_libraries': [],
            'devops_tools': [],
            'operating_systems': [],
            'networking_tools': [],
            'monitoring_tools': [],
            'cloud_platforms': [],
            'databases': [],
            'version_control': [],
            'virtualization': [],
            'security_concepts': [],
            'other_technical': []
        }

        category_keywords = {
            'cybersecurity_tools': ['kali', 'metasploit', 'nmap', 'burp', 'nikto', 'owasp', 'wireshark', 'crowdsec'],
            'programming_languages': ['python', 'java', 'javascript', 'c#', 'c++', 'go', 'rust', 'php', 'ruby', 'bash'],
            'frameworks_libraries': ['react', 'angular', 'vue', 'django', 'flask', 'spring', 'laravel', 'express'],
            'devops_tools': ['docker', 'kubernetes', 'terraform', 'ansible', 'jenkins', 'gitlab'],
            'operating_systems': ['linux', 'ubuntu', 'windows', 'centos', 'debian', 'rhel', 'macos'],
            'networking_tools': ['openvpn', 'wireguard', 'tcp/ip', 'dhcp', 'dns', 'iptables'],
            'monitoring_tools': ['prometheus', 'grafana', 'seq', 'nagios', 'zabbix'],
            'cloud_platforms': ['aws', 'azure', 'gcp', 'digitalocean', 'heroku'],
            'databases': ['mysql', 'postgresql', 'mongodb', 'redis', 'sqlite', 'oracle'],
            'version_control': ['git', 'github', 'gitlab', 'svn'],
            'virtualization': ['vmware', 'virtualbox', 'hyper-v', 'docker'],
            'security_concepts': ['intrusion detection', 'firewall', 'mfa', 'authentication', 'encryption']
        }

        for skill in all_skills:
            skill_lower = skill.lower()
            categorized = False

            for category, keywords in category_keywords.items():
                if any(keyword in skill_lower for keyword in keywords):
                    categories[category].append(skill)
                    categorized = True
                    break

            if not categorized:
                categories['other_technical'].append(skill)

        return categories

    def parse_cv_step_by_step(self, cv_text: str) -> Tuple[Optional[Dict], str, int]:
        """Parse CV using step-by-step approach with multi-API support"""
        if not self.working_keys:
            return None, "No working API keys available", 0

        if not cv_text or len(cv_text.strip()) < 30:
            return None, "CV text too short", 0

        total_tokens = 0

        try:
            logger.info("Step 1: Extracting personal information...")
            personal_info = self.extract_personal_info(cv_text)
            total_tokens += 100

            logger.info("Step 2: Extracting all skills...")
            all_skills = self.extract_all_skills(cv_text)
            total_tokens += 200

            logger.info("Step 3: Extracting certifications...")
            certifications = self.extract_certifications_fixed(cv_text)
            total_tokens += 150

            logger.info("Step 4: Extracting education and experience...")
            edu_exp = self.extract_education_experience(cv_text)
            total_tokens += 100

            logger.info("Step 5: Categorizing skills...")
            categorized_skills = self.categorize_skills(all_skills)

            complete_data = {
                'personal_info': personal_info,
                'all_skills': all_skills,
                'skills_categorized': categorized_skills,
                'certifications': certifications,
                'education': edu_exp.get('education', {}),
                'latest_job': edu_exp.get('latest_job', {}),
                'total_skills_count': len(all_skills),
                'total_certifications': len(certifications)
            }

            logger.info(f"Parsing completed: {len(all_skills)} skills, {len(certifications)} certifications")
            return complete_data, "Successfully parsed with multi-API", total_tokens

        except Exception as e:
            logger.error(f"Multi-API parsing error: {e}")
            return None, f"Parsing error: {str(e)}", total_tokens

    def get_usage_stats(self) -> Dict:
        """Get usage statistics for all API keys"""
        stats = {
            'total_keys': len(self.api_keys),
            'working_keys': len(self.working_keys),
            'failed_keys': len(self.failed_keys),
            'current_key': self.current_key_index + 1,
            'key_usage': {}
        }

        for i, usage in self.key_usage.items():
            stats['key_usage'][f'Key_{i + 1}'] = usage

        return stats

    def process_single_cv(self, metadata_id: int) -> Dict:
        """Process one CV with multi-API approach"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT id, name, drive_link FROM cv_metadata WHERE id = ?', (metadata_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return {"status": "error", "message": "CV not found"}

        cv_id, name, drive_link = result

        # Check if already processed
        cursor.execute('SELECT id FROM parsed_cvs_enhanced WHERE metadata_id = ?', (metadata_id,))
        if cursor.fetchone():
            conn.close()
            return {"status": "skipped", "message": "Already processed", "cv_id": cv_id, "name": name}

        conn.close()

        logger.info(f"Processing CV {cv_id}: {name}")

        # Extract text
        raw_text, extraction_status = self.download_and_extract_text(drive_link)
        if not raw_text:
            return {"status": "failed", "step": "extraction", "message": extraction_status, "cv_id": cv_id,
                    "name": name}

        # Parse with multi-API
        parsed_data, parse_status, tokens_used = self.parse_cv_step_by_step(raw_text)
        if not parsed_data:
            return {"status": "failed", "step": "parsing", "message": parse_status, "cv_id": cv_id, "name": name}

        # Store in database
        try:
            parsed_cv_id = self.store_parsed_cv(metadata_id, raw_text, parsed_data, tokens_used)

            return {
                "status": "success",
                "message": "CV processed successfully with multi-API",
                "cv_id": cv_id,
                "parsed_cv_id": parsed_cv_id,
                "name": name,
                "tokens_used": tokens_used,
                "api_key_used": self.current_key_index + 1,
                "extracted_name": parsed_data.get('personal_info', {}).get('name'),
                "total_skills": len(parsed_data.get('all_skills', [])),
                "certifications": len(parsed_data.get('certifications', [])),
                "linkedin": parsed_data.get('personal_info', {}).get('linkedin'),
                "github": parsed_data.get('personal_info', {}).get('github'),
                "location": parsed_data.get('personal_info', {}).get('location'),
                "skills_sample": parsed_data.get('all_skills', [])[:10],
                "certifications_sample": [cert.get('name', '') for cert in parsed_data.get('certifications', [])][:5]
            }

        except Exception as e:
            return {"status": "failed", "step": "storage", "message": str(e), "cv_id": cv_id, "name": name}

    def store_parsed_cv(self, metadata_id: int, raw_text: str, parsed_data: Dict, tokens_used: int) -> int:
        """Store parsed CV data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            personal_info = parsed_data.get('personal_info', {})
            skills_cat = parsed_data.get('skills_categorized', {})
            education = parsed_data.get('education', {})
            latest_job = parsed_data.get('latest_job', {})
            all_skills = parsed_data.get('all_skills', [])
            certifications = parsed_data.get('certifications', [])

            cursor.execute('''
                           INSERT INTO parsed_cvs_enhanced (metadata_id, raw_text, full_name, email_parsed,
                                                            phone_parsed, location, linkedin, github, website,
                                                            highest_degree, field_of_study, university_parsed,
                                                            graduation_year, all_technical_skills,
                                                            programming_languages,
                                                            frameworks_libraries, tools_and_technologies, soft_skills, projects,
                                                            latest_position, latest_company, total_skills_count,
                                                            total_certifications, complete_parsed_json, parsing_status,
                                                            parsed_at, tokens_used, api_key_used)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ''', (
                               metadata_id, raw_text[:10000],
                               personal_info.get('name'), personal_info.get('email'), personal_info.get('phone'),
                               personal_info.get('location'), personal_info.get('linkedin'),
                               personal_info.get('github'),
                               personal_info.get('website'),
                               education.get('degree'), education.get('field'), education.get('university'),
                               education.get('graduation_year'),
                               json.dumps(all_skills, ensure_ascii=False),
                               json.dumps(skills_cat.get('programming_languages', []), ensure_ascii=False),
                               json.dumps(skills_cat.get('frameworks', []), ensure_ascii=False),
                               json.dumps(skills_cat.get('tools_and_technologies', []), ensure_ascii=False),
                               json.dumps(skills_cat.get('soft_skills', []), ensure_ascii=False),
                               json.dumps([], ensure_ascii=False),  # Projects - empty for now, can be enhanced later
                               latest_job.get('position'), latest_job.get('company'),
                               len(all_skills), len(certifications),
                               json.dumps(parsed_data, ensure_ascii=False),
                               'completed', datetime.now(), tokens_used, self.current_key_index
                           ))

            parsed_cv_id = cursor.lastrowid

            # Insert certifications
            for cert in certifications:
                cursor.execute('''
                               INSERT INTO cv_certifications_enhanced (parsed_cv_id, certification_name, issuer, issue_date)
                               VALUES (?, ?, ?, ?)
                               ''', (
                                   parsed_cv_id,
                                   cert.get('name'),
                                   cert.get('issuer') if cert.get('issuer') not in ['null', 'NULL',
                                                                                    None] else 'Not specified',
                                   cert.get('date')
                               ))

            conn.commit()
            logger.info(f"CV stored: {len(all_skills)} skills, {len(certifications)} certifications")
            return parsed_cv_id

        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing CV: {e}")
            raise
        finally:
            conn.close()

    def load_metadata_from_excel(self, excel_path: str = None) -> Tuple[int, int]:
        """Load CV metadata from Excel"""
        if excel_path is None:
            for filename in os.listdir('.'):
                if filename.endswith('.xlsx') and '4SİM' in filename:
                    excel_path = filename
                    break

        if not excel_path:
            return 0, 0

        try:
            df = pd.read_excel(excel_path, engine='openpyxl')
            logger.info(f"Loaded Excel with {len(df)} rows")
        except Exception as e:
            logger.error(f"Error loading Excel: {e}")
            return 0, 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        successful = 0
        failed = 0

        for index, row in df.iterrows():
            try:
                name = str(row.get('Ad və Soyad', '')).strip()
                drive_link = str(row.get('Zəhmət olmasa CV-nizi PDF şəklində paylaşardınız', '')).strip()

                if not name or name.lower() in ['nan', 'aaaaa', '']:
                    failed += 1
                    continue

                if not drive_link or 'drive.google.com' not in drive_link:
                    failed += 1
                    continue

                cursor.execute('''
                               INSERT
                               OR IGNORE INTO cv_metadata 
                    (name, email, phone, university, specialization, field_of_interest, drive_link, upload_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                               ''', (
                                   name,
                                   str(row.get('E-mail ünvanınız', '')).strip(),
                                   str(row.get('Əlaqə nömrəniz', '')).strip(),
                                   str(row.get('Təhsil aldığınız müəssisə', '')).strip(),
                                   str(row.get('İxtisasınız', '')).strip(),
                                   str(row.get('Sahə: ai', '')).strip(),
                                   drive_link,
                                   str(row.get('Timestamp', '')).strip()
                               ))
                successful += 1

            except Exception as e:
                failed += 1

        conn.commit()
        conn.close()

        logger.info(f"Loaded {successful} CVs, {failed} failed")
        return successful, failed

    def list_available_cvs(self) -> List[Tuple]:
        """List all available CVs for processing"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT m.id,
                              m.name,
                              CASE WHEN p.id IS NOT NULL THEN 'Processed' ELSE 'Pending' END as status,
                              p.total_skills_count,
                              p.total_certifications,
                              p.api_key_used
                       FROM cv_metadata m
                                LEFT JOIN parsed_cvs_enhanced p ON m.id = p.metadata_id
                       ORDER BY m.id
                       ''')

        results = cursor.fetchall()
        conn.close()
        return results

    def process_multiple_cvs(self, cv_ids: List[int]) -> Dict:
        """Process multiple CVs with automatic API key rotation"""
        results = {
            'successful': [],
            'failed': [],
            'skipped': [],
            'total_processed': 0,
            'api_usage': {}
        }

        initial_working_keys = len(self.working_keys)

        for cv_id in cv_ids:
            if not self.working_keys:
                print("\nAll API keys exhausted! Cannot continue processing.")
                break

            print(f"\n--- Processing CV {cv_id} (API Key {self.current_key_index + 1}) ---")
            result = self.process_single_cv(cv_id)

            if result['status'] == 'success':
                results['successful'].append(result)
                print(f"✅ Success: {result['name']}")
                print(f"   Skills: {result['total_skills']}, Certifications: {result['certifications']}")
                print(f"   Used API Key: {result['api_key_used']}")
            elif result['status'] == 'skipped':
                results['skipped'].append(result)
                print(f"⏭️ Skipped: {result['name']} (already processed)")
            else:
                results['failed'].append(result)
                print(f"❌ Failed: {result['name']} - {result['message']}")

            results['total_processed'] += 1

            # Show current API key status
            stats = self.get_usage_stats()
            print(f"   Current API usage: {stats['key_usage']}")
            print(f"   Working keys remaining: {stats['working_keys']}")

            # Small delay between requests
            time.sleep(1)

        results['api_usage'] = self.get_usage_stats()
        return results


def test_multi_api_parser():
    """Test the multi-API key parser"""
    print("Multi-API Key CV Parser Test")
    print("=" * 50)

    # Get multiple API keys
    api_keys = []
    print("Enter your Gemini API keys (press Enter with empty input to finish):")

    key_count = 1
    while True:
        key = input(f"API Key {key_count}: ").strip()
        if not key:
            break
        api_keys.append(key)
        key_count += 1

    if not api_keys:
        print("No API keys provided")
        return

    print(f"\nInitializing parser with {len(api_keys)} API keys...")
    parser = MultiAPIKeyParser(api_keys)

    if not parser.working_keys:
        print("No working API keys found. Please check your keys.")
        return

    print("Loading metadata...")
    successful, failed = parser.load_metadata_from_excel()
    print(f"Loaded: {successful} successful, {failed} failed")

    if successful == 0:
        print("No CVs found to process")
        return

    # Show API key status
    stats = parser.get_usage_stats()
    print(f"\nAPI Key Status:")
    print(f"  Total keys: {stats['total_keys']}")
    print(f"  Working keys: {stats['working_keys']}")
    print(f"  Failed keys: {stats['failed_keys']}")
    print(f"  Current key: {stats['current_key']}")

    # List available CVs
    print("\nAvailable CVs:")
    available_cvs = parser.list_available_cvs()

    for cv_id, name, status, skills, certs, api_used in available_cvs:
        status_info = f"({skills} skills, {certs} certs)" if status == 'Processed' else ""
        api_info = f" [API Key {api_used}]" if api_used else ""
        print(f"  {cv_id}: {name} - {status} {status_info}{api_info}")

    print("\nProcessing options:")
    print("1. Process a single CV")
    print("2. Process multiple CVs (manual selection)")
    print("3. Process all pending CVs")
    print("4. Re-process a specific CV")
    print("5. Show API usage statistics")
    print("6. Select and save 10 CVs for next run")
    print("7. Continue from saved queue")
    print("8. Interactive CV selection (choose exactly what you want)")

    choice = input("\nEnter your choice (1-8): ").strip()

    if choice == '1':
        cv_id = input("Enter CV ID to process: ").strip()
        try:
            cv_id = int(cv_id)
            print(f"\nProcessing CV {cv_id}...")
            result = parser.process_single_cv(cv_id)

            print("\nProcessing Result:")
            print(json.dumps(result, indent=2, ensure_ascii=False))

            if result.get('status') == 'success':
                print(f"\nSuccess Details:")
                print(f"Name: {result.get('extracted_name', 'N/A')}")
                print(f"Total skills: {result.get('total_skills', 0)}")
                print(f"Certifications: {result.get('certifications', 0)}")
                print(f"API Key used: {result.get('api_key_used', 'N/A')}")
                print(f"LinkedIn: {result.get('linkedin', 'Not found')}")
                print(f"GitHub: {result.get('github', 'Not found')}")
                print(f"Location: {result.get('location', 'Not found')}")

            # Show updated API stats
            stats = parser.get_usage_stats()
            print(f"\nAPI Usage After Processing:")
            for key, usage in stats['key_usage'].items():
                print(f"  {key}: {usage} requests")

        except ValueError:
            print("Invalid CV ID")

    elif choice == '2':
        cv_ids_input = input("Enter CV IDs separated by commas (e.g., 1,2,3): ").strip()
        try:
            cv_ids = [int(x.strip()) for x in cv_ids_input.split(',')]
            print(f"\nProcessing {len(cv_ids)} CVs with automatic API rotation...")
            results = parser.process_multiple_cvs(cv_ids)

            print(f"\nBatch Processing Summary:")
            print(f"Successful: {len(results['successful'])}")
            print(f"Failed: {len(results['failed'])}")
            print(f"Skipped: {len(results['skipped'])}")
            print(f"Total processed: {results['total_processed']}")

            print(f"\nFinal API Usage:")
            for key, usage in results['api_usage']['key_usage'].items():
                print(f"  {key}: {usage} requests")

        except ValueError:
            print("Invalid CV IDs format")

    elif choice == '3':
        pending_cvs = [cv[0] for cv in available_cvs if cv[2] == 'Pending']
        if not pending_cvs:
            print("No pending CVs found")
            return

        print(f"\nProcessing {len(pending_cvs)} pending CVs with automatic API rotation...")
        results = parser.process_multiple_cvs(pending_cvs)

        print(f"\nBatch Processing Summary:")
        print(f"Successful: {len(results['successful'])}")
        print(f"Failed: {len(results['failed'])}")
        print(f"Skipped: {len(results['skipped'])}")
        print(f"Total processed: {results['total_processed']}")

        print(f"\nFinal API Usage:")
        for key, usage in results['api_usage']['key_usage'].items():
            print(f"  {key}: {usage} requests")

    elif choice == '4':
        cv_id = input("Enter CV ID to re-process: ").strip()
        try:
            cv_id = int(cv_id)

            # Delete existing parsed data
            conn = sqlite3.connect(parser.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT id FROM parsed_cvs_enhanced WHERE metadata_id = ?', (cv_id,))
            parsed_result = cursor.fetchone()

            if parsed_result:
                parsed_cv_id = parsed_result[0]
                cursor.execute('DELETE FROM cv_certifications_enhanced WHERE parsed_cv_id = ?', (parsed_cv_id,))
                cursor.execute('DELETE FROM parsed_cvs_enhanced WHERE id = ?', (parsed_cv_id,))
                conn.commit()
                print(f"Cleared existing data for CV {cv_id}")

            conn.close()

            print(f"\nRe-processing CV {cv_id}...")
            result = parser.process_single_cv(cv_id)

            print("\nRe-processing Result:")
            print(json.dumps(result, indent=2, ensure_ascii=False))

        except ValueError:
            print("Invalid CV ID")

    elif choice == '5':
        stats = parser.get_usage_stats()
        print(f"\nAPI Usage Statistics:")
        print(f"  Total keys: {stats['total_keys']}")
        print(f"  Working keys: {stats['working_keys']}")
        print(f"  Failed keys: {stats['failed_keys']}")
        print(f"  Current key: {stats['current_key']}")
        print(f"\nIndividual Key Usage:")
        for key, usage in stats['key_usage'].items():
            status = "Working" if int(key.split('_')[1]) - 1 in parser.working_keys else "Exhausted"
            print(f"  {key}: {usage} requests ({status})")

    elif choice == '6':
        # Select and save 10 CVs for next run
        print("\nSelect 10 CVs to save for next run:")
        selected_cvs = parser.select_cvs_interactive(available_cvs)

        if selected_cvs:
            # Limit to 10 if more selected
            selected_cvs = selected_cvs[:10]
            print(f"\nSelected {len(selected_cvs)} CVs:")
            for cv_id in selected_cvs:
                cv_info = next((cv for cv in available_cvs if cv[0] == cv_id), None)
                if cv_info:
                    print(f"  {cv_id}: {cv_info[1][:50]}... - {cv_info[2]}")

            if parser.save_processing_queue(selected_cvs):
                print(f"\nSaved {len(selected_cvs)} CVs to queue for next run")

                # Ask if user wants to process now
                process_now = input("Process these CVs now? (y/n): ").strip().lower()
                if process_now == 'y':
                    results = parser.process_multiple_cvs(selected_cvs)

                    # Remove processed CVs from queue
                    processed_ids = [r['cv_id'] for r in results['successful']]
                    if processed_ids:
                        parser.remove_processed_from_queue(processed_ids)

                    print(f"\nProcessing Summary:")
                    print(f"Successful: {len(results['successful'])}")
                    print(f"Failed: {len(results['failed'])}")
                    print(f"Skipped: {len(results['skipped'])}")
        else:
            print("No CVs selected")

    elif choice == '7':
        # Continue from saved queue
        saved_queue = parser.load_processing_queue()

        if not saved_queue:
            print("No saved queue found")
            return

        print(f"\nFound {len(saved_queue)} CVs in saved queue:")
        queue_cvs = []
        for cv_id in saved_queue:
            cv_info = next((cv for cv in available_cvs if cv[0] == cv_id), None)
            if cv_info:
                queue_cvs.append(cv_info)
                print(f"  {cv_id}: {cv_info[1][:50]}... - {cv_info[2]}")

        process_queue = input("\nProcess all CVs from queue? (y/n): ").strip().lower()
        if process_queue == 'y':
            results = parser.process_multiple_cvs(saved_queue)

            # Remove processed CVs from queue
            processed_ids = [r['cv_id'] for r in results['successful']]
            if processed_ids:
                parser.remove_processed_from_queue(processed_ids)

            print(f"\nQueue Processing Summary:")
            print(f"Successful: {len(results['successful'])}")
            print(f"Failed: {len(results['failed'])}")
            print(f"Skipped: {len(results['skipped'])}")

            remaining_queue = parser.load_processing_queue()
            if remaining_queue:
                print(f"Remaining in queue: {len(remaining_queue)} CVs")
            else:
                print("Queue completed!")

    elif choice == '8':
        # Interactive CV selection
        print("\nInteractive CV Selection:")
        selected_cvs = parser.select_cvs_interactive(available_cvs)

        if selected_cvs:
            print(f"\nSelected {len(selected_cvs)} CVs:")
            for cv_id in selected_cvs:
                cv_info = next((cv for cv in available_cvs if cv[0] == cv_id), None)
                if cv_info:
                    print(f"  {cv_id}: {cv_info[1][:50]}... - {cv_info[2]}")

            print("\nOptions:")
            print("1. Process now")
            print("2. Save for later")
            print("3. Process now and save remaining")

            sub_choice = input("Choose option (1-3): ").strip()

            if sub_choice == '1':
                results = parser.process_multiple_cvs(selected_cvs)
                print(f"Processing Summary: {len(results['successful'])} successful, {len(results['failed'])} failed")

            elif sub_choice == '2':
                parser.save_processing_queue(selected_cvs)

            elif sub_choice == '3':
                # Process some, save rest
                batch_size = int(input("How many to process now: ").strip())
                process_now = selected_cvs[:batch_size]
                save_later = selected_cvs[batch_size:]

                if process_now:
                    results = parser.process_multiple_cvs(process_now)
                    print(f"Processed: {len(results['successful'])} successful")

                if save_later:
                    parser.save_processing_queue(save_later)
                    print(f"Saved {len(save_later)} CVs for later")
        else:
            print("No CVs selected")

    else:
        print("Invalid choice")


if __name__ == "__main__":
    test_multi_api_parser()