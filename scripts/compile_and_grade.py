import sys
import os
import json
import time
import shlex
import requests
import config
from bs4 import BeautifulSoup
from requests_toolbelt.multipart.encoder import MultipartEncoder
from pypdf import PdfReader

### File upload parameters
LOGIN_ENDPOINT = "https://www.gradescope.com/login"
COURSE_ENDPOINT = f'https://www.gradescope.com/courses/{config.course_id}'
SUBMISSIONS_ENDPOINT = f'https://www.gradescope.com/courses/{config.course_id}/assignments/{config.assignment_id}/submissions'
SUBMISSION_METADATA = "/autograder/submission_metadata.json"
###
SUBMISSION = "/autograder/submission/"
SOURCE = "/autograder/source/"
RESULT = "/autograder/results/results.json"
OUTPUT = "/autograder/results/output.txt"
LOG_ANALYSIS_OUTPUT = "/autograder/results/log_analysis_output.txt"

def write_result(output_header, output_text, output_score=1, output_max_score=1, dropdown_results=[]):
    result = {}
    result["tests"] = [{"name": output_header, "output": output_text, "score": output_score, "max_score": output_max_score, "visibility": "visible"}] + dropdown_results
    with open(RESULT, "w") as f:
        json.dump(result, f)

# Add a test without a score to the autograder output
def add_test(name, output, passed):
    result = {}
    with open(RESULT, "r") as f:
        result = json.load(f)
    if "tests" in result:
        result["tests"] = result["tests"] + [{"name": name, "output": output, "status": "passed" if passed else "failed", "visibility": "visible"}]
    else:
        result["tests"] = [{"name": name, "output": output, "status": "passed" if passed else "failed", "visibility": "visible"}]
    with open(RESULT, "w") as f:
        json.dump(result, f)

def get_filename():
    """
    Gets the filename of the `.tex` file to compile. 
    """
    _, _, files = next(os.walk(SUBMISSION, (None, None, [])))
    tex_files = []

    for file in files:
        if file.endswith(".tex"):
            tex_files.append(file)
        if file.endswith("main.tex"): # If we see `main.tex`, assume that is main file
            return file

    if len(tex_files) != 1:
        write_result("Error compiling", "Since there was no main.tex, we tried to infer the .tex file to compile, of which there were none or more than 1. \nThere should be exactly one .tex file in the submission (not within any folders). \nPlease try re-uploading your submission again. ", 0, 1)
        sys.exit(1)

    return tex_files[0]

def compile_file(filename):
    """
    Compiles the file and returns the output.
    """
    command = "latexmk -pdf -interaction=nonstopmode -halt-on-error -jobname=submission " + shlex.quote(SUBMISSION + filename) + " > " + OUTPUT
    os.system(command)

def grade():
    """
    Grades the submission.
    """
    with open(OUTPUT, "r", encoding="utf-8") as output_file:
        output = output_file.read()
    log = SUBMISSION + "submission.log"

    with open(log, "r", encoding="latin1") as log_file:
        log_file_text = log_file.read()

    log_test = {"name": "LaTeX Output Log", "output": log_file_text.split("! ", 1)[-1], "visibility": "hidden"}

    if "Fatal error occurred, no output PDF file produced!" in output:
        log_test["visibility"] = "visible"
        log_test["score"] = 0
        log_test["max_score"] = 1
        write_result("Error compiling", "There was a fatal error while compiling the submission and no PDF file was produced. \nPlease check your .tex file and try again. The log file is shown below. ", 0, 1, [log_test])
        sys.exit(1)

    os.system("/autograder/source/scripts/texloganalyser --last -w " + log + " > " + LOG_ANALYSIS_OUTPUT)

    with open(LOG_ANALYSIS_OUTPUT, "r") as log_analysis_file:
        log_analysis_output = log_analysis_file.read()

    warning_test = {"name": "Warnings", "output": log_analysis_output, "visibility": "visible"}
    output_tests = [warning_test]

    if "0 warnings" in log_analysis_output:
        warning_test["name"] = "No warnings!"
        with open(f"{SOURCE}templates/fun/frog.txt", "r", encoding="utf-8") as fun_frog_file:
            fun_frog_text = fun_frog_file.read()
        frog_test = {"name": "Frog cowboy!", "output": fun_frog_text, "visibility": "visible"}
        output_tests = output_tests + [frog_test]
    else:
        warning_test["max_score"] = 0
        warning_test["score"] = 0
        warning_test["name"] = "Warnings"

    write_result("Your .tex file compiled successfully!", "You'll see any warnings or bad boxes produced below, along with a generated score. \nPlease still verify that your submitted PDF is correct and correctly tagged.", 1, 1, output_tests)

session = requests.Session()
def upload():
    # Get the login endpoint first to retrieve CSRF token
    login_page_res = session.get(LOGIN_ENDPOINT)
    login_page_soup = BeautifulSoup(login_page_res.text, "html.parser")
    auth_token = login_page_soup.select_one(
            'form[action="/login"] input[name="authenticity_token"]'
        )["value"]
    login_data = {
        "utf8": "✓",
        "authenticity_token": auth_token,
        "session[email]": config.username,
        "session[password]": config.password,
        "session[remember_me]": 0,
        "commit": "Log In",
        "session[remember_me_sso]": 0,
    }
    # Login
    login_resp = session.post(LOGIN_ENDPOINT, login_data)

    if (
            # login_resp.history returns a list of redirects that occurred while handling a request
            len(login_resp.history) != 0
            and login_resp.history[0].status_code == requests.codes.found
        ):
        # update headers with csrf token
        # grab x-csrf-token
        soup = BeautifulSoup(login_resp.text, "html.parser")
        csrf_token = soup.select_one('meta[name="csrf-token"]')["content"]

        session.headers.update({"X-CSRF-Token": csrf_token})
    else:
        add_test("PDF Assignment Upload Error", "There was an error logging into Gradescope. Please try again or inform the course staff.", False)
        print(f'Gradescope response code was {login_resp.status_code}. Details below:')
        print(login_resp.json())
        sys.exit(1)

    # Get student ID from submission metadata - assumes this is not a group assignment
    with open(SUBMISSION_METADATA, "r") as metadata_file:
        submission_metadata = json.load(metadata_file)
    student_id = str(submission_metadata['users'][0]['id'])

    # Upload PDF
    with open(SUBMISSION + "submission.pdf", "rb") as pdf_file:
        file_upload_fields = [
                ("utf8", "✓"),
                ("authenticity_token", session.headers.get("X-CSRF-Token")),
                ("owner_id", student_id),
                (
                        "pdf_attachment",
                        (
                            "submission.pdf",
                            pdf_file,
                            "application/pdf",
                        ),
                    )
            ]
        multipart = MultipartEncoder(fields=file_upload_fields)

        headers = {
                "Content-Type": multipart.content_type,
            }
        upload_response = session.post(SUBMISSIONS_ENDPOINT, data=multipart, headers=headers)
    if upload_response.url == COURSE_ENDPOINT or upload_response.url.endswith("submissions"):
        add_test("PDF Assignment Upload Error", "There was an error uploading your compiled PDF file to Gradescope. Please try again or inform the course staff.", False)
        print(f'Gradescope response code was {upload_response.status_code}. Details below:')
        print(upload_response.json())
        sys.exit(1)
    add_test("PDF Upload Successful", "Your compiled PDF has successfully been uploaded to Gradescope. Please go into the PDF assignment and make sure it looks correct. NOTE: The assignment will show up as if it was submitted late, regardless if you submitted on time. Don't worry.", True)
    # Return the submission URL
    return upload_response.url[:upload_response.url.rfind('/')]

# Assumes PDF contains every question sequentially and that there cannot be multiple problems on one page
def get_pages():
    reader = PdfReader(SUBMISSION + "submission.pdf")
    num_pages = reader.get_num_pages()
    # Less pages than questions is bad
    if num_pages < len(config.question_ids):
        add_test("Page Assignment Failure", "We could not automatically assign pages to your uploaded PDF as there were less pages than assigned questions. Please make sure you're using the assigned template.", False)
        sys.exit(1)
    # 100 characters should be enough to find the header
    if reader.pages[0].extract_text().find("Problem 1", 0, 100) == -1:
        add_test("Page Assignment Failure", "We could not automatically assign pages to your uploaded PDF as Problem 1 was not found on the first page. Please make sure you're using the assigned template or contact the course staff.", False)
        sys.exit(1)
    next_problem = 2
    pages = []
    curr_pages = [0]
    for i in range(1, num_pages):
        if reader.pages[i].extract_text().find(f"Problem {next_problem}") != -1:
            pages.append(curr_pages)
            curr_pages = [i]
            next_problem += 1
        else:
            curr_pages.append(i)
    pages.append(curr_pages)
    # Not all questions were assigned
    if len(pages) < len(config.question_ids):
        add_test("Page Assignment Failure", f"We could not automatically assign pages to your uploaded PDF as we only found {len(pages)} problems in it. Please make sure you're using the assigned template or contact the course staff.", False)
        sys.exit(1)
    return pages

def set_pages(submission_url, pages):
    select_pages_url = submission_url + "/select_pages"
    update_pages_url = submission_url + "/update_pages"
    attachment_status_url = submission_url + "/pdf_attachment_status.json"
    select_pages_res = session.get(select_pages_url)
    select_pages_soup = BeautifulSoup(select_pages_res.text, "html.parser")
    # Get CSRF token
    csrf_token = select_pages_soup.select_one('meta[name="csrf-token"]')["content"]
    session.headers.update({"X-CSRF-Token": csrf_token})
    # Check PDF processing status - 1 is processing, 2 is complete
    status = 1
    while status == 1:
        status_response = session.get(attachment_status_url)
        if not status_response.ok:
            add_test("Page Assignment Failure", "Failed to check PDF attachment status on Gradescope. Please try again or contact the course staff.", False)
            print(f'Gradescope response code was {status_response.status_code}. Details below:')
            print(status_response.json())
            sys.exit(1)
        status = status_response.json()["status"]
        if status == 2:
            break
        time.sleep(5)
    if status != 2:
        add_test("Page Assignment Failure", "Unknown PDF processing status encountered. Please try again or contact the course staff.", False)
        print(f'Gradescope response code was {status_response.status_code}. Details below:')
        print(status_response.json())
        sys.exit(1)
    # Get processed page IDs in JSON
    select_pages_json = session.get(select_pages_url, headers={"Accept": "application/json"})
    if not select_pages_json.ok:
        add_test("Page Assignment Failure", "Failed to get pages in JSON format from Gradescope. Please try again or contact the course staff.", False)
        print(f'Gradescope response code was {select_pages_json.status_code}. Details below:')
        print(select_pages_json.json())
        sys.exit(1)
    pages_resp = select_pages_json.json()["pdf_attachment"]["pages"]
    # Convert pages list to dictionary and page numbers to Gradescope IDs
    pages_dict = {}
    for idx, question_pages in enumerate(pages):
        if config.question_ids[idx] != "-1":
            pages_dict.update({config.question_ids[idx]: list(map(lambda num: pages_resp[num]["id"], question_pages))})
    update_pages_form_data = {"pages_for_question": json.dumps(pages_dict), "pages": json.dumps(pages_resp)}
    # Call update pages endpoint
    update_pages_resp = session.post(update_pages_url, data=update_pages_form_data)
    if update_pages_resp.ok and update_pages_resp.json()["path"]:
        add_test("Page Assignment Successful", "Auto-assignment of PDF pages successful. Please go into the PDF assignment, check and re-assign pages if it has been done incorrectly.", True)
    else:
        add_test("Page Assignment Failure", "Invalid response received while trying to update page selection on Gradescope. Please try again or contact the course staff.", False)
        print(f'Gradescope response code was {update_pages_resp.status_code}. Details below:')
        print(update_pages_resp.json())
        sys.exit(1)

# Removes [draft] from the tex if someone forgot to do that
def remove_draft(filename):
    with open(SUBMISSION + filename, 'r') as file:
        data = file.read()
    data = data.replace('\\usepackage[draft]', '\\usepackage[]')
    with open(SUBMISSION + filename, 'w') as file:
        file.write(data)


def main():
    file_to_compile = get_filename()
    remove_draft(file_to_compile)
    compile_file(file_to_compile)
    grade()
    if config.upload_enabled:
        submission_url = upload()
        pages = get_pages()
        set_pages(submission_url, pages)

if __name__ == "__main__":
    main()
