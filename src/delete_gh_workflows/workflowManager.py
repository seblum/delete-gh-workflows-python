import requests
import subprocess
from pathlib import Path
import click

class GitHubWorkflowManager:
    """
    A class to manage GitHub Actions workflows and runs via the GitHub API and CLI.

    Attributes:
        github_api_url (str): The base URL for the GitHub API. Defaults to "https://api.github.com".
        repo (str): The repository identifier in the format "owner/repo".
        token (str): The GitHub token used for API authentication.
    """

    def __init__(self, github_api_url: str = "https://api.github.com"):
        """
        Initializes the GitHubWorkflowManager with the API URL, repository information, and GitHub token.

        Args:
            github_api_url (str): The base URL for the GitHub API. Defaults to "https://api.github.com".
        """
        self.repo = self.__get_repo_info()
        self.token = self.__get_gh_token()
        self.github_api_url = github_api_url

    def __get_repo_info(self):
        """
        Retrieves the repository information from the local Git configuration.

        Returns:
            str: The repository path in the format "owner/repo".
            None: If the repository information cannot be retrieved.
        """
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
        """
        Retrieves the GitHub token using the GitHub CLI.

        Returns:
            str: The GitHub token if successfully retrieved.
            None: If the token cannot be retrieved or the CLI is not installed.
        """
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
        """
        Lists all workflows for the current repository.

        Returns:
            list: A list of tuples containing workflow ID and name.
                  Example: [(workflow_id, workflow_name), ...]
            list: An empty list if no workflows are found or if the request fails.
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.github_api_url}/repos/{self.repo}/actions/workflows"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            click.echo(f"Failed to fetch workflows: {response.text}")
            return []
        workflows = response.json()["workflows"]
        return [(workflow["id"], workflow["name"]) for workflow in workflows]

    def list_workflow_runs(self, workflow_id):
        """
        Lists all runs for a specific workflow.

        Args:
            workflow_id (int): The ID of the workflow.

        Returns:
            list: A list of tuples containing run ID, name, creation date, and status.
                  Example: [(run_id, run_name, created_at, status), ...]
        """
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
        """
        Deletes a specific workflow run.

        Args:
            run_id (int): The ID of the workflow run to delete.

        Returns:
            bool: True if the deletion was successful, False otherwise.
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.github_api_url}/repos/{self.repo}/actions/runs/{run_id}"
        response = requests.delete(url, headers=headers)
        return response.status_code == 204

    def delete_all_runs(self, workflow_id):
        """
        Deletes all runs for a specific workflow.

        Args:
            workflow_id (int): The ID of the workflow for which to delete all runs.
        """
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
        """
        Displays an interactive `fzf` selection menu for the provided items.

        Args:
            items (list): The list of items to display in the menu.
            prompt (str): The prompt message to display. Defaults to "Select an item".

        Returns:
            list: A list of selected items.
        """
        input_items = "\n".join(items)
        process = subprocess.Popen(
            ['fzf', '--multi', '--bind', 'space:toggle', '--preview', 'echo {}', '--prompt', prompt],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output, _ = process.communicate(input=input_items.encode('utf-8'))
        selected_items = output.decode('utf-8').splitlines()
        click.echo(f"\n{len(selected_items)} items selected.")  # Feedback on how many were selected
        return selected_items
