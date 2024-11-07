import click
import os
import requests
import subprocess
from pathlib import Path

GITHUB_API_URL = "https://api.github.com"

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
    """Check if user is logged in with GitHub CLI and retrieve the token."""
    try:
        # Check if the user is authenticated with GitHub CLI
        result = subprocess.run(['gh', 'auth', 'status'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # If the user is not authenticated, prompt for login
        if result.returncode != 0:
            click.echo("You are not authenticated with GitHub CLI. Initiating login process...")
            subprocess.run(['gh', 'auth', 'login'], check=True)
        
        # Get the auth token (after login)
        result = subprocess.run(['gh', 'auth', 'token'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            return result.stdout.decode('utf-8').strip()
        else:
            click.echo("Failed to retrieve GitHub token.")
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

def run_fzf_selection(items, prompt="Select an item"):
    """Run fzf for interactive selection of items and show selected items clearly."""
    # Prepare input for fzf, each line is an item
    input_items = "\n".join(items)
    
    # Run fzf to select multiple items
    process = subprocess.Popen(
        ['fzf', '--multi', '--preview', 'echo {}', '--prompt', prompt],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    
    # Send the items to fzf via stdin and capture the selected lines
    output, _ = process.communicate(input=input_items.encode('utf-8'))
    
    # Return the selected items as a list
    return output.decode('utf-8').splitlines()

@click.command()
def manage_workflow_runs():
    """List and delete GitHub Action workflow runs for the current repository."""
    
    # Get authentication token from GitHub CLI
    token = get_gh_token()
    if not token:
        click.echo("GitHub token is required. Please login using 'gh auth login' or provide a token.")
        return

    # Get repository info
    repo = get_repo_info()
    if not repo:
        click.echo("Could not determine repository. Ensure you're in a GitHub repo directory.")
        return

    click.echo(f"\nFetching workflows for repository '{repo}'...")
    workflows = list_workflows(repo, token)
    if not workflows:
        click.echo("No workflows found.")
        return

    # Add Exit option to the list
    workflow_choices = [f"{workflow[1]} (ID: {workflow[0]})" for workflow in workflows] + ["Exit"]
    selected_workflow = run_fzf_selection(workflow_choices, "Select a workflow")

    if not selected_workflow:
        click.echo("No workflow selected. Exiting.")
        return

    if "Exit" in selected_workflow:
        click.echo("Exiting without selecting any workflow.")
        return

    # Extract selected workflow ID
    selected_workflow_name = selected_workflow[0]
    selected_workflow_id = next(w[0] for w in workflows if f"{w[1]} (ID: {w[0]})" == selected_workflow_name)

    click.echo(f"\nFetching runs for workflow '{selected_workflow_name}'...")

    # List all runs for the selected workflow
    runs = list_workflow_runs(repo, selected_workflow_id, token)
    if not runs:
        click.echo("No workflow runs found.")
        return

    # Sort runs by name
    runs.sort(key=lambda x: x[1].lower())

    # Display runs with fzf for selection
    run_choices = [f"{run[1]} - Created: {run[2]} - Status: {run[3]} (ID: {run[0]})" for run in runs] + ["Delete All Runs"]
    selected_runs = run_fzf_selection(run_choices, "Select workflow runs to delete (use arrows or space for multiple)")

    if not selected_runs:
        click.echo("No runs selected. Exiting.")
        return

    if "Delete All Runs" in selected_runs:
        click.echo(f"\nYou selected 'Delete All Runs' for workflow '{selected_workflow_name}'.")
        delete_choice = click.prompt(
            "Are you sure you want to delete all runs? This action cannot be undone. (y/n)",
            type=str
        )
        if delete_choice.lower() == 'y':
            delete_all_runs(repo, selected_workflow_id, token)
        else:
            click.echo("Exiting without deleting all runs.")
    else:
        # Convert the selected run strings back to IDs
        selected_run_ids = [int(run.split("(ID: ")[1][:-1]) for run in selected_runs]

        delete_choice = click.prompt(
            "\nDo you want to delete these runs? (y/n)",
            type=str
        )

        if delete_choice.lower() == 'y':
            for run_id in selected_run_ids:
                if delete_workflow_run(repo, run_id, token):
                    click.echo(f"Deleted workflow run ID {run_id}.")
                else:
                    click.echo(f"Failed to delete workflow run ID {run_id}.")
        else:
            click.echo("Exiting without deleting any workflow runs.")

if __name__ == "__main__":
    manage_workflow_runs()
