/** Runtime configuration, baked in at build time from Terraform outputs (see .env.example). */
export const config = {
  apiUrl: (import.meta.env.VITE_API_URL ?? 'http://localhost:3000').replace(/\/$/, ''),
  authMode: (import.meta.env.VITE_AUTH_MODE ?? 'amplify') as 'amplify' | 'fake',
  cognito: {
    userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID ?? '',
    userPoolClientId: import.meta.env.VITE_COGNITO_CLIENT_ID ?? '',
    domain: import.meta.env.VITE_COGNITO_DOMAIN ?? '',
  },
  webUrl: (import.meta.env.VITE_WEB_URL ?? window.location.origin).replace(/\/$/, ''),
}
