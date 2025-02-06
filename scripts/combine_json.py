import json
import os
import config

def read_tex_results():
    with open("/autograder/tex_results.json", 'r') as f_tex:
        json_tex = json.load(f_tex)
        return {"tests": json_tex["tests"]}

def read_lean_results():
    with open("/autograder/lean_results.json", 'r') as f_lean:
        json_lean = json.load(f_lean)
        # The lean result contains a "tests" field iff it was able to complete testing - otherwise
        # it just has a score of 0 and a description of the error that prevented testing.
        return { "tests": (json_lean["tests"] if "tests" in json_lean else json_lean) }


def main():
    has_lean, has_tex = os.path.isfile("/autograder/lean_results.json"), os.path.isfile("/autograder/tex_results.json")
    pdf_submitted = any(file.endswith(".pdf") for file in os.listdir("/autograder/submission/"))

    lean_results = read_lean_results() if has_lean else {"tests": [{"name": "No .lean file found", "score": 0, "output": "You are expected to upload exactly one .lean file!", "status": "failed"}]}
    tex_results = read_tex_results() if has_tex else {"tests": [{"name": "No .tex file found", "score": 0, "output": "You are expected to upload at least one .tex file!", "status": "failed"}]}

    # Remove warnings if optional
    if config.lean_optional and not has_lean:
        lean_results = {"tests": []}
    if config.tex_optional and not has_tex:
        tex_results = {"tests": []}
    # If TeX is optional, remove scores and replace with pass/fail. Assuming Lean is extra credit if optional.
    if config.tex_optional and has_tex:
        for idx in range(len(tex_results["tests"])):
            if "score" in tex_results["tests"][idx] and tex_results["tests"][idx]["max_score"] > 0:
                if tex_results["tests"][idx]["score"] >= tex_results["tests"][idx]["max_score"]:
                    tex_results["tests"][idx]["status"] = "passed"
                else:
                    tex_results["tests"][idx]["status"] = "failed"
                del(tex_results["tests"][idx]["score"])
                del(tex_results["tests"][idx]["max_score"])
    if pdf_submitted:
        tex_results["tests"] += [{"name": "PDF submitted!", "output": "You have submitted a PDF file to the wrong assignment. It will be ignored.", "status": "failed"}]

    results = {"tests": lean_results["tests"] + tex_results["tests"]}
    total_score = sum(t["score"] for t in results["tests"] if "score" in t)
    results["score"] = total_score

    with open("results/results.json", "w") as f_out:
        f_out.write(json.dumps(results))

if __name__ == "__main__":
    main()
