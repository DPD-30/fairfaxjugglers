#!/usr/bin/env python3
"""
Sync meetings from CSV to Google Calendar.

Setup:
1. Create a Google Cloud project and enable the Google Calendar API
2. Create a service account and download the JSON credentials
3. Share your Google Calendar with the service account email
4. Add secrets to GitHub:
   - GOOGLE_CALENDAR_CREDENTIALS: Base64-encoded service account JSON
   - GOOGLE_CALENDAR_ID: Your Google Calendar ID (email address)
"""

import os
import sys
import csv
import json
import base64
import hashlib
from datetime import datetime, time
import traceback
from zoneinfo import ZoneInfo
from datetime import timedelta
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


CALENDAR_API_SCOPES = ['https://www.googleapis.com/auth/calendar']
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', '_data', 'meetings.csv')


def get_calendar_service():
    """Create and return a Google Calendar service."""
    credentials_json = os.environ.get('GOOGLE_CALENDAR_CREDENTIALS')
    if not credentials_json:
        raise ValueError('GOOGLE_CALENDAR_CREDENTIALS environment variable not set')
    
    try:
        # Decode from base64
        credentials_dict = json.loads(base64.b64decode(credentials_json))
    except Exception as e:
        raise ValueError(f'Failed to decode credentials: {e}')
    
    credentials = Credentials.from_service_account_info(
        credentials_dict,
        scopes=CALENDAR_API_SCOPES
    )
    
    service = build('calendar', 'v3', credentials=credentials)
    return service


def parse_time_range(time_str):
    """
    Parse time ranges like:
    - '7-9pm'
    - '11am-11pm'
    - '7:30pm-9:15pm'
    - '7pm-1am' (overnight)
    """

    if not time_str:
        raise ValueError("Empty time string")

    original = time_str
    time_str = time_str.strip().lower().replace(" ", "")

    if '-' not in time_str:
        raise ValueError(f"Invalid time range format: '{original}'")

    start_str, end_str = time_str.split('-', 1)

    def normalize(t, fallback_meridiem=None):
        """Ensure time has am/pm and minutes."""
        if 'am' not in t and 'pm' not in t:
            if not fallback_meridiem:
                raise ValueError(f"Missing am/pm in '{original}'")
            t += fallback_meridiem

        # Add :00 if missing minutes
        if ':' not in t:
            t = t.replace('am', ':00am').replace('pm', ':00pm')

        return t

    # Determine fallback meridiem from end time
    fallback_meridiem = None
    if 'am' in end_str:
        fallback_meridiem = 'am'
    elif 'pm' in end_str:
        fallback_meridiem = 'pm'

    start_str = normalize(start_str, fallback_meridiem)
    end_str = normalize(end_str)

    try:
        start_time = datetime.strptime(start_str, '%I:%M%p').time()
        end_time = datetime.strptime(end_str, '%I:%M%p').time()
    except Exception as e:
        raise ValueError(f"Failed to parse time '{original}': {e}")

    return start_time, end_time

def read_meetings_from_csv():
    """Read meetings from CSV file."""
    meetings = []
    
    if not os.path.exists(CSV_PATH):
        print(f'CSV file not found: {CSV_PATH}')
        return meetings
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('date') and row.get('location'):
                meetings.append(row)
    
    return meetings


def generate_meeting_id(meeting_date, location, address):
    """Generate a unique ID for a meeting based on date, location, and address."""
    meeting_key = f"{meeting_date}_{location}_{address}"
    return hashlib.md5(meeting_key.encode()).hexdigest()


def meeting_exists(service, calendar_id, meeting_date, location, address):
    """Check if a meeting already exists in the calendar using extendedProperties or fallback matching."""
    # Generate the unique meeting ID
    meeting_id = generate_meeting_id(meeting_date, location, address)
    target_timezone = "America/New_York"
    # Create a timezone object
    tz = ZoneInfo(target_timezone)
   
    # Parse date and time to build the calendar location string
    calendar_location = location
    if address:
        calendar_location = f"{location}, {address}"
    
    # Parse date and convert to UTC range for the day in America/New_York timezone
    # Eastern Time is UTC-5 (EST) or UTC-4 (EDT)
    # For February, it's EST (UTC-5), so:
    # 02/05/2026 00:00:00 EST = 02/05/2026 05:00:00 UTC
    # 02/05/2026 23:59:59 EST = 02/06/2026 04:59:59 UTC
    date_obj = datetime.strptime(meeting_date, '%m/%d/%Y')
    print(f'DEBUG: raw date: {meeting_date} - datetime.strptime(meeting_date, %m/%d/%Y)  {meeting_date}')
   
    
    # Day start in EST/EDT becomes this hour in UTC
        # Day start in EST/EDT becomes this hour in UTC
    start_of_day_utc = datetime.combine(date_obj, time(0,0,0), tzinfo=tz) 
    # Day end in EST/EDT
    end_of_day_utc = datetime.combine(date_obj, time.max, tzinfo=tz) 
    # Convert to RFC3339 format with Z suffix for UTC
    start_str = start_of_day_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_str = end_of_day_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Search for events on this date with the matching ID in extendedProperties
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_str,
        timeMax=end_str,
        singleEvents=True,
        maxResults=50
    ).execute()
    
    events = events_result.get('items', [])
    print(f'DEBUG: Checking for meeting on {meeting_date}, looking for ID: {meeting_id}')
    print(f'DEBUG: Query range: {start_str} to {end_str}')
    print(f'DEBUG: Found {len(events)} events on this date')
    
    for event in events:
        # Check for matching sync ID (primary method)
        event_props = event.get('extendedProperties', {}).get('private', {})
        event_sync_id = event_props.get('meeting_sync_id', '')
        print(f'DEBUG: Event "{event.get("summary")}" has sync ID: {event_sync_id}')
        
        if event_sync_id == meeting_id:
            print(f'DEBUG: Found matching sync ID!')
            return True
    
    print(f'DEBUG: No matching event found')
    return False


def add_meeting_to_calendar(service, calendar_id, meeting):
    """Add a meeting to Google Calendar."""
    meeting_date = meeting.get('date', '')
    location = meeting.get('location', '')
    address = meeting.get('address', '')
    time_range = meeting.get('time', '')
    
    # Skip if already exists
    if meeting_exists(service, calendar_id, meeting_date, location, address):
        print(f'Meeting already exists: {meeting_date} at {location}')
        return False
    
    # Parse date and time
    date_obj = datetime.strptime(meeting_date, '%m/%d/%Y')
    start_time, end_time = parse_time_range(time_range)
    
    if not start_time or not end_time:
        print(f'Warning: Could not parse time "{time_range}" for {meeting_date}')
        start_time = start_time or datetime.strptime('19:00', '%H:%M').time()
        end_time = end_time or datetime.strptime('21:00', '%H:%M').time()
    
    target_timezone = "America/New_York"
    # Create a timezone object
    tz = ZoneInfo(target_timezone)

    start_datetime = datetime.combine(date_obj.date(), start_time, tzinfo=tz)
    end_datetime = datetime.combine(date_obj.date(), end_time, tzinfo=tz)
    # Handle overnight events (e.g., 7pm–1am)
    if end_datetime <= start_datetime:
        end_datetime += timedelta(days=1)

    # Combine location and address for the calendar event
    calendar_location = location
    if address:
        calendar_location = f"{location}, {address}"
    
    # Generate unique meeting ID
    meeting_id = generate_meeting_id(meeting_date, location, address)
    
    # Create event
    event = {
        'summary': 'Fairfax Jugglers Meeting',
        'location': calendar_location,
        'description': 'Fairfax Jugglers Meetup',
        'start': {
            'dateTime': start_datetime.isoformat(),
            'timeZone': 'America/New_York',
        },
        'end': {
            'dateTime': end_datetime.isoformat(),
            'timeZone': 'America/New_York',
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                {'method': 'popup', 'minutes': 60},  # 1 hour before
            ],
        },
        'extendedProperties': {
            'private': {'meeting_sync_id': meeting_id}
        },
    }
    
    created_event = service.events().insert(
        calendarId=calendar_id,
        body=event
    ).execute()
    
    
    print(f'Created event: {meeting_date} at {calendar_location}')
    print(f'Event ID: {created_event.get("id")}')
    return True


def main():
    """Main function."""
    calendar_id = os.environ.get('GOOGLE_CALENDAR_ID')
    if not calendar_id:
        print('Error: GOOGLE_CALENDAR_ID environment variable not set')
        sys.exit(1)
    
    try:
        service = get_calendar_service()
        meetings = read_meetings_from_csv()
        
        if not meetings:
            print('No meetings found in CSV')
            sys.exit(0)
        
        added_count = 0
        for meeting in meetings:
            if add_meeting_to_calendar(service, calendar_id, meeting):
                added_count += 1
        
        print(f'\nSync complete. Added {added_count} new events.')
    
    except Exception as e:
        print(f'Error: {e}')
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
