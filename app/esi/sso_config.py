# FILE: app/esi/sso_config.py
# VERSION: 1.1.0

# SECURITY NOTE:
# The ESI client ID is safe to hardcode.
# Do NOT add the secret key to this file or anywhere else in the app.

ESI_CLIENT_ID = "276100afb30f4c3eb527d65f2ec7c3e5"

# EVE SSO official endpoints.
ESI_AUTH_URL = "https://login.eveonline.com/v2/oauth/authorize/"
ESI_TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"

# Must match exactly what is configured in the EVE Developer Portal.
ESI_REDIRECT_URI = "http://127.0.0.1:8635/callback"