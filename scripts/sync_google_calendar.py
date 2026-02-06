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
from datetime import datetime
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
    """Parse time range string like '7-9pm' into start and end times."""
    time_str = time_str.strip()
    
    if '-' not in time_str:
        return None, None
    
    parts = time_str.split('-')
    if len(parts) != 2:
        return None, None
    
    start_str = parts[0].strip()
    end_str = parts[1].strip()
    
    # Handle AM/PM
    if 'pm' in end_str.lower() or 'am' in end_str.lower():
        meridiem = end_str[-2:].lower()
        if 'pm' not in start_str.lower() and 'am' not in start_str.lower():
            start_str += meridiem
    
    try:
        start_time = datetime.strptime(start_str, '%I%p').time()
        end_time = datetime.strptime(end_str, '%I%p').time()
        return start_time, end_time
    except ValueError:
        return None, None


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
    
    # Parse date and time to build the calendar location string
    calendar_location = location
    if address:
        calendar_location = f"{location}, {address}"
    
    # Parse date and create timezone-aware datetimes
    date_obj = datetime.strptime(meeting_date, '%m/%d/%Y')
    start_of_day = datetime(date_obj.year, date_obj.month, date_obj.day, 0, 0, 0)
    end_of_day = datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59)
    
    # Convert to RFC3339 with Z suffix for UTC
    start_str = start_of_day.isoformat() + 'Z'
    end_str = end_of_day.isoformat() + 'Z'
    
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
    print(f'DEBUG: Found {len(events)} events on this date')
    
    for event in events:
        # Check for matching sync ID (primary method)
        event_props = event.get('extendedProperties', {}).get('private', {})
        event_sync_id = event_props.get('meeting_sync_id', '')
        print(f'DEBUG: Event "{event.get("summary")}" has sync ID: {event_sync_id}')
        
        if event_sync_id == meeting_id:
            print(f'DEBUG: Found matching sync ID!')
            return True
        
        # Fallback: check for matching location and summary (for events created before sync ID was added)
        event_summary = event.get('summary', '')
        event_location = event.get('location', '')
        
        if event_summary == 'Fairfax Jugglers Meeting':
            # Check for exact location match
            if event_location == calendar_location:
                print(f'DEBUG: Found matching location (exact)')
                return True
            # Check if event location contains just the location name (for old events)
            if event_location == location:
                print(f'DEBUG: Found matching location (name only)')
                return True
            # Check if event location contains the address (handles variations)
            if address and address in event_location:
                print(f'DEBUG: Found matching location (address match)')
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
    
    start_datetime = datetime.combine(date_obj.date(), start_time)
    end_datetime = datetime.combine(date_obj.date(), end_time)
    
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
        sys.exit(1)


if __name__ == '__main__':
    main()
