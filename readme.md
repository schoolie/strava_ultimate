# Store strava client secret in environment:

Copy client secret from https://www.strava.com/settings/api

export STRAVA_CLIENT_SECRET="`secret`"

# Get google sheets client secret json file:

Go to https://console.developers.google.com/apis/credentials

Under "OAuth 2.0 client IDs," select the link to download the appropriate credential file.

Save to project directory as `gsheet_secret.json`

`scp gsheet_secret.json [user]@[host]:~/strava_ultimate/gsheet_secret.json
`
