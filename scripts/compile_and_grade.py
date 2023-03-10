import sys
import os
import json

SUBMISSION = "/autograder/submission/"
SOURCE = "/autograder/source/"
RESULT = "/autograder/results/results.json"
OUTPUT = "/autograder/results/output.txt"
LOG_ANALYSIS_OUTPUT = "/autograder/results/log_analysis_output.txt"
PREAMBLE = "This autograder is still in beta! It works by attempting to compile your .tex file and providing you with feedback if there are warnings and errors. The easiest way to submit to this autograder is to download the source .zip file from Overleaf and uploading that directly (Menu > Download > Source).\n\t\nPlease take these results with a grain of salt (it is still very buggy!). We hope the autograder will catch LaTeX errors before your final sumbission so you are able to amend any issues with your file. \n\t\nThe results here are solely for your information, they are not for a grade and we will not be looking at the output whatsoever. If you have any feedback, please don't hesitate to contact us. \n\t\n - CS22 TAs <3"

def write_result(output_header, output_text, output_score=1, output_max_score=1, dropdown_results=[]):
    result = {}
    result["output"] = f"{PREAMBLE}"
    result["tests"] = [{"name": output_header, "output": output_text, "score": output_score, "max_score": output_max_score, "visibility": "visible"}] + dropdown_results
    with open(RESULT, "w") as f:
        f.write(json.dumps(result))

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
        write_result("Error compiling", "Since there was no main.tex, we tried to infer the .tex file to compile, of which there were none or more than 1. \nThere should be exactly one .tex file in the submission (not within any folders). \nPlease try re-uploading your submission again. ", 0, 2)
        sys.exit(1)

    return tex_files[0]

def compile_file(filename):
    """
    Compiles the file and returns the output.
    """
    command = "pdflatex -shell-escape -interaction=nonstopmode -halt-on-error \"" + SUBMISSION + filename + "\" > " + OUTPUT
    os.system(command)

def grade(filename):
    """
    Grades the submission.
    """
    with open(OUTPUT, "r", encoding="utf-8") as output_file:
        output = output_file.read()
    log = SUBMISSION + filename.replace(".tex", ".log")

    with open(filename.replace(".tex", ".log"), "r", encoding="latin1") as log_file:
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
        with open(f"{SOURCE}templates/fun/tea.txt", "r", encoding="utf-8") as fun_tea_file:
            fun_tea_text = fun_tea_file.read()
        tea_test = {"name": "Tea!", "output": fun_tea_text, "visibility": "visible"}
        output_tests = output_tests + [tea_test]
    else:
        warning_test["max_score"] = 0
        warning_test["score"] = 0
        warning_test["name"] = "Warnings"

    write_result("Your .tex file compiled successfully!", "You'll see any warnings or bad boxes produced below, along with a generated score. \nPlease still verify that your submitted PDF is correct and correctly tagged.", 1, 1, output_tests)

def main():
    file_to_compile = get_filename()
    compile_file(file_to_compile)
    grade(file_to_compile)

if __name__ == "__main__":
    main()
