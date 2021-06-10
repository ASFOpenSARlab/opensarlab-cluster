
"""
custom.ICAL_URL = 'https://calendar.google.com/calendar/ical/....'

c.JupyterHub.services = [
    {
        'name': 'notifications',
        'url': 'http://notifications.notifications'
    }
]

"""

import os
import argparse
from datetime import datetime
import json
from urllib.parse import urlparse
import re

import yaml
from ics import Calendar
import requests
from fastapi import FastAPI, HTTPException
import html2text

app = FastAPI()

def notes(profile_arg, ical_arg):

    try:
        cal = Calendar(requests.get(ical_arg).text)
        active_events = []
        
        for event in list(cal.events):
            begin_time = event.begin.to('utc').datetime.replace(tzinfo=None)
            now_time = datetime.utcnow().replace(tzinfo=None)
            end_time = event.end.to('utc').datetime.replace(tzinfo=None)

            if begin_time <= now_time <= end_time:
                compiled = re.compile("<meta>(.*)<message>(.*)$", re.DOTALL)
                descr_to_html = html2text.html2text(event.description)

                groups = compiled.search(descr_to_html)
                meta = yaml.safe_load(groups.group(1))
                message = groups.group(2)

                profile = [ prof.strip() for prof in meta['profile'].split(',') ]

                if 'mute' not in meta:
                    if type(profile) is not list:
                        profile = [profile]

                    if profile_arg in profile:
                        active_events.append(
                            {
                                "title": event.name,
                                "message": message.strip(),
                                "type": meta['type'].strip()
                            }
                        )
    
        print(f"Active events to popup: {active_events}")
        return active_events

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"{e}")

@app.get('/services/notifications/')
def main(profile: str='default', ical: str=None):
    if ical is None:
        ical = os.environ.get('ICAL_URL', None)
    if ical is None:
        raise HTTPException(status_code=404, detail="iCal URL not found.")

    return notes(profile, ical)
