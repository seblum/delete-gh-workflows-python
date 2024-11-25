import click
from src.delete_gh_workflows.workflowManager import GitHubWorkflowManager

@click.command()
def manage_workflow_runs():
    """
    CLI tool for managing GitHub Actions workflow runs.

    Allows the user to:
    - List workflows in a repository.
    - View and manage workflow runs.
    - Delete specific runs or all runs for a workflow.
    """
    manager = GitHubWorkflowManager()
    
    # Ensure the user has a valid GitHub token
    if not manager.token:
        click.echo("GitHub token is required. Please login using 'gh auth login' or provide a token.")
        return

    # Ensure the script is run in a GitHub repository
    if not manager.repo:
        click.echo("Could not determine repository. Ensure you're in a GitHub repo directory.")
        return

    while True:
        # Fetch and display available workflows
        click.echo(f"\nFetching workflows for repository '{manager.repo}'...")
        workflows = manager.list_workflows()
        if not workflows:
            click.echo("No workflows found.")
            return

        # Present workflows in a selectable menu
        workflow_choices = [f"{workflow[1]} (ID: {workflow[0]})" for workflow in workflows] + ["Exit"]
        selected_workflow = manager.run_fzf_selection(workflow_choices, "Select a workflow")

        # Exit if the user chooses to
        if "Exit" in selected_workflow:
            click.echo("Exiting without selecting any workflow.")
            return

        # Retrieve the ID and name of the selected workflow
        selected_workflow_name = selected_workflow[0]
        selected_workflow_id = next(w[0] for w in workflows if f"{w[1]} (ID: {w[0]})" == selected_workflow_name)

        while True:
            # Fetch and display workflow runs for the selected workflow
            click.echo(f"\nFetching runs for workflow '{selected_workflow_name}'...")
            runs = manager.list_workflow_runs(selected_workflow_id)
            if not runs:
                click.echo("No workflow runs found.")
                break

            # Sort and display workflow runs
            runs.sort(key=lambda x: x[1].lower())
            run_choices = [
                f"{run[1]} - Created: {run[2]} - Status: {run[3]} (ID: {run[0]})" for run in runs
            ] + ["Delete All Runs", "Back"]
            selected_runs = manager.run_fzf_selection(run_choices, "Select workflow runs to delete")

            # Handle "Back" option to return to workflow selection
            if "Back" in selected_runs:
                click.echo("Returning to workflow selection.")
                break

            # Handle "Delete All Runs" option
            if "Delete All Runs" in selected_runs:
                delete_choice = click.prompt("Delete all runs? (y/n)", type=str)
                if delete_choice.lower() == 'y':
                    manager.delete_all_runs(selected_workflow_id)

            elif selected_runs:
                # Provide feedback on how many runs are selected
                selected_run_count = len(selected_runs)
                delete_choice = click.prompt(
                    f"\nYou have selected {selected_run_count} run(s). Do you want to delete these? (y/n)",
                    type=str
                )

                # Delete selected runs if confirmed
                if delete_choice.lower() == 'y':
                    for run_id in [int(run.split("(ID: ")[1][:-1]) for run in selected_runs]:
                        if manager.delete_workflow_run(run_id):
                            click.echo(f"Deleted workflow run ID {run_id}.")
                        else:
                            click.echo(f"Failed to delete workflow run ID {run_id}.")
            else:
                # Inform the user if no runs are selected
                click.echo("No runs selected. Exiting.")

if __name__ == "__main__":
    manage_workflow_runs()
