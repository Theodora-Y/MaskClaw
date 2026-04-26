from __future__ import annotations

import typer

from maskclaw_cli.output import echo_json, echo_kv, echo_table
from maskclaw_cli.services.task_service import TaskApiError, TaskService

app = typer.Typer(help="Manage AutoGLM tasks submitted via the bridge service.")

svc = TaskService()


@app.command("run")
def run(
    task: str = typer.Argument(..., help="Task description to execute on the phone."),
    max_steps: int = typer.Option(100, "--max-steps", help="Maximum number of steps."),
    lang: str = typer.Option("cn", "--lang", help="Language: cn or en."),
    api_key: str | None = typer.Option(None, "--api-key", help="ModelScope API key."),
    base_url: str = typer.Option(
        "https://api-inference.modelscope.cn/v1",
        "--base-url",
        help="Model API base URL.",
    ),
    model: str = typer.Option(
        "ZhipuAI/AutoGLM-Phone-9B",
        "--model",
        help="Model name.",
    ),
    device_id: str = typer.Option("", "--device-id", help="ADB device ID."),
    privacy_debug: bool = typer.Option(True, "--privacy-debug/--no-privacy-debug"),
    save_privacy_images: bool = typer.Option(True, "--save-privacy-images/--no-save-privacy-images"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        result = svc.run(
            task=task,
            max_steps=max_steps,
            lang=lang,
            api_key=api_key,
            base_url=base_url,
            model=model,
            device_id=device_id,
            privacy_debug=privacy_debug,
            save_privacy_images=save_privacy_images,
        )
        if json_output:
            echo_json(result)
            return
        echo_kv("Task submitted", {
            "task_id": result.get("task_id", ""),
            "status": result.get("status", ""),
            "stream_url": result.get("stream_url", ""),
            "message": result.get("message", ""),
        })
    except TaskApiError as exc:
        typer.secho(f"Error: {exc.message}", fg="red", err=True)
        raise typer.Exit(1)


@app.command("list")
def list_tasks(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        result = svc.list()
        if json_output:
            echo_json(result)
            return
        rows = [
            {
                "task_id": t.get("task_id", ""),
                "status": t.get("status", ""),
                "created_at": t.get("created_at", ""),
                "started_at": t.get("started_at") or "",
                "completed_at": t.get("completed_at") or "",
            }
            for t in result.get("tasks", [])
        ]
        echo_table(
            rows,
            [
                ("task_id", "Task ID"),
                ("status", "Status"),
                ("created_at", "Created"),
                ("started_at", "Started"),
                ("completed_at", "Completed"),
            ],
        )
    except TaskApiError as exc:
        typer.secho(f"Error: {exc.message}", fg="red", err=True)
        raise typer.Exit(1)


@app.command("status")
def status(
    task_id: str = typer.Argument(..., help="Task ID returned by 'task run'."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        result = svc.status(task_id)
        if json_output:
            echo_json(result)
            return
        echo_kv(f"Status: {result.get('status', '')}", {
            "task_id": result.get("task_id", ""),
            "status": result.get("status", ""),
            "created_at": result.get("created_at", ""),
            "started_at": result.get("started_at") or "",
            "completed_at": result.get("completed_at") or "",
            "error": result.get("error") or "",
        })
    except TaskApiError as exc:
        typer.secho(f"Error: {exc.message}", fg="red", err=True)
        raise typer.Exit(1)


@app.command("logs")
def logs(
    task_id: str = typer.Argument(..., help="Task ID returned by 'task run'."),
    limit: int = typer.Option(50, "--limit", help="Maximum number of log lines to fetch."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        events = svc.logs(task_id, limit=limit)
        if json_output:
            echo_json({"task_id": task_id, "events": events})
            return
        if not events:
            typer.echo("No log events received yet. The task may still be pending.")
            return
        for ev in events:
            event_type = ev.get("event", "message")
            data = ev.get("data", {})
            desc = data.get("action_metadata", {}).get("description", "")
            msg = data.get("message", "")
            text = desc or msg or str(data)
            color = "green" if event_type in ("task_completed",) else "red" if event_type in ("task_error",) else "cyan"
            prefix = f"[{event_type}]"
            typer.secho(f"{prefix} {text}", fg=color)
    except TaskApiError as exc:
        typer.secho(f"Error: {exc.message}", fg="red", err=True)
        raise typer.Exit(1)


@app.command("cancel")
def cancel(
    task_id: str = typer.Argument(..., help="Task ID returned by 'task run'."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        result = svc.cancel(task_id)
        if json_output:
            echo_json(result)
            return
        echo_kv("Cancel result", {
            "task_id": result.get("task_id", ""),
            "status": result.get("status", ""),
            "message": result.get("message", ""),
        })
    except TaskApiError as exc:
        typer.secho(f"Error: {exc.message}", fg="red", err=True)
        raise typer.Exit(1)
