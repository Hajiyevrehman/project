from github import Github
2import requests
3from concurrent.futures import ThreadPoolExecutor
4from github import GithubException
5import openai
6
7def get_words_in_order_from_all_files(access_token, username):
8    g = Github(access_token, timeout= 3000)
9    user = g.get_user(username)
10    repos = user.get_repos()
11
12    results = []
13
14    for repo in repos:
15        repo_result = {"repo_name": repo.name, "files": {}}
16        try:
17            contents = repo.get_contents("")
18            for content_file in contents:
19                if content_file.type == "file":
20                    lines = content_file.decoded_content.decode("utf-8").splitlines()
21                    repo_result["files"][content_file.name] = lines
22            results.append(repo_result)
23        except GithubException as e:
24            if e.status == 404:
25                print(f"Repository '{repo.name}' is empty.")
26            else:
27                print(f"Error occurred while processing '{repo.name}': {e}")
28
29    return results
30
31def analyze_code_category(gpt3_api_key, code_data, prompt_addition):
32    openai.api_key = gpt3_api_key
33
34    def analyze_repo(repo_data):
35        repo_name = repo_data["repo_name"]
36        code_input = f"I am analyzing code from the following repository: {repo_name}\n"
37
38        for file_name, lines in repo_data["files"].items():
39            code_input += f"  File: {file_name}\n"
40            for i, line in enumerate(lines, start=1):
41                code_input += f"    Line {i}: {line}\n"
42        code_input += f"\n{prompt_addition}"
43
44        response = openai.Completion.create(
45            engine="text-davinci-002",
46            prompt=code_input,
47            max_tokens=200,
48            n=1,
49            stop=None,
50            temperature=0.5,
51        )
52
53        analysis = response.choices[0].text.strip()
54        return (repo_name, analysis)
55
56    with ThreadPoolExecutor() as executor:
57        repo_analyses = list(executor.map(analyze_repo, code_data))
58
59    return repo_analyses
60
61
62def aggregate_insights(repo_analyses_list):
63    aggregated_insights = {}
64
65    for category_analyses in repo_analyses_list:
66        for repo_name, analysis in category_analyses:
67            if repo_name not in aggregated_insights:
68                aggregated_insights[repo_name] = []
69            aggregated_insights[repo_name].append(analysis)
70
71    return aggregated_insights
72
73def print_aggregated_insights(aggregated_insights):
74    for repo_name, insights in aggregated_insights.items():
75        print(f"Repository: {repo_name}")
76        for insight in insights:
77            print(f"{insight}\n")
78        print("\n")
79
80def get_summary_skills(gpt3_api_key, aggregated_insights):
81    openai.api_key = gpt3_api_key
82    prompt = "Based on the aggregated insights from all repositories, provide a final summary of the applicant's skills:\n\nMake ad readable as possible and as deatailed as possible"
83
84    for repo_name, insights in aggregated_insights.items():
85        prompt += f"Repository: {repo_name}\n"
86        for insight in insights:
87            prompt += f"{insight}\n"
88        prompt += "\n"
89
90    response = openai.Completion.create(
91        engine="text-davinci-002",
92        prompt=prompt,
93        max_tokens=200,
94        n=1,
95        stop=None,
96        temperature=0.5,
97    )
98
99    summary_skills = response.choices[0].text.strip()
100    return summary_skills
101
102def analyze_github_user(github_access_token, github_username, openai_api_key):
103    code_data = get_words_in_order_from_all_files(github_access_token, github_username)
104    result = {}
105
106    if code_data:
107        categories = [
108            "Analyze the code and provide insights on the following:\n1. Skills & Accomplishments\n2. Facts",
109            "Analyze the code and provide insights on the following:\n1. Libraries & Algorithms\n2. Code Quality & Efficiency",
110            "Analyze the code and provide insights on the following:\n1. Problem-solving, Communication & Collaboration\n2. Adaptability (languages, tools, frameworks)",
111        ]
112        repo_analyses_list = []
113
114        for category in categories:
115            repo_analyses_list.append(analyze_code_category(openai_api_key, code_data, category))
116
117        aggregated_insights = aggregate_insights(repo_analyses_list)
118        summary_skills = get_summary_skills(openai_api_key, aggregated_insights)
119
120        result["aggregated_insights"] = aggregated_insights
121        result["summary_skills"] = summary_skills
122    else:
123        result["error"] = f"No files were found in the repositories of '{github_username}'."
124
125    return result
126
127from http.server import BaseHTTPRequestHandler
128import json
129
130class handler(BaseHTTPRequestHandler):
131    def do_POST(self):
132        content_length = int(self.headers['Content-Length'])
133        raw_post_data = self.rfile.read(content_length)
134        post_data = json.loads(raw_post_data.decode('utf-8'))
135
136        github_access_token = post_data.get("github_access_token")
137        github_username = post_data.get("github_username")
138        openai_api_key = post_data.get("openai_api_key")
139
140        analysis_result = analyze_github_user(github_access_token, github_username, openai_api_key)
141
142        self.send_response(200)
143        self.send_header('Content-type', 'application/json')
144        self.end_headers()
145
146        if "error" in analysis_result:
147            response = {"error": analysis_result["error"]}
148        else:
149            response = {
150                "aggregated_insights": analysis_result["aggregated_insights"],
151                "summary_skills": analysis_result["summary_skills"],
152            }
153
154        self.wfile.write(json.dumps(response).encode())
155        return
