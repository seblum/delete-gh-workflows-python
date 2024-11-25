import requests
import subprocess
from pathlib import Path
import click

class GitHubWorkflowManager:
    def __init__(self,github_api_url:str="https://api.github.com"):
        self.repo = self.__get_repo_info()
        self.token = self.__get_gh_token()
        self.github_api_url = github_api_url

    def __get_repo_info(self):
        try:
            git_path = Path(".git").resolve()
            with open(git_path / "config") as f:
                lines = f.readlines()
            for line in lines:
                if line.strip().startswith("url = "):
                    url = line.split("=", 1)[1].strip()
                    repo_path = url.split("github.com/")[1].replace(".git", "")
                    return repo_path
        except Exception as e:
            click.echo(f"Error retrieving repo info: {e}")
            return None

    def __get_gh_token(self):
        try:
            result = subprocess.run(['gh', 'auth', 'status'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                click.echo("You are not authenticated with GitHub CLI. Initiating login process...")
                subprocess.run(['gh', 'auth', 'login'], check=True)
            
            result = subprocess.run(['gh', 'auth', 'token'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                return result.stdout.decode('utf-8').strip()
            else:
                click.echo("Failed to retrieve GitHub token.")
                return None
        except FileNotFoundError:
            click.echo("GitHub CLI ('gh') is not installed. Please install it to authenticate.")
            return None

    def list_workflows(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.github_api_url}/repos/{self.repo}/actions/workflows"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            click.echo(f"Failed to fetch workflows: {response.text}")
            return []
        workflows = response.json()["workflows"]
        return [(workflow["id"], workflow["name"]) for workflow in workflows]

    def list_workflow_runs(self, workflow_id):
        headers = {"Authorization": f"Bearer {self.token}"}
        runs = []
        page = 1
        per_page = 100

        while True:
            url = f"{self.github_api_url}/repos/{self.repo}/actions/workflows/{workflow_id}/runs"
            response = requests.get(url, headers=headers, params={"per_page": per_page, "page": page})
            if response.status_code != 200:
                click.echo(f"Failed to fetch workflow runs: {response.text}")
                break

            data = response.json()["workflow_runs"]
            if not data:
                break

            runs.extend([(run["id"], run["name"], run["created_at"], run["status"]) for run in data])
            page += 1

        return runs

    def delete_workflow_run(self, run_id):
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.github_api_url}/repos/{self.repo}/actions/runs/{run_id}"
        response = requests.delete(url, headers=headers)
        return response.status_code == 204

    def delete_all_runs(self, workflow_id):
        runs = self.list_workflow_runs(workflow_id)
        if not runs:
            click.echo("No workflow runs found for this workflow.")
            return

        for run_id, _, _, _ in runs:
            if self.delete_workflow_run(run_id):
                click.echo(f"Deleted workflow run ID {run_id}.")
            else:
                click.echo(f"Failed to delete workflow run ID {run_id}.")

    def run_fzf_selection(self, items, prompt="Select an item"):
        input_items = "\n".join(items)
        process = subprocess.Popen(
            ['fzf', '--multi', '--bind', 'space:toggle', '--preview', 'echo {}', '--prompt', prompt],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output, _ = process.communicate(input=input_items.encode('utf-8'))
        selected_items = output.decode('utf-8').splitlines()
        click.echo(f"\n{len(selected_items)} items selected.")  # Feedback on how many were selected
        return selected_items
