"""
Copy this file to local_settings.py and fill in your values.

    cp local_settings.example.py local_settings.py

Never commit local_settings.py if it contains real passwords.
"""

LOGIN_URL = "http://localhost:5000/login"
EMAIL = "your-email@example.com"
PASSWORD = "your-password"

# Add_candidate.py — example candidate fields
CANDIDATE_FIRST_NAME = "Test"
CANDIDATE_LAST_NAME = "Candidate"
CANDIDATE_EMAIL = "test.candidate@example.com"
CANDIDATE_PHONE = "4155550199"
CANDIDATE_LOCATION = "San Francisco, CA"
CANDIDATE_EXPERIENCE_COMPANY = "Acme Corp"
CANDIDATE_EXPERIENCE_TITLE = "Engineer"
CANDIDATE_EDUCATION_SCHOOL = "State University"
CANDIDATE_EDUCATION_DEGREE = "B.S. Computer Science"

# Optional — bulk_add_candidates.py
# BULK_CANDIDATE_COUNT = 100
# BULK_CONTINUE_ON_ERROR = False
# BULK_PAUSE_AFTER_SAVE = 3.0
