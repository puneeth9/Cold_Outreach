from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import settings
from src.core.outreach_service import build_outreach
from src.db.outreach_repo import list_outreach, save_outreach, update_outreach
from src.db.reply_repo import (
    get_awaiting_outreaches,
    get_outreach_by_id,
    get_replies_for_outreach,
    get_reply_by_id,
    mark_outreach_replied,
    save_reply,
    update_reply_classification,
)
from src.db.session import get_session

app = typer.Typer(help="Cold outreach tracker")
console = Console()


def _fmt(dt: datetime) -> str:
    """Format a UTC datetime as local time."""
    local = dt.replace(tzinfo=timezone.utc).astimezone(tz=None)
    return local.strftime("%Y-%m-%d %H:%M %Z")


@app.command()
def add(
    to: str = typer.Option(..., "--to", help="Recipient email address"),
    name: str = typer.Option(..., "--name", help="Recipient name"),
    subject: str = typer.Option(..., "--subject", help="Email subject"),
    company: Optional[str] = typer.Option(None, "--company", help="Recipient company"),
    role: Optional[str] = typer.Option(None, "--role", help="Role context (freeform)"),
    body_file: Optional[Path] = typer.Option(None, "--body-file", exists=True, help="Path to file containing email body"),
    sent_at: Optional[str] = typer.Option(None, "--sent-at", help="ISO datetime of when email was sent (defaults to now)"),
) -> None:
    """Record a sent cold outreach email."""
    if body_file:
        body = body_file.read_text()
    else:
        console.print("Paste email body. Enter a blank line then [bold]EOF[/bold] to finish:")
        lines = []
        while True:
            line = input()
            if line == "EOF":
                break
            lines.append(line)
        body = "\n".join(lines)

    parsed_sent_at = None
    if sent_at:
        parsed_sent_at = datetime.fromisoformat(sent_at)

    try:
        data = build_outreach(
            recipient_email=to,
            recipient_name=name,
            subject=subject,
            body=body,
            company=company,
            role_context=role,
            sent_at=parsed_sent_at,
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    with get_session() as session:
        record = save_outreach(session, data)
        console.print(f"[green]Added outreach #{record.id}[/green] to {data.recipient_email}")


@app.command(name="list")
def list_cmd(
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status: awaiting_reply | replied | archived"),
) -> None:
    """List recorded outreach emails."""
    valid_statuses = {"awaiting_reply", "replied", "archived"}
    if status and status not in valid_statuses:
        console.print(f"[red]Invalid status.[/red] Choose from: {', '.join(sorted(valid_statuses))}")
        raise typer.Exit(1)

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", justify="right", width=5)
    table.add_column("Recipient", min_width=20)
    table.add_column("Company", min_width=15)
    table.add_column("Subject", min_width=25)
    table.add_column("Status", min_width=15)
    table.add_column("Sent At", min_width=20)

    with get_session() as session:
        records = list_outreach(session, status_filter=status)
        if not records:
            console.print("No outreach records found.")
            return
        for r in records:
            table.add_row(
                str(r.id),
                f"{r.recipient_name} <{r.recipient_email}>",
                r.company or "—",
                r.subject,
                r.status.value,
                _fmt(r.sent_at) if r.sent_at else "—",
            )

    console.print(table)


@app.command()
def show(outreach_id: int = typer.Argument(..., help="Outreach record ID")) -> None:
    """Show full detail for a single outreach record and its replies."""
    with get_session() as session:
        record = get_outreach_by_id(session, outreach_id)
        if not record:
            console.print(f"[red]No outreach found with ID {outreach_id}.[/red]")
            raise typer.Exit(1)

        console.print(Panel(
            f"[bold]To:[/bold] {record.recipient_name} <{record.recipient_email}>\n"
            f"[bold]Company:[/bold] {record.company or '—'}\n"
            f"[bold]Role:[/bold] {record.role_context or '—'}\n"
            f"[bold]Subject:[/bold] {record.subject}\n"
            f"[bold]Status:[/bold] {record.status.value}\n"
            f"[bold]Sent:[/bold] {_fmt(record.sent_at)}\n\n"
            f"[bold]Body:[/bold]\n{record.body}",
            title=f"Outreach #{record.id}",
        ))

        replies = get_replies_for_outreach(session, outreach_id)
        if not replies:
            console.print("[dim]No replies recorded.[/dim]")
            return

        rtable = Table(show_header=True, header_style="bold", title="Replies")
        rtable.add_column("Reply ID", justify="right", width=8)
        rtable.add_column("Received", min_width=18)
        rtable.add_column("Classification", min_width=15)
        rtable.add_column("Confidence", justify="right", width=10)
        rtable.add_column("Reasoning", min_width=30)

        for r in replies:
            rtable.add_row(
                str(r.id),
                _fmt(r.received_at),
                r.classification.value,
                f"{r.classification_confidence:.0%}" if r.classification_confidence else "—",
                r.classification_reasoning or "—",
            )

        console.print(rtable)


@app.command()
def edit(
    outreach_id: int = typer.Argument(..., help="Outreach record ID to edit"),
    to: Optional[str] = typer.Option(None, "--to", help="New recipient email"),
    name: Optional[str] = typer.Option(None, "--name", help="New recipient name"),
    subject: Optional[str] = typer.Option(None, "--subject", help="New subject"),
    company: Optional[str] = typer.Option(None, "--company", help="New company"),
    role: Optional[str] = typer.Option(None, "--role", help="New role context"),
    status: Optional[str] = typer.Option(None, "--status", help="New status: awaiting_reply | replied | archived"),
    sent_at: Optional[str] = typer.Option(None, "--sent-at", help="New sent datetime (ISO format)"),
) -> None:
    """Edit fields on an existing outreach record."""
    from src.models.outreach import OutreachStatus

    valid_statuses = {"awaiting_reply", "replied", "archived"}
    if status and status not in valid_statuses:
        console.print(f"[red]Invalid status.[/red] Choose from: {', '.join(sorted(valid_statuses))}")
        raise typer.Exit(1)

    fields = {}
    if to:
        fields["recipient_email"] = to.strip().lower()
    if name:
        fields["recipient_name"] = name.strip()
    if subject:
        fields["subject"] = subject.strip()
    if company:
        fields["company"] = company.strip()
    if role:
        fields["role_context"] = role.strip()
    if status:
        fields["status"] = OutreachStatus(status)
    if sent_at:
        fields["sent_at"] = datetime.fromisoformat(sent_at)

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


def _classify_reply(session, reply, outreach) -> None:
    """Classify a reply using Claude and persist the result. Logs result to console."""
    from src.core.classifier import build_prompt
    from src.integrations.claude_client import ClaudeClient

    try:
        claude = ClaudeClient()
        prompt = build_prompt(
            outreach_subject=outreach.subject,
            outreach_body=outreach.body,
            reply_body=reply.body,
            recipient_name=outreach.recipient_name,
            company=outreach.company,
        )
        result = claude.classify(prompt)
        update_reply_classification(session, reply.id, result)
        console.print(
            f"    [cyan]Classified:[/cyan] {result.classification.value} "
            f"({result.confidence:.0%}) — {result.reasoning}"
        )
    except Exception as e:
        console.print(f"    [yellow]Classification failed:[/yellow] {e} (reply saved as unclassified)")


@app.command()
def sync() -> None:
    """Poll Gmail for replies on all awaiting_reply outreaches."""
    from src.core.matcher import find_matching_outreach
    from src.core.reply_service import build_reply
    from src.integrations.gmail_client import GmailClient

    creds_path = Path(settings.google_credentials_file)
    if not creds_path.exists():
        console.print(
            "[red]Not authenticated.[/red] Run [bold]outreach-track auth[/bold] first."
        )
        raise typer.Exit(1)

    try:
        gmail = GmailClient()
    except Exception as e:
        console.print(f"[red]Failed to connect to Gmail:[/red] {e}")
        raise typer.Exit(1)

    with get_session() as session:
        outreaches = get_awaiting_outreaches(session)
        if not outreaches:
            console.print("No outreaches awaiting reply.")
            return

        console.print(f"Checking {len(outreaches)} outreach(es) for replies...")
        found = 0
        skipped = 0


        for outreach in outreaches:
            console.print(
                f"  Checking #{outreach.id} — {outreach.recipient_email} "
                f"(sent {_fmt(outreach.sent_at)})"
            )
            message_ids = gmail.list_message_ids_from(
                sender_email=outreach.recipient_email,
                after=outreach.sent_at,
            )
            console.print(f"    Found {len(message_ids)} message(s) from this sender")

            for message_id in message_ids:
                message = gmail.get_message(message_id)
                from_email = gmail.get_from_email(message)
                received_at = gmail.get_received_at(message)
                console.print(f"    → from={from_email}  received={_fmt(received_at)}")

                if not from_email:
                    console.print("      [dim]Skipped: no from header[/dim]")
                    continue

                match = find_matching_outreach(from_email, [outreach])
                if not match:
                    console.print(
                        f"      [dim]Skipped: {from_email!r} did not match "
                        f"{outreach.recipient_email!r}[/dim]"
                    )
                    continue

                body = gmail.decode_body(message)
                received_at = gmail.get_received_at(message)

                try:
                    reply_data = build_reply(
                        gmail_message_id=message_id,
                        outreach_id=match.id,
                        received_at=received_at,
                        body=body,
                    )
                    reply = save_reply(session, reply_data)
                    mark_outreach_replied(session, match.id)
                    found += 1
                    console.print(
                        f"  [green]Reply found[/green] from {from_email} "
                        f"(outreach #{match.id})"
                    )
                    _classify_reply(session, reply, match)
                except Exception as e:
                    # Unique constraint hit = already recorded; skip silently
                    if "UNIQUE constraint failed" in str(e):
                        skipped += 1
                        session.rollback()
                    else:
                        raise

        console.print(
            f"\n[bold]Done.[/bold] {found} new reply(s) recorded, {skipped} already known."
        )


@app.command()
def classify(reply_id: int = typer.Argument(..., help="Reply ID to classify")) -> None:
    """Re-run Claude classification on an existing reply."""
    with get_session() as session:
        reply = get_reply_by_id(session, reply_id)
        if not reply:
            console.print(f"[red]No reply found with ID {reply_id}.[/red]")
            raise typer.Exit(1)

        outreach = get_outreach_by_id(session, reply.outreach_id)
        if not outreach:
            console.print(f"[red]Outreach record for reply #{reply_id} not found.[/red]")
            raise typer.Exit(1)

        _classify_reply(session, reply, outreach)


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
