from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import settings
from src.core.message_service import build_message
from src.core.outreach_service import build_outreach
from src.core.status import compute_status
from src.db.message_repo import (
    get_local_gmail_ids,
    get_message_by_id,
    get_messages_for_outreach,
    save_message,
    update_message_classification,
)
from src.db.outreach_repo import (
    get_active_outreaches,
    get_outreach_by_id,
    get_unresolved_outreaches,
    list_outreaches,
    save_outreach,
    set_thread_id,
    update_outreach,
)
from src.db.session import get_session
from src.models.message import Direction

app = typer.Typer(help="Cold outreach tracker")
console = Console()


def _fmt(dt: datetime) -> str:
    local = dt.replace(tzinfo=timezone.utc).astimezone(tz=None)
    return local.strftime("%Y-%m-%d %H:%M %Z")


def _status_color(status: str) -> str:
    colors = {
        "interested": "green",
        "not_interested": "red",
        "needs_followup": "yellow",
        "follow_up_needed": "magenta",
        "awaiting_reply": "cyan",
        "unclassified": "dim",
        "archived": "dim",
        "draft": "dim",
    }
    color = colors.get(status, "white")
    return f"[{color}]{status}[/{color}]"


def _read_body(body_file: Optional[Path]) -> str:
    if body_file:
        return body_file.read_text()
    console.print("Paste email body. Enter [bold]EOF[/bold] on a new line to finish:")
    lines = []
    while True:
        line = input()
        if line == "EOF":
            break
        lines.append(line)
    return "\n".join(lines)


def _classify_message(session, message, outreach) -> None:
    from src.core.classifier import build_prompt
    from src.integrations.claude_client import ClaudeClient

    try:
        messages = get_messages_for_outreach(session, outreach.id)
        # Build thread up to and including this message
        thread = [m for m in messages if m.sent_at <= message.sent_at]
        if not thread or thread[-1].id != message.id:
            thread.append(message)

        claude = ClaudeClient()
        prompt = build_prompt(
            messages=thread,
            recipient_name=outreach.recipient_name,
            company=outreach.company,
        )
        result = claude.classify(prompt)
        update_message_classification(session, message.id, result)
        console.print(
            f"    [cyan]Classified:[/cyan] {result.classification.value} "
            f"({result.confidence:.0%}) — {result.reasoning}"
        )
    except Exception as e:
        console.print(f"    [yellow]Classification failed:[/yellow] {e}")


@app.command()
def add(
    to: str = typer.Option(..., "--to", help="Recipient email address"),
    subject: str = typer.Option(..., "--subject", help="Email subject"),
    name: Optional[str] = typer.Option(None, "--name", help="Recipient name"),
    company: Optional[str] = typer.Option(None, "--company", help="Recipient company"),
    role: Optional[str] = typer.Option(None, "--role", help="Role context (freeform)"),
    body_file: Optional[Path] = typer.Option(None, "--body-file", exists=True, help="Path to file containing email body"),
    sent_at: Optional[str] = typer.Option(None, "--sent-at", help="ISO datetime sent (defaults to now)"),
    follow_up_after_days: Optional[int] = typer.Option(None, "--follow-up-after-days", help="Override global follow-up threshold"),
) -> None:
    """Record a sent cold outreach email (creates outreach + first outbound message)."""
    body = _read_body(body_file)

    parsed_sent_at = datetime.fromisoformat(sent_at) if sent_at else datetime.now(timezone.utc)

    try:
        outreach_data = build_outreach(
            recipient_email=to,
            recipient_name=name,
            company=company,
            role=role,
            follow_up_after_days=follow_up_after_days,
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    with get_session() as session:
        outreach = save_outreach(session, outreach_data)
        msg_data = build_message(
            outreach_id=outreach.id,
            direction=Direction.outbound,
            subject=subject,
            body=body,
            sent_at=parsed_sent_at,
        )
        save_message(session, msg_data)
        console.print(
            f"[green]Added outreach #{outreach.id}[/green] to {outreach_data.recipient_email}\n"
            f"  Run [bold]outreach-track list[/bold] to sync and see updated status."
        )


@app.command(name="list")
def list_cmd(
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
    no_sync: bool = typer.Option(False, "--no-sync", help="Skip Gmail sync before listing"),
) -> None:
    """Sync Gmail then list outreach records with their derived status."""
    valid_statuses = {
        "awaiting_reply", "follow_up_needed", "interested",
        "not_interested", "needs_followup", "unclassified", "archived", "draft",
    }
    if status and status not in valid_statuses:
        console.print(f"[red]Invalid status.[/red] Choose from: {', '.join(sorted(valid_statuses))}")
        raise typer.Exit(1)

    if not no_sync:
        _run_sync()

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", justify="right", width=5)
    table.add_column("Recipient", min_width=22)
    table.add_column("Company", min_width=14)
    table.add_column("Status", min_width=18)
    table.add_column("Thread ID", min_width=12)
    table.add_column("Created", min_width=18)

    with get_session() as session:
        outreaches = list_outreaches(session)
        if not outreaches:
            console.print("No outreach records found.")
            return

        rows = []
        for o in outreaches:
            messages = get_messages_for_outreach(session, o.id)
            derived = compute_status(o, messages, settings.follow_up_after_days_default)
            if status and derived != status:
                continue
            rows.append((o, derived))

        if not rows:
            console.print(f"No outreaches with status '{status}'.")
            return

        for o, derived in rows:
            table.add_row(
                str(o.id),
                f"{o.recipient_name or '—'} <{o.recipient_email}>",
                o.company or "—",
                _status_color(derived),
                o.gmail_thread_id[:12] + "…" if o.gmail_thread_id else "[dim]unresolved[/dim]",
                _fmt(o.created_at) if o.created_at else "—",
            )

    console.print(table)


@app.command()
def show(outreach_id: int = typer.Argument(..., help="Outreach record ID")) -> None:
    """Show full detail for an outreach including the complete message thread."""
    with get_session() as session:
        outreach = get_outreach_by_id(session, outreach_id)
        if not outreach:
            console.print(f"[red]No outreach found with ID {outreach_id}.[/red]")
            raise typer.Exit(1)

        messages = get_messages_for_outreach(session, outreach_id)
        derived = compute_status(outreach, messages, settings.follow_up_after_days_default)

        console.print(Panel(
            f"[bold]To:[/bold] {outreach.recipient_name or '—'} <{outreach.recipient_email}>\n"
            f"[bold]Company:[/bold] {outreach.company or '—'}\n"
            f"[bold]Role:[/bold] {outreach.role or '—'}\n"
            f"[bold]Status:[/bold] {_status_color(derived)}\n"
            f"[bold]Gmail Thread:[/bold] {outreach.gmail_thread_id or '[dim]unresolved — run sync[/dim]'}\n"
            f"[bold]Follow-up after:[/bold] {outreach.follow_up_after_days or settings.follow_up_after_days_default} days\n"
            f"[bold]Created:[/bold] {_fmt(outreach.created_at)}",
            title=f"Outreach #{outreach.id}",
        ))

        if not messages:
            console.print("[dim]No messages in thread.[/dim]")
            return

        console.print(f"\n[bold]Thread ({len(messages)} message(s)):[/bold]\n")
        for msg in messages:
            if msg.direction == Direction.outbound:
                arrow = "[blue]→ You[/blue]"
            else:
                arrow = "[green]← Recipient[/green]"

            header = f"{arrow}  [dim]{_fmt(msg.sent_at)}[/dim]  Subject: {msg.subject}"
            console.print(header)
            console.print(f"   ID: {msg.id}")
            console.print(f"   {msg.body.strip()[:300]}{'…' if len(msg.body) > 300 else ''}")

            if msg.direction == Direction.inbound and msg.classification:
                console.print(
                    f"   [cyan]Classification:[/cyan] {msg.classification.value} "
                    f"({msg.classification_confidence:.0%} confidence) — {msg.classification_reasoning}"
                )
            console.print()


@app.command()
def edit(
    outreach_id: int = typer.Argument(..., help="Outreach record ID to edit"),
    to: Optional[str] = typer.Option(None, "--to", help="New recipient email"),
    name: Optional[str] = typer.Option(None, "--name", help="New recipient name"),
    company: Optional[str] = typer.Option(None, "--company", help="New company"),
    role: Optional[str] = typer.Option(None, "--role", help="New role context"),
    follow_up_after_days: Optional[int] = typer.Option(None, "--follow-up-after-days", help="New follow-up threshold (days)"),
    archived: Optional[bool] = typer.Option(None, "--archived", help="Set archived status (true/false)"),
) -> None:
    """Edit fields on an existing outreach record."""
    fields = {}
    if to:
        fields["recipient_email"] = to.strip().lower()
    if name:
        fields["recipient_name"] = name.strip()
    if company:
        fields["company"] = company.strip()
    if role:
        fields["role"] = role.strip()
    if follow_up_after_days is not None:
        fields["follow_up_after_days"] = follow_up_after_days
    if archived is not None:
        fields["archived"] = archived

    if not fields:
        console.print("[yellow]Nothing to update — pass at least one option.[/yellow]")
        raise typer.Exit(1)

    with get_session() as session:
        record = update_outreach(session, outreach_id, **fields)
        if not record:
            console.print(f"[red]No outreach found with ID {outreach_id}.[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Updated outreach #{outreach_id}.[/green]")
        for key, value in fields.items():
            console.print(f"  {key} = {value}")


def _run_sync() -> None:
    """Sync Gmail threads: resolve unresolved outreaches, then fetch new messages."""
    from src.core.message_service import build_message
    from src.core.thread_diff import compute_new_message_ids, detect_direction
    from src.integrations.gmail_client import GmailClient

    creds_path = Path(settings.google_credentials_file)
    if not creds_path.exists():
        console.print("[red]Not authenticated.[/red] Run [bold]outreach-track auth[/bold] first.")
        raise typer.Exit(1)

    try:
        gmail = GmailClient()
        auth_email = gmail.get_authenticated_email()
    except Exception as e:
        console.print(f"[red]Failed to connect to Gmail:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"Authenticated as: {auth_email}\n")

    with get_session() as session:
        # Step 1: Resolve thread IDs for outreaches that don't have one yet
        unresolved = get_unresolved_outreaches(session)
        if unresolved:
            console.print(f"Resolving {len(unresolved)} unresolved outreach(es)...")
            for outreach in unresolved:
                # Use the subject from the first outbound message
                messages = get_messages_for_outreach(session, outreach.id)
                first = next((m for m in messages if m.direction == Direction.outbound), None)
                if not first:
                    console.print(f"  [yellow]#{outreach.id}[/yellow] — no outbound message, skipping")
                    continue

                thread_id = gmail.search_sent_thread_id(
                    to_email=outreach.recipient_email,
                    subject=first.subject,
                )
                if not thread_id:
                    console.print(
                        f"  [yellow]#{outreach.id}[/yellow] — could not find Gmail thread "
                        f"(to={outreach.recipient_email}, subject={first.subject!r}). Will retry on next sync."
                    )
                    continue

                set_thread_id(session, outreach.id, thread_id)
                console.print(f"  [green]#{outreach.id}[/green] — thread resolved: {thread_id}")

        # Step 2: Sync messages for all active (resolved, non-archived) outreaches
        active = get_active_outreaches(session)
        if not active:
            console.print("No active outreaches to sync.")
            return

        console.print(f"\nSyncing {len(active)} active outreach(es)...")
        total_new = 0

        for outreach in active:
            console.print(
                f"  #{outreach.id} — {outreach.recipient_email} "
                f"(thread: {outreach.gmail_thread_id})"
            )
            thread_message_ids = gmail.get_thread_message_ids(outreach.gmail_thread_id)
            local_ids = get_local_gmail_ids(session, outreach.id)
            new_ids = compute_new_message_ids(thread_message_ids, local_ids)

            if not new_ids:
                console.print("    No new messages.")
                continue

            console.print(f"    {len(new_ids)} new message(s) found")

            for message_id in new_ids:
                raw = gmail.get_message(message_id)
                from_email = gmail.get_from_email(raw)
                direction_str = detect_direction(from_email or "", auth_email)
                direction = Direction(direction_str)
                subject = gmail.get_subject(raw)
                body = gmail.decode_body(raw)
                sent_at = gmail.get_sent_at(raw)

                msg_data = build_message(
                    outreach_id=outreach.id,
                    direction=direction,
                    subject=subject,
                    body=body,
                    sent_at=sent_at,
                    gmail_message_id=message_id,
                )
                message = save_message(session, msg_data)
                total_new += 1

                arrow = "→ outbound" if direction == Direction.outbound else "← inbound"
                console.print(f"    [{arrow}] {subject[:60]} ({_fmt(sent_at)})")

                if direction == Direction.inbound:
                    _classify_message(session, message, outreach)

        console.print(f"\n[bold]Done.[/bold] {total_new} new message(s) recorded.\n")


@app.command()
def sync() -> None:
    """Sync Gmail threads: resolve unresolved outreaches, then fetch new messages."""
    _run_sync()


@app.command()
def classify(message_id: int = typer.Argument(..., help="Message ID to classify (inbound only)")) -> None:
    """Re-run Claude classification on an existing inbound message."""
    with get_session() as session:
        message = get_message_by_id(session, message_id)
        if not message:
            console.print(f"[red]No message found with ID {message_id}.[/red]")
            raise typer.Exit(1)

        if message.direction == Direction.outbound:
            console.print("[red]Cannot classify an outbound message.[/red]")
            raise typer.Exit(1)

        outreach = get_outreach_by_id(session, message.outreach_id)
        if not outreach:
            console.print(f"[red]Outreach for message #{message_id} not found.[/red]")
            raise typer.Exit(1)

        _classify_message(session, message, outreach)


@app.command(name="help")
def help_cmd() -> None:
    """List all available commands with descriptions."""
    commands = [
        ("add",      "Record a sent cold outreach email (creates outreach + first message)"),
        ("list",     "Sync Gmail then list outreach records (use --no-sync to skip sync)"),
        ("show",     "Show full thread detail for a single outreach"),
        ("edit",     "Edit fields on an existing outreach record"),
        ("sync",     "Resolve Gmail threads and fetch new messages"),
        ("classify", "Re-run Claude classification on an existing inbound message"),
        ("auth",     "Authenticate with Gmail via OAuth (one-time setup)"),
        ("help",     "List all available commands with descriptions"),
    ]

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Command", style="cyan", min_width=12)
    table.add_column("Description")

    for cmd_name, description in commands:
        table.add_row(cmd_name, description)

    console.print("\n[bold]outreach-track[/bold] — Cold Outreach Tracker\n")
    console.print(table)
    console.print("\nRun [cyan]outreach-track <command> --help[/cyan] for detailed options.\n")


@app.command()
def auth() -> None:
    """Authenticate with Gmail via OAuth (one-time setup)."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    secret_path = Path(settings.google_client_secret_file)
    if not secret_path.exists():
        console.print(
            f"[red]Client secret file not found:[/red] {secret_path}\n"
            "Download it from GCP Console → APIs & Services → Credentials → OAuth 2.0 Client IDs."
        )
        raise typer.Exit(1)

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path = Path(settings.google_credentials_file)
    token_path.write_text(creds.to_json())
    console.print(f"[green]Authenticated.[/green] Token saved to {token_path}")
