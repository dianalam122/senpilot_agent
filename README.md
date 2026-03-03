# UARB Document Request Agent

Processes email requests for Nova Scotia UARB documents: parses the request, fetches documents from the UARB WebDirect portal, zips them, and sends a reply by email.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright browsers

```bash
playwright install chromium
```

### 3. Configure SMTP (for sending emails)

Set these environment variables:

| Variable    | Description                    | Example          |
|-------------|--------------------------------|------------------|
| `SMTP_HOST` | SMTP server hostname           | `smtp.gmail.com`  |
| `SMTP_PORT` | SMTP port (default: 587)      | `587`            |
| `SMTP_USER` | SMTP username / email         | 'd@gmail.com`  |
| `SMTP_PASS` | SMTP password                 | (app password)   |
| `SMTP_FROM` | From address (optional)       | `you@gmail.com`  |

#### For security reasons, SMTP credentials are not included in this repository!

**Gmail users**: Use an [App Password](https://support.google.com/accounts/answer/185833), not your regular account password. Enable 2FA first, then generate an app password under Security → App passwords.

### 4. Run with sample email

```bash
python -m src.main --email_text_file sample_emails/sample_valid.txt --reply_to someone@example.com
```

- `--email_text_file`: Path to a `.txt` file containing the incoming email body.
- `--reply_to`: Recipient for the reply. If the parsed email contains a requester address, that is used; otherwise `--reply_to` is used.

## Flow

1. **Parse** – Extracts matter number (e.g., M12205) and document type from the email.
2. **Navigate** – Searches the UARB portal for the matter.
3. **Download** – Clicks "Go Get It" for each document in the requested tab.
4. **Zip** – Bundles downloaded files into a ZIP.
5. **Send** – Emails the reply with counts, summary, and ZIP attachment (if any).
