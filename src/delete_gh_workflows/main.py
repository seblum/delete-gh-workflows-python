import click
from src.delete_gh_workflows.workflowManager import GitHubWorkflowManager

@click.command()
def manage_workflow_runs():
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

                if selected_runs:
                    selected_run_count = len(selected_runs)
                    delete_choice = click.prompt(
                        f"\nYou have selected {selected_run_count} run(s). Do you want to delete these? (y/n)",
                        type=str
                    )

                    if delete_choice.lower() == 'y':
                        for run_id in selected_run_ids:
                            if manager.delete_workflow_run(run_id):
                                click.echo(f"Deleted workflow run ID {run_id}.")
                            else:
                                click.echo(f"Failed to delete workflow run ID {run_id}.")
                else:
                    click.echo("No runs selected. Exiting.")

            # else:
            #     selected_run_ids = [int(run.split("(ID: ")[1][:-1]) for run in selected_runs]
            #     delete_choice = click.prompt("Delete these runs? (y/n)", type=str)
            #     if delete_choice.lower() == 'y':
            #         for run_id in selected_run_ids:
            #             if manager.delete_workflow_run(run_id):
            #                 click.echo(f"Deleted workflow run ID {run_id}.")
            #             else:
            #                 click.echo(f"Failed to delete workflow run ID {run_id}.")

if __name__ == "__main__":
    manage_workflow_runs()
