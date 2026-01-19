#!/usr/bin/env python3
import argparse
import csv
import os
import sys
from datetime import datetime, date
import shutil

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


def purge_past(path, header):
    # Make a backup before modifying
    if os.path.exists(path):
        bak = path + '.bak'
        shutil.copy2(path, bak)

    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for r in reader:
            if not any(field.strip() for field in r):
                continue
            rows.append(r)

    # ensure header present
    if not rows or rows[0] != header:
        # keep header from provided header
        rows = [header] + [r for r in rows if r != header]

    kept = [rows[0]]
    today = date.today()
    for r in rows[1:]:
        # try to parse date in first column with common formats
        dstr = r[0].strip()
        parsed = None
        for fmt in ("%m/%d/%Y", "%m/%d/%y"):
            try:
                parsed = datetime.strptime(dstr, fmt).date()
                break
            except Exception:
                parsed = None
        # if parsed and in the past, skip; otherwise keep
        if parsed is not None:
            if parsed >= today:
                kept.append(r)
        else:
            # keep rows with non-parseable dates
            kept.append(r)

    # write back
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(kept)


def main():
    parser = argparse.ArgumentParser(description='Append a meeting entry to _data/meetings.csv')
    parser.add_argument('--date', required=False, help='Date string for the meeting (e.g. 01/15/2026)')
    parser.add_argument('--location', default='', help='Location or note for the meeting')
    parser.add_argument('--address', default='', help='Address for the meeting')
    parser.add_argument('--time', default='', help='Time for the meeting (e.g. 7-9pm)')
    parser.add_argument('--purge-past', action='store_true', help='Remove meetings dated before today (creates .bak)')
    args = parser.parse_args()

    header = ['date', 'location', 'address', 'time']
    entry = {
        'date': args.date,
        'location': args.location,
        'address': args.address,
        'time': args.time,
    }

    csv_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '_data', 'meetings.csv'))
    # require date unless purge-only
    if not args.purge_past and not args.date:
        print('Error: --date is required unless --purge-past is used', file=sys.stderr)
        sys.exit(2)

    try:
        if args.purge_past:
            purge_past(csv_path, header)
            print('Purged past meetings (backup at', csv_path + '.bak' + ')')
        # only append when a date was supplied
        if args.date:
            append_row(csv_path, entry, header)
            print('Appended meeting to', csv_path)
    except Exception as e:
        print('Error modifying CSV:', e, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
