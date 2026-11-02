# cognito

User pool for Localbini: username/password sign-up with email verification, Google social login, Hosted UI and a public (PKCE) web client. Roles are the Cognito groups **`admin`** and **`organizer`**; membership arrives in the `cognito:groups` claim of both ID and access tokens.

`terraform test` (mocked AWS provider) asserts the contract: `cd infra/modules/cognito && terraform init -backend=false && terraform test`.

## Manual steps (once per environment)

1. **Google OAuth client** in Google Cloud Console → APIs & Services → Credentials → *OAuth client ID* → *Web application*:
   - Authorized JavaScript origin: `https://<hosted_ui_domain>`
   - Authorized redirect URI: `https://<hosted_ui_domain>/oauth2/idpresponse`
   (`terraform output -raw hosted_ui_domain`)
2. **Write the credentials into SSM** (Terraform only created `CHANGE_ME` placeholders and never reads the secret back into state):
   ```bash
   aws ssm put-parameter --overwrite --name /localbini/dev/google/client_id --type String --value '<id>.apps.googleusercontent.com'
   aws ssm put-parameter --overwrite --name /localbini/dev/google/client_secret --type SecureString --value '<secret>'
   ```
3. Re-run `terraform apply` so the Google identity provider picks them up. Until then, set `enable_google_login = false` if you want a clean apply without Google.
4. **First Admin**: sign up through the web app, then
   ```bash
   aws cognito-idp admin-add-user-to-group --user-pool-id <pool> --username <email> --group-name admin
   ```
   Admins assign the `organizer` group from the web app (#11).
