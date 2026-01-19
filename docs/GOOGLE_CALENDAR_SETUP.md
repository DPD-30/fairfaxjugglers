# Google Calendar Integration Setup

This guide explains how to set up the GitHub Action to automatically sync Fairfax Jugglers meetings to Google Calendar.

## Prerequisites

- A Google Cloud Project
- Google Calendar API enabled
- A service account with Calendar API access
- A GitHub repository with secrets configured

## Step-by-Step Setup

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Give it a name like "Fairfax Jugglers Calendar"

### 2. Enable the Google Calendar API

1. In the Cloud Console, go to **APIs & Services** > **Library**
2. Search for "Google Calendar API"
3. Click on it and press **Enable**

### 3. Create a Service Account

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **Service Account**
3. Fill in the details:
   - Service account name: `fairfax-jugglers-calendar`
   - Click **Create and Continue**
4. Skip the optional steps and click **Done**

### 4. Create and Download Service Account Key

1. Under "Service Accounts", click the service account you just created
2. Go to the **Keys** tab
3. Click **Add Key** > **Create new key**
4. Choose **JSON** format
5. Click **Create** - this will download a JSON file

### 5. Share Your Calendar with the Service Account

1. Open the downloaded JSON file and copy the `client_email` value (something like `fairfax-jugglers-calendar@project-id.iam.gserviceaccount.com`)
2. Go to [Google Calendar](https://calendar.google.com/)
3. Find the calendar you want to sync to (or create a new one)
4. Right-click on the calendar > **Settings**
5. Go to **Share with specific people or groups**
6. Add the service account email address with "Make changes to events" permission

### 6. Get Your Calendar ID

1. In Google Calendar, right-click on the calendar > **Settings**
2. In the "Integrate calendar" section, copy the **Calendar ID** (usually your email address)

### 7. Configure GitHub Secrets

1. Go to your GitHub repository
2. Go to **Settings** > **Secrets and variables** > **Actions**
3. Create two new secrets:

#### Secret 1: `GOOGLE_CALENDAR_CREDENTIALS`
- Open the JSON file you downloaded
- Copy the entire JSON content
- Use this command to base64 encode it (or use an online tool):
  ```bash
  cat service-account-key.json | base64 -w 0
  ```
- Paste the entire base64 string as the secret value

#### Secret 2: `GOOGLE_CALENDAR_ID`
- Paste your Calendar ID (the email-like identifier)

### 8. Test the Action

1. Go to your GitHub repository
2. Go to **Actions**
3. Select the "Sync Meetings to Google Calendar" workflow
4. Click **Run workflow** > **Run workflow**
5. The action will run and sync all meetings from `_data/meetings.csv` to your Google Calendar

## Workflow Triggers

The workflow automatically runs when:
- You push changes to `_data/meetings.csv`
- Every Sunday at 9 AM UTC (can be customized in the workflow file)
- You manually trigger it from the Actions tab

## Customization

### Change the Schedule
Edit `.github/workflows/sync-calendar.yml` and modify the cron expression:
```yaml
schedule:
  - cron: '0 9 * * 0'  # Change this line
```

Common cron patterns:
- `'0 9 * * 0'` - Every Sunday at 9 AM UTC
- `'0 20 * * 2'` - Every Tuesday at 8 PM UTC
- `'0 */12 * * *'` - Every 12 hours

### Customize Event Details
Edit `scripts/sync_google_calendar.py` to change:
- Event title (line ~160: `'summary': 'Fairfax Jugglers Meeting'`)
- Default duration if time parsing fails (line ~134)
- Reminder settings (lines ~168-171)
- Timezone (line ~167: currently set to `'America/New_York'`)

## Troubleshooting

### Authentication Failed
- Verify the service account JSON is correctly base64 encoded
- Ensure the service account email has access to the calendar
- Check that Calendar API is enabled in Google Cloud

### Events Not Showing Up
- Check the calendar ID is correct
- Verify the calendar is shared with the service account
- Check GitHub Action logs for detailed error messages

### Duplicate Events
- The script checks for existing events before creating new ones
- If manually created events exist, they won't be re-added

## Logging

View the workflow logs in GitHub:
1. Go to **Actions** tab
2. Click on the "Sync Meetings to Google Calendar" workflow
3. Click the most recent run
4. Click the "sync-calendar" job to view detailed logs

## Security Notes

- The Google Calendar credentials are stored as a GitHub Secret and are encrypted
- The service account has limited permissions (Calendar API only)
- Each GitHub Action run is isolated and doesn't have persistent access
- Consider rotating service account keys periodically
