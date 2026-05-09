#!/usr/bin/env python3
"""
Morning Email Draft Routine
Scans the inbox for emails needing a reply and creates Gmail drafts via Claude.
"""

import os
import re
import base64
import email.mime.text
from datetime import datetime

import anthropic
from gmail_auth import get_gmail_service

# Senders that never need a personal reply
AUTOMATED_PATTERNS = [
    r'no.?reply', r'noreply', r'do.?not.?reply',
    r'notification[s]?@', r'mailer-daemon', r'postmaster',
    r'bounce[^@]*@', r'automated@', r'newsletter@',
    r'news@', r'updates@', r'alert[s]?@', r'support-noreply',
    r'hello@.*\.(io|com).*unsubscribe',
]


def is_automated(address: str) -> bool:
    low = address.lower()
    return any(re.search(p, low) for p in AUTOMATED_PATTERNS)


def get_header(headers: list, name: str) -> str:
    for h in headers:
        if h['name'].lower() == name.lower():
            return h['value']
    return ''


def extract_body(payload: dict) -> str:
    """Recursively pull plain-text body from a Gmail message payload."""
    mime = payload.get('mimeType', '')
    if mime == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
    elif 'multipart' in mime:
        for part in payload.get('parts', []):
            result = extract_body(part)
            if result:
                return result
    return ''


def format_thread(thread: dict, user_email: str) -> str:
    parts = []
    for msg in thread.get('messages', []):
        headers = msg['payload']['headers']
        sender = get_header(headers, 'From')
        date = get_header(headers, 'Date')
        subject = get_header(headers, 'Subject')
        body = extract_body(msg['payload']).strip()[:2000]
        role = 'You' if user_email.lower() in sender.lower() else sender
        parts.append(f"[From: {role}] [Date: {date}] [Subject: {subject}]\n{body}")
    return '\n\n---\n\n'.join(parts)


def get_threads_with_drafts(service) -> set:
    """Return the set of thread IDs that already have a draft."""
    draft_thread_ids: set = set()
    page_token = None
    while True:
        params: dict = {'userId': 'me', 'maxResults': 100}
        if page_token:
            params['pageToken'] = page_token
        result = service.users().drafts().list(**params).execute()
        for draft in result.get('drafts', []):
            tid = draft.get('message', {}).get('threadId')
            if tid:
                draft_thread_ids.add(tid)
        page_token = result.get('nextPageToken')
        if not page_token:
            break
    return draft_thread_ids


def build_raw_reply(
    to: str, subject: str, body: str,
    from_email: str, in_reply_to: str, references: str,
) -> str:
    msg = email.mime.text.MIMEText(body, 'plain', 'utf-8')
    msg['To'] = to
    msg['From'] = from_email
    msg['Subject'] = subject if subject.lower().startswith('re:') else f'Re: {subject}'
    if in_reply_to:
        msg['In-Reply-To'] = in_reply_to
    if references:
        msg['References'] = references
    return base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')


def load_writing_style() -> str | None:
    if os.path.exists('writing_style.md'):
        with open('writing_style.md') as f:
            content = f.read().strip()
        return content if content else None
    return None


def draft_reply(thread: dict, user_email: str, service, claude: anthropic.Anthropic, style: str | None) -> bool:
    """Generate and save a draft reply. Returns True if a draft was created."""
    messages = thread['messages']
    last = messages[-1]
    headers = last['payload']['headers']

    sender_raw = get_header(headers, 'From')
    match = re.search(r'<(.+?)>', sender_raw)
    sender_email = match.group(1) if match else sender_raw.strip()
    subject = get_header(headers, 'Subject') or '(no subject)'
    msg_id = get_header(headers, 'Message-ID')
    existing_refs = get_header(headers, 'References')
    references = f'{existing_refs} {msg_id}'.strip() if existing_refs else msg_id

    thread_text = format_thread(thread, user_email)
    style_block = f'\n\nUSER WRITING STYLE:\n{style}' if style else ''

    system = (
        f'You draft email replies on behalf of {user_email}.\n'
        'Rules:\n'
        '- Output ONLY the reply body. No subject, no "Here is a draft:", no preamble.\n'
        '- If the email is a newsletter, marketing message, automated alert, or genuinely '
        'needs no personal reply, output exactly: SKIP\n'
        '- Use [TODO: ...] where the user needs to fill in specific information.\n'
        '- Keep it concise and genuine.'
        f'{style_block}'
    )

    resp = claude.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1024,
        system=system,
        messages=[{
            'role': 'user',
            'content': f'Draft a reply to this email thread:\n\n{thread_text}',
        }],
    )

    draft_body = resp.content[0].text.strip()
    if draft_body.upper() == 'SKIP':
        return False

    raw = build_raw_reply(
        to=sender_email,
        subject=subject,
        body=draft_body,
        from_email=user_email,
        in_reply_to=msg_id,
        references=references,
    )

    service.users().drafts().create(
        userId='me',
        body={'message': {'threadId': thread['id'], 'raw': raw}},
    ).execute()
    return True


def main():
    print(f"\n{'='*55}")
    print(f"  Email Draft Routine — {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"{'='*55}")

    service = get_gmail_service()
    claude = anthropic.Anthropic()
    user_email = service.users().getProfile(userId='me').execute()['emailAddress']
    style = load_writing_style()

    print(f"Account : {user_email}")
    print(f"Style   : {'loaded from writing_style.md' if style else 'using defaults'}\n")

    threads_with_drafts = get_threads_with_drafts(service)

    result = service.users().threads().list(
        userId='me', q='in:inbox', maxResults=50
    ).execute()
    inbox_threads = result.get('threads', [])
    print(f"Inbox threads fetched : {len(inbox_threads)}")

    drafted = skipped = errors = 0

    for summary in inbox_threads:
        tid = summary['id']
        if tid in threads_with_drafts:
            continue

        thread = service.users().threads().get(
            userId='me', threadId=tid, format='full'
        ).execute()

        messages = thread.get('messages', [])
        if not messages:
            continue

        last = messages[-1]
        sender = get_header(last['payload']['headers'], 'From')
        subject = get_header(last['payload']['headers'], 'Subject') or '(no subject)'

        # Skip threads where the last message is already from us
        if user_email.lower() in sender.lower():
            continue

        # Skip automated senders
        if is_automated(sender):
            continue

        print(f"\n  → {subject[:60]}")
        print(f"    From: {sender[:60]}")

        try:
            created = draft_reply(thread, user_email, service, claude, style)
            if created:
                print('    ✓ Draft created')
                drafted += 1
            else:
                print('    — Skipped (no personal reply needed)')
                skipped += 1
        except Exception as exc:
            print(f'    ✗ Error: {exc}')
            errors += 1

    print(f"\n{'='*55}")
    print(f"  Drafted: {drafted}  |  Skipped: {skipped}  |  Errors: {errors}")
    print(f"{'='*55}\n")


if __name__ == '__main__':
    main()
