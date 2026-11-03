# Notifications

Emails Attendees through SES. Bus events reach the Lambda through SQS:

```
EventBridge rule (BookingConfirmed, EventBookingsCancelled)
  → SQS meeton-<env>-notifications (visibility 6 min, maxReceiveCount 5)
      → Lambda (batch 5, ReportBatchItemFailures)        ↘ DLQ after 5 failed receives
```

- **Partial-batch failures**: only the records whose handler raised go back to the queue.
- **Idempotency**: every email has a key (e.g. `BookingConfirmed#<booking>`); a conditional put claims it before sending and is released if SES fails, so redeliveries never send twice and failed sends are retried.
- **Templates** (`templates/<name>.{subject,html,txt}`): Jinja2, HTML autoescaped (Event titles are user input), strict undefined, single-line subjects.

## Manual setup (SES sandbox)

1. Set the repository variables used by CI: `SENDER_EMAIL` (address to send from) and `ALERT_EMAILS` (JSON list, e.g. `["you@example.com"]`). Locally, copy `infra/envs/<env>/terraform.tfvars.example` to `terraform.tfvars` (gitignored).
2. After `terraform apply`, SES emails the sender address a verification link: click it.
3. Sandbox accounts can only send **to verified addresses** (max 1 email/s, 200/day). Verify each test recipient: `aws sesv2 create-email-identity --email-identity <recipient>`, then click the link.
4. Production access (sending to anyone) is out of scope for now; request it in the SES console when needed and raise `ses_max_send_rate`.
