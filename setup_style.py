#!/usr/bin/env python3
"""
One-time setup: reads your sent emails and generates writing_style.md.
Run this locally before your first deploy:
    python setup_style.py
"""

import base64
import re

import anthropic
from gmail_auth import get_gmail_service


def get_header(headers: list, name: str) -> str:
    for h in headers:
        if h['name'].lower() == name.lower():
            return h['value']
    return ''


def extract_body(payload: dict) -> str:
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


def main():
    print('Connecting to Gmail...')
    service = get_gmail_service()
    claude = anthropic.Anthropic()

    user_email = service.users().getProfile(userId='me').execute()['emailAddress']
    print(f'Account: {user_email}')
    print('Fetching sent emails (last 180 days)...')

    result = service.users().messages().list(
        userId='me',
        q='in:sent newer_than:180d',
        maxResults=60,
    ).execute()

    message_refs = result.get('messages', [])
    print(f'Found {len(message_refs)} sent messages. Fetching content...')

    samples = []
    for ref in message_refs:
        try:
            msg = service.users().messages().get(
                userId='me', id=ref['id'], format='full'
            ).execute()
            headers = msg['payload']['headers']
            to = get_header(headers, 'To')
            subject = get_header(headers, 'Subject')
            body = extract_body(msg['payload']).strip()

            # Skip very short messages and automated replies
            if len(body) < 30:
                continue
            # Skip if it looks like a forwarded message
            if re.search(r'^(fwd?:|fw:)', subject, re.IGNORECASE):
                continue

            samples.append(f'To: {to}\nSubject: {subject}\n\n{body[:1200]}')
        except Exception:
            continue

    if not samples:
        print('\nNo usable sent emails found.')
        print('writing_style.md was NOT created — the routine will use its defaults.')
        return

    # Cap at 25 samples to keep the prompt reasonable
    samples = samples[:25]
    samples_text = '\n\n===\n\n'.join(samples)

    print(f'\nAnalyzing {len(samples)} emails with Claude to build your style profile...')

    resp = claude.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        messages=[{
            'role': 'user',
            'content': (
                f'Analyze these emails written by {user_email} and produce a detailed, '
                'practical writing style guide that another AI can use to convincingly '
                'mimic this person\'s email voice.\n\n'
                'Cover:\n'
                '1. Overall tone (formal vs casual, warm vs direct, etc.)\n'
                '2. Typical greeting phrases (e.g., "Hey", "Hi [name]", "Hello")\n'
                '3. Typical sign-off phrases (e.g., "Thanks!", "Best," "Cheers")\n'
                '4. Sentence length and structure preferences\n'
                '5. Vocabulary or phrases they use repeatedly\n'
                '6. How they handle requests, thank-yous, updates, and follow-ups differently\n'
                '7. Use of humor, personality, or personal touches\n'
                '8. How concise or detailed they tend to be\n'
                '9. Punctuation and formatting habits\n\n'
                'Be specific. Quote actual phrases where helpful. '
                'Format as a guide an AI can act on immediately.\n\n'
                f'SENT EMAILS:\n\n{samples_text}'
            ),
        }],
    )

    style_guide = resp.content[0].text.strip()

    with open('writing_style.md', 'w') as f:
        f.write(f'# Writing Style Profile — {user_email}\n\n')
        f.write(f'*Generated from {len(samples)} sent emails*\n\n')
        f.write('---\n\n')
        f.write(style_guide)
        f.write('\n')

    print('\nwriting_style.md created successfully!')
    print('Review it, make any tweaks, then commit it to the repo.')
    print('The routine will use it automatically on every run.')


if __name__ == '__main__':
    main()
