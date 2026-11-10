# Daily trigger (Cloudflare Worker)

## What it does and why

GitHub starts scheduled runs 4.5 to 10 hours late. This Worker calls the GitHub
workflow-dispatch API at 05:17 UTC every day, so `daily-predictions` starts on time.
The `schedule` in `daily.yml` stays as a late fallback.

## Setup (owner)

1. Create a GitHub fine-grained personal access token. Limit it to the repository
   `straf10/675hoops-Euroleague-Analytics`. Set the permission "Actions: Read and write"
   and no other permission. Set an expiry date.
2. Run `cd infra/daily-trigger`.
3. Run `npx wrangler secret put GITHUB_TOKEN` and paste the token.
4. Run `npx wrangler deploy`.
5. Check the setup:
   - In the Cloudflare dashboard, open the Worker. "Settings > Triggers" shows the cron `17 5 * * *`.
   - After 05:17 UTC, a run with event `workflow_dispatch` appears in the repo's Actions tab.

## What stays

The GitHub `schedule` in `daily.yml` is unchanged. It still runs later in the day as a fallback.
So there are two full runs per day. The second run makes one more odds API call.

## How to stop it

1. Run `npx wrangler delete`.
2. Revoke the token on GitHub.

## Token expiry

When the token expires, the cron fails with status 401. To fix it, renew the token
and run step 3 again.

## Not verified

The Cron Trigger limits of the Cloudflare free plan are not verified. Check the
Cloudflare dashboard at setup.
