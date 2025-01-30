import json

secrets = {}
config_file = {}
with open("/autograder/source/upload_secrets.json", "r") as f:
    secrets = json.load(f)
with open("/autograder/source/config.json", "r") as f:
    config_file = json.load(f)
course_id = secrets["course_id"]
assignment_id = secrets["assignment_id"]
username = secrets["username"]
password = secrets["password"]
question_ids = secrets["question_ids"]
upload_enabled = config_file["upload_enabled"]
tex_optional = config_file["tex_optional"]
lean_optional = config_file["lean_optional"]
