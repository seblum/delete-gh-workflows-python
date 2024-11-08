# src/main.py

import click
import os
import requests
import subprocess
from pathlib import Path

GITHUB_API_URL = "https://api.github.com"

class GitHubWorkflowManager:
    def __init__(self):
        self.repo = self.get_repo_info()
        self.token = self.get_gh_token()

    def get_repo_info(self):
        """Retrieve repository name from .git configuration."""
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

    def get_gh_token(self):
        """Check if user is logged in with GitHub CLI and retrieve the token."""
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
        """List all workflows in the repository."""
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{GITHUB_API_URL}/repos/{self.repo}/actions/workflows"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            click.echo(f"Failed to fetch workflows: {response.text}")
            return []
        workflows = response.json()["workflows"]
        return [(workflow["id"], workflow["name"]) for workflow in workflows]

    def list_workflow_runs(self, workflow_id):
        """List GitHub Actions workflow runs for a specific workflow with pagination."""
        headers = {"Authorization": f"Bearer {self.token}"}
        runs = []
        page = 1
        per_page = 100

        while True:
            url = f"{GITHUB_API_URL}/repos/{self.repo}/actions/workflows/{workflow_id}/runs"
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
        """Delete a specific workflow run."""
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{GITHUB_API_URL}/repos/{self.repo}/actions/runs/{run_id}"
        response = requests.delete(url, headers=headers)
        return response.status_code == 204

    def delete_all_runs(self, workflow_id):
        """Delete all workflow runs for a specific workflow."""
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
        """Run fzf for interactive selection of items and show selected items clearly."""
        input_items = "\n".join(items)
        process = subprocess.Popen(
            ['fzf', '--multi', '--preview', 'echo {}', '--prompt', prompt],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output, _ = process.communicate(input=input_items.encode('utf-8'))
        return output.decode('utf-8').splitlines()

@click.command()
def manage_workflow_runs():
    """List and delete GitHub Action workflow runs for the current repository."""
    manager = GitHubWorkflowManager()
    
    if not manager.token:
        click.echo("GitHub token is required. Please login using 'gh auth login' or provide a token.")
        return

    if not manager.repo:
        click.echo("Could not determine repository. Ensure you're in a GitHub repo directory.")
        return

    while True:
        click.echo(f"\nFetching workflows for repository '{manager.repo}'...")
        workflows = manager.list_workflows()
        if not workflows:
            click.echo("No workflows found.")
            return

        workflow_choices = [f"{workflow[1]} (ID: {workflow[0]})" for workflow in workflows] + ["Exit"]
        selected_workflow = manager.run_fzf_selection(workflow_choices, "Select a workflow")

        if "Exit" in selected_workflow:
            click.echo("Exiting without selecting any workflow.")
            return

        selected_workflow_name = selected_workflow[0]
        selected_workflow_id = next(w[0] for w in workflows if f"{w[1]} (ID: {w[0]})" == selected_workflow_name)

        while True:
            click.echo(f"\nFetching runs for workflow '{selected_workflow_name}'...")
            runs = manager.list_workflow_runs(selected_workflow_id)
            if not runs:
                click.echo("No workflow runs found.")
                break

            runs.sort(key=lambda x: x[1].lower())
            run_choices = [f"{run[1]} - Created: {run[2]} - Status: {run[3]} (ID: {run[0]})" for run in runs] + ["Delete All Runs", "Back"]
            selected_runs = manager.run_fzf_selection(run_choices, "Select workflow runs to delete")

            if "Back" in selected_runs:
                click.echo("Returning to workflow selection.")
                break

            if "Delete All Runs" in selected_runs:
                delete_choice = click.prompt("Delete all runs? (y/n)", type=str)
                if delete_choice.lower() == 'y':
                    manager.delete_all_runs(selected_workflow_id)
            else:
                selected_run_ids = [int(run.split("(ID: ")[1][:-1]) for run in selected_runs]
                delete_choice = click.prompt("Delete these runs? (y/n)", type=str)
                if delete_choice.lower() == 'y':
                    for run_id in selected_run_ids:
                        if manager.delete_workflow_run(run_id):
                            click.echo(f"Deleted workflow run ID {run_id}.")
                        else:
                            click.echo(f"Failed to delete workflow run ID {run_id}.")

if __name__ == "__main__":
    manage_workflow_runs()
