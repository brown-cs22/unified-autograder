import json
import os

def read_tex_results():
    with open("/autograder/tex_results.json", 'r') as f_tex:
        s_tex = f_tex.read()
        json_tex = json.loads(s_tex)
        return {"tests": json_tex["tests"]}

def main():
    has_tex = os.path.isfile("/autograder/tex_results.json")

    tex_results = read_tex_results() if has_tex else {"tests": [{"name": "No .tex file found", "score": 0, "output": "You are expected to upload at least one .tex file!", "status": "failed"}]}

    results = {"tests": tex_results["tests"]}
    total_score = sum(t["score"] for t in results["tests"] if "score" in t)
    results["score"] = total_score

    with open("results/results.json", "w") as f_out:
        f_out.write(json.dumps(results))

if __name__ == "__main__":
    main()
