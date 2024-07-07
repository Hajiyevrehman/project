from github import Github
import requests
from concurrent.futures import ThreadPoolExecutor
from github import GithubException
import openai

def get_words_in_order_from_all_files(access_token, username):
    g = Github(access_token, timeout= 3000)
    user = g.get_user(username)
    repos = user.get_repos()

    results = []

    for repo in repos:
        repo_result = {"repo_name": repo.name, "files": {}}
        try:
            contents = repo.get_contents("")
            for content_file in contents:
                if content_file.type == "file":
                    lines = content_file.decoded_content.decode("utf-8").splitlines()
                    repo_result["files"][content_file.name] = lines
            results.append(repo_result)
        except GithubException as e:
            if e.status == 404:
                print(f"Repository '{repo.name}' is empty.")
            else:
                print(f"Error occurred while processing '{repo.name}': {e}")

    return results

def analyze_code_category(gpt3_api_key, code_data, prompt_addition):
    openai.api_key = gpt3_api_key

    def analyze_repo(repo_data):
        repo_name = repo_data["repo_name"]
        code_input = f"I am analyzing code from the following repository: {repo_name}\n"

        for file_name, lines in repo_data["files"].items():
            code_input += f"  File: {file_name}\n"
            for i, line in enumerate(lines, start=1):
                code_input += f"    Line {i}: {line}\n"
        code_input += f"\n{prompt_addition}"

        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=code_input,
            max_tokens=200,
            n=1,
            stop=None,
            temperature=0.5,
        )

        analysis = response.choices[0].text.strip()
        return (repo_name, analysis)

    with ThreadPoolExecutor() as executor:
        repo_analyses = list(executor.map(analyze_repo, code_data))

    return repo_analyses

def aggregate_insights(repo_analyses_list):
    aggregated_insights = {}

    for category_analyses in repo_analyses_list:
        for repo_name, analysis in category_analyses:
            if repo_name not in aggregated_insights:
                aggregated_insights[repo_name] = []
            aggregated_insights[repo_name].append(analysis)

    return aggregated_insights

def print_aggregated_insights(aggregated_insights):
    for repo_name, insights in aggregated_insights.items():
        print(f"Repository: {repo_name}")
        for insight in insights:
            print(f"{insight}\n")
        print("\n")

def get_summary_skills(gpt3_api_key, aggregated_insights):
    openai.api_key = gpt3_api_key
    prompt = "Based on the aggregated insights from all repositories, provide a final summary of the applicant's skills:\n\nMake ad readable as possible and as deatailed as possible"

    for repo_name, insights in aggregated_insights.items():
        prompt += f"Repository: {repo_name}\n"
        for insight in insights:
            prompt += f"{insight}\n"
        prompt += "\n"

    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=prompt,
        max_tokens=200,
        n=1,
        stop=None,
        temperature=0.5,
    )

    summary_skills = response.choices[0].text.strip()
    return summary_skills

def analyze_github_user(github_access_token, github_username, openai_api_key):
    code_data = get_words_in_order_from_all_files(github_access_token, github_username)
    result = {}

    if code_data:
        categories = [
            "Analyze the code and provide insights on the following:\n1. Skills & Accomplishments\n2. Facts",
            "Analyze the code and provide insights on the following:\n1. Libraries & Algorithms\n2. Code Quality & Efficiency",
            "Analyze the code and provide insights on the following:\n1. Problem-solving, Communication & Collaboration\n2. Adaptability (languages, tools, frameworks)",
        ]
        repo_analyses_list = []

        for category in categories:
            repo_analyses_list.append(analyze_code_category(openai_api_key, code_data, category))

        aggregated_insights = aggregate_insights(repo_analyses_list)
        summary_skills = get_summary_skills(openai_api_key, aggregated_insights)

        result["aggregated_insights"] = aggregated_insights
        result["summary_skills"] = summary_skills
    else:
        result["error"] = f"No files were found in the repositories of '{github_username}'."

    return result

from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        raw_post_data = self.rfile.read(content_length)
        post_data = json.loads(raw_post_data.decode('utf-8'))

        github_access_token = post_data.get("github_access_token")
        github_username = post_data.get("github_username")
        openai_api_key = post_data.get("openai_api_key")

        analysis_result = analyze_github_user(github_access_token, github_username, openai_api_key)

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        if "error" in analysis_result:
            response = {"error": analysis_result["error"]}
        else:
            response = {
                "aggregated_insights": analysis_result["aggregated_insights"],
                "summary_skills": analysis_result["summary_skills"],
            }

        self.wfile.write(json.dumps(response).encode())
        return
