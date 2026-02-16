# CV Analyzer - Intelligent Resume Parsing System

An advanced AI-powered CV/Resume parsing system that automatically extracts and structures information from PDF resumes using Google's Gemini AI with intelligent multi-API key rotation for high-volume processing.

## System Overview

The CV Analyzer is designed to process large volumes of resumes efficiently by leveraging multiple Google Gemini API keys with automatic rotation and quota management. The system intelligently extracts structured information from unstructured CV documents and stores the parsed data in a normalized SQLite database for easy querying and analysis.

### Core Architecture

The system operates in three main stages:

1. **PDF Text Extraction**: Extracts raw text content from PDF resumes using PyPDF2
2. **AI-Powered Parsing**: Processes the extracted text through Google Gemini 2.0 Flash to identify and categorize information
3. **Structured Storage**: Stores parsed data in a relational database with separate tables for CVs and certifications

## Key Features

### Multi-API Key Management

The system implements an intelligent API key rotation mechanism that ensures continuous processing even when individual API keys hit quota limits:

- **Automatic Key Testing**: Tests all provided API keys on initialization to identify working keys
- **Intelligent Rotation**: Automatically switches to the next available key when quota limits are detected
- **Usage Tracking**: Monitors API call counts per key for optimization insights
- **Error Detection**: Distinguishes between quota errors and other API failures for appropriate handling
- **Quota Error Detection**: Recognizes various quota-related error messages (429 errors, rate limits, daily limits)

### Robust Parsing Engine

The parsing engine is built to handle real-world CV variations and formatting inconsistencies:

- **JSON Extraction**: Intelligent extraction of structured data from Gemini's responses, handling both markdown-wrapped and plain JSON
- **Bracket Matching**: Advanced bracket counting algorithm to extract complete JSON objects and arrays from mixed-format responses
- **Trailing Comma Cleanup**: Automatic removal of invalid trailing commas in JSON structures
- **Retry Logic**: Built-in retry mechanisms for transient failures with configurable attempt limits

### Comprehensive Information Extraction

The system categorizes and extracts a wide range of CV information:

#### Personal Information
- Full name, email, phone number
- Location, LinkedIn profile, GitHub profile, personal website

#### Education Details
- Highest degree obtained
- Field of study
- University/institution name
- Graduation year

#### Technical Skills Categorization
The system categorizes technical skills into specialized domains:
- **Programming Languages**: Python, JavaScript, Java, C++, etc.
- **Web Frameworks**: React, Django, Flask, Angular, etc.
- **AI/ML Frameworks**: TensorFlow, PyTorch, scikit-learn, Keras
- **Data Science Tools**: NumPy, Pandas, Matplotlib, Seaborn
- **Databases**: PostgreSQL, MongoDB, MySQL, Redis
- **Cloud Platforms**: AWS, Azure, Google Cloud Platform
- **DevOps Tools**: Docker, Kubernetes, Jenkins, GitLab CI
- **Data Visualization**: Tableau, Power BI, D3.js
- **Big Data Tools**: Hadoop, Spark, Kafka
- **Mobile Development**: React Native, Flutter, Swift
- **Desktop Frameworks**: Electron, Qt
- **Version Control**: Git, SVN
- **Operating Systems**: Linux, Windows, macOS
- **Development Tools**: VS Code, IntelliJ, Jupyter

#### Professional Experience
- Latest job position and company
- Total years of professional experience
- Detailed project descriptions

#### Certifications
Extracted into a separate normalized table with:
- Certification name
- Issuing organization
- Issue date
- Credential ID

### Database Schema

The system uses SQLite with two primary tables:

**parsed_cvs_enhanced**: Main CV information table
- Metadata reference and raw text
- Personal contact information
- Education details
- All skill categories (15+ specialized fields)
- Professional experience summary
- Parsing metadata (status, timestamp, tokens used, API key used)

**cv_certifications_enhanced**: Normalized certifications table
- Foreign key reference to main CV record
- Certification details (name, issuer, date, credential ID)

### Interactive Processing Modes

The system provides multiple processing workflows:

1. **Single CV Processing**: Parse individual resumes with detailed feedback
2. **Batch Processing**: Process multiple CVs by ID list with comprehensive summary
3. **Pending CVs Processing**: Automatically process all CVs marked as "pending"
4. **Re-processing**: Clear and re-parse existing CV entries
5. **Queue Management**: Save CV selections for later processing and resume from saved queues
6. **Interactive Selection**: Visual CV selection with flexible processing options

### Error Handling & Recovery

The system implements comprehensive error handling:

- **Database Transactions**: All database operations use transactions with rollback on failure
- **Graceful Degradation**: Continues processing remaining CVs even if individual ones fail
- **Detailed Error Logging**: Captures parsing errors with timestamps and error messages
- **Partial Data Retention**: Saves successfully extracted fields even if complete parsing fails
- **Processing Status Tracking**: Maintains status flags (pending/completed/failed) for all CVs

## Technology Stack

### Core Libraries

**PDF Processing**
- **PyPDF2**: Handles PDF reading and text extraction with support for multi-page documents

**AI/ML**
- **google-generativeai**: Official Python SDK for Google's Gemini API
- Configured to use Gemini 2.0 Flash Experimental model for optimal cost/performance

**Database**
- **sqlite3**: Lightweight relational database for structured data storage
- **pandas**: Used for data manipulation and database query result handling

**HTTP & API**
- **requests**: HTTP library for potential remote CV fetching
- **io**: In-memory file operations for processing

**Data Processing**
- **json**: Parsing and serialization of structured CV data
- **re**: Regular expressions for text pattern matching and JSON cleanup
- **datetime**: Timestamp management for parsing records
- **time**: Rate limiting and retry delays

**System & Logging**
- **logging**: Comprehensive logging system for debugging and monitoring
- **os**: File system operations
- **typing**: Type hints for better code documentation and IDE support

### Configuration Management

The system uses flexible configuration:
- **Temperature**: Set to 0.1 for consistent, deterministic outputs
- **Max Output Tokens**: Configurable per request (default 1000 for structured data)
- **Retry Attempts**: Configurable based on number of available API keys

## Processing Flow

1. **Initialization**
   - Load and test all API keys
   - Initialize database connection
   - Set up logging

2. **CV Selection**
   - Query database for available CVs
   - Display CV metadata (ID, filename, current status)
   - Allow user to select processing mode

3. **Text Extraction**
   - Fetch PDF from storage
   - Extract text using PyPDF2
   - Store raw text in database

4. **AI Parsing**
   - Construct detailed prompt with CV text and expected JSON schema
   - Call Gemini API with current active key
   - Handle quota errors with automatic key rotation
   - Extract and validate JSON from response

5. **Data Storage**
   - Parse JSON response into structured fields
   - Insert/update main CV record
   - Insert certification records in separate table
   - Update processing status and metadata

6. **Batch Management**
   - Track successful, failed, and skipped CVs
   - Provide processing summaries
   - Update API usage statistics

## Database Operations

The system includes database management utilities:

- **Schema Updates**: Scripts to modify database structure without data loss
- **Backup Creation**: Automatic backup before schema changes
- **Data Migration**: Handles migration from old schema to new categorization system
- **Transaction Management**: Ensures data consistency with commit/rollback logic

## Output & Statistics

After processing, the system provides:

- **Success/Failure Counts**: Summary of processing results
- **API Usage Statistics**: Per-key request counts and current status
- **Detailed Error Reports**: Specific error messages for failed CVs
- **Processing Timestamps**: Track when each CV was last processed
- **Token Usage**: Monitor API token consumption per CV

## Use Cases

- **Recruitment Automation**: Quickly parse and categorize hundreds of applicant CVs
- **Candidate Database**: Build searchable databases of candidate skills and experience
- **Skills Gap Analysis**: Analyze technical skill distributions across applicants
- **Resume Screening**: Pre-filter candidates based on extracted qualifications
- **Talent Analytics**: Generate insights from structured CV data

## System Design Philosophy

The CV Analyzer prioritizes:
- **Reliability**: Multi-key rotation ensures continuous operation
- **Scalability**: Batch processing with queue management for large volumes
- **Accuracy**: AI-powered extraction with structured validation
- **Flexibility**: Configurable skill categories and parsing rules
- **Maintainability**: Clean separation of concerns and comprehensive logging

---

Built with modern AI and designed for production-scale resume processing.
