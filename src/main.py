import click
import os
import requests
import subprocess
from pathlib import Path

GITHUB_API_URL = "https://api.github.com"

# Function to get the current repository name from the .git directory
def get_repo_info():
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

def get_gh_token():
    """Use GitHub CLI to retrieve authentication token (if available)."""
    try:
        result = subprocess.run(['gh', 'auth', 'token'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            return result.stdout.decode('utf-8').strip()
        else:
            click.echo("You need to be logged in with GitHub CLI ('gh'). Run 'gh auth login'.")
            return None
    except FileNotFoundError:
        click.echo("GitHub CLI ('gh') is not installed. Please install it to authenticate.")
        return None

def list_workflows(repo, token):
    """List all workflows in the repository."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        click.echo(f"Failed to fetch workflows: {response.text}")
        return []
    workflows = response.json()["workflows"]
    return [(workflow["id"], workflow["name"]) for workflow in workflows]

def list_workflow_runs(repo, workflow_id, token):
    """List GitHub Actions workflow runs for a specific workflow with pagination."""
    headers = {"Authorization": f"Bearer {token}"}
    runs = []
    page = 1
    per_page = 100  # maximum allowed per page

    while True:
        url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_id}/runs"
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

def delete_workflow_run(repo, run_id, token):
    """Delete a specific workflow run."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GITHUB_API_URL}/repos/{repo}/actions/runs/{run_id}"
    response = requests.delete(url, headers=headers)
    return response.status_code == 204

def delete_all_runs(repo, workflow_id, token):
    """Delete all workflow runs for a specific workflow."""
    runs = list_workflow_runs(repo, workflow_id, token)
    if not runs:
        click.echo("No workflow runs found for this workflow.")
        return

    for run_id, _, _, _ in runs:
        if delete_workflow_run(repo, run_id, token):
            click.echo(f"Deleted workflow run ID {run_id}.")
        else:
            click.echo(f"Failed to delete workflow run ID {run_id}.")

@click.command()
def manage_workflow_runs():
    """List and delete GitHub Action workflow runs for the current repository."""
    
    token = get_gh_token()
    if not token:
        click.echo("GitHub token is required. Please login using 'gh auth login' or provide a token.")
        return

    repo = get_repo_info()
    if not repo:
        click.echo("Could not determine repository. Ensure you're in a GitHub repo directory.")
        return

    click.echo(f"Fetching workflows for repository '{repo}'...")
    workflows = list_workflows(repo, token)
    if not workflows:
        click.echo("No workflows found.")
        return

    # Display list of workflows and let user select one
    click.echo("\nAvailable Workflows:")
    for i, (workflow_id, name) in enumerate(workflows, start=1):
        click.echo(f"{i}: {name} (ID: {workflow_id})")

    workflow_index = click.prompt(
        "\nEnter the number of the workflow to view its runs, or 'q' to quit",
        type=str
    )

    if workflow_index.lower() == 'q':
        click.echo("Exiting.")
        return

    try:
        workflow_index = int(workflow_index) - 1
        if workflow_index < 0 or workflow_index >= len(workflows):
            raise ValueError("Invalid selection.")
    except ValueError:
        click.echo("Invalid input. Please enter a valid number.")
        return

    selected_workflow_id, selected_workflow_name = workflows[workflow_index]
    click.echo(f"\nFetching runs for workflow '{selected_workflow_name}'...")

    # List all runs for the selected workflow
    runs = list_workflow_runs(repo, selected_workflow_id, token)
    if not runs:
        click.echo("No workflow runs found.")
        return

    # Sort runs by name
    runs.sort(key=lambda x: x[1].lower())

    # Adjusted column widths for wider table
    header_format = "{:<4} {:<35} {:<30} {:<15} {:<15}"
    click.echo(header_format.format("No.", "Name", "Created At", "Status", "ID"))
    click.echo("=" * 110)

    # Wider columns for better readability
    row_format = "{:<4} {:<35} {:<30} {:<15} {:<15}"
    for i, (run_id, name, created_at, status) in enumerate(runs, start=1):
        click.echo(row_format.format(i, name[:34], created_at, status, run_id))

    delete_choice = click.prompt(
        "\nDo you want to delete all runs for this workflow? (y/n) or delete specific runs (comma-separated)",
        type=str
    )

    if delete_choice.lower() == 'y':
        click.echo(f"\nDeleting all runs for workflow '{selected_workflow_name}'...")
        delete_all_runs(repo, selected_workflow_id, token)
    elif delete_choice.lower() == 'n':
        click.echo("Exiting without deleting any workflow runs.")
        return
    else:
        try:
            indices_to_delete = [int(i.strip()) for i in delete_choice.split(",")]
        except ValueError:
            click.echo("Invalid input. Please enter valid numbers.")
            return

        for i in indices_to_delete:
            if 1 <= i <= len(runs):
                run_id = runs[i - 1][0]
                if delete_workflow_run(repo, run_id, token):
                    click.echo(f"Deleted workflow run ID {run_id}.")
                else:
                    click.echo(f"Failed to delete workflow run ID {run_id}.")
            else:
                click.echo(f"Invalid selection: {i}. Skipping.")

if __name__ == "__main__":
    manage_workflow_runs()
