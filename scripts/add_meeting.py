#!/usr/bin/env python3
import argparse
import csv
import os
import sys

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', '_data', 'meetings.csv')


def ensure_header(path, header):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)


def append_row(path, row, header):
    ensure_header(path, header)
    # Read existing rows and drop any completely-empty rows
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for r in reader:
            # consider a row empty if all fields are empty strings
            if any(field.strip() for field in r):
                rows.append(r)

    # Ensure header is present as the first row
    if not rows or [h for h in rows[0]] != header:
        # replace rows with header if header missing
        rows = [header] + [r for r in rows if r != header]

    # Build new row matching header order
    out_row = [row.get(h, '') for h in header]

    # Append the new row and write the file back without extraneous blank lines
    rows.append(out_row)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description='Append a meeting entry to _data/meetings.csv')
    parser.add_argument('--date', required=True, help='Date string for the meeting (e.g. 01/15/2026)')
    parser.add_argument('--location', default='', help='Location or note for the meeting')
    parser.add_argument('--time', default='', help='Time for the meeting (e.g. 7-9pm)')
    args = parser.parse_args()

    header = ['date', 'location', 'time']
    entry = {
        'date': args.date,
        'location': args.location,
        'time': args.time,
    }

    csv_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '_data', 'meetings.csv'))
    try:
        append_row(csv_path, entry, header)
    except Exception as e:
        print('Error appending to CSV:', e, file=sys.stderr)
        sys.exit(1)

    print('Appended meeting to', csv_path)


if __name__ == '__main__':
    main()
