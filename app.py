from os import listdir
from os.path import exists, join, dirname
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools

import datetime
from dateutil import parser
import json
import logging
import requests
import toml


logging.basicConfig(
    filename="run.log",
    format="%(asctime)s %(levelname)-8s %(module)s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

config = toml.load("config.toml")
ALBUM_ID = config["photos"]["album_id"]
SHEET_ID = config["sheets"]["sheet_id"]
CELL_RANGE = config["sheets"]["cell_range"]
CALENDAR_ID = config["calendar"]["calendar_id"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/photoslibrary.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
]

store = file.Storage(join(dirname(__file__), "token.json"))
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets("credentials.json", SCOPES)
    creds = tools.run_flow(flow, store)


def get_photos(creds):
    google_photos = build(
        "photoslibrary", "v1", http=creds.authorize(Http()), static_discovery=False
    )

    results = (
        google_photos.mediaItems()
        .search(
            body={
                # Goodash album
                "albumId": ALBUM_ID,
                "pageSize": 100,  # max = 100
            }
        )
        .execute()
    )

    items = results.get("mediaItems", [])
    logger.info(f"Found {len(items)} photos...")
    for item in items:
        url = item["baseUrl"]
        filename = "templates/img/slideshow/" + item["filename"]
        if not exists(filename):
            r = requests.get(url)
            with open(filename, "wb") as f:
                f.write(r.content)
                f.close()

    files = ["img/slideshow/" + file for file in listdir("templates/img/slideshow/")]
    with open("templates/js/photos.js", "w") as f:
        f.write(f"var photos = {json.dumps(files, indent=4)};")
        f.close()

    logger.info("Photo sync complete.")


def get_sheets(creds):
    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SHEET_ID, range=CELL_RANGE).execute()
        values = result.get("values", [])
        if not values:
            logger.info("No data found.")
            return
        for row in values:
            print("%s, %s" % (row[0], row[1]))
    except Exception as e:
        print(e)


def pretty_time(iso_date: str, is_start: bool):
    dt = parser.parse(iso_date)
    today = datetime.datetime.now().strftime("%d")
    ftime = dt.strftime("%I:%M%p")
    if ftime[0] == "0":
        ftime = ftime[1:]
    if dt.strftime("%d") != today and is_start:
        ftime = "Tomorrow " + ftime
    return ftime


def get_calendar(creds):
    try:
        service = build("calendar", "v3", credentials=creds)
        t0 = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=12)
        t1 = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=36)

        events_list = (
            service.events()
            .list(
                calendarId=CALENDAR_ID,
                orderBy="startTime",
                timeMin=t0.isoformat(),
                timeMax=t1.isoformat(),
                singleEvents=True,
            )
            .execute()
        )
        events = events_list.get("items", [])
        logger.info(f"Found {len(events)} events...")

        calendar = []
        for event in events:
            if "summary" in event.keys():
                start = pretty_time(event["start"]["dateTime"], True)
                end = pretty_time(event["end"]["dateTime"], False)
                calendar.append(
                    {
                        "start_dt": event["start"]["dateTime"],
                        "summary": event["summary"],
                        "start": start,
                        "end": end,
                    }
                )

        from operator import itemgetter

        calendar.sort(key=itemgetter("start_dt"))
        with open("templates/js/calendar.js", "w") as f:
            f.write(f"var calendar = {json.dumps(calendar, indent=4)};")
            f.close()

    except Exception as e:
        logger.error(e)

    logger.info("Calendar sync complete.")


def main():
    now = datetime.datetime.now()
    logger.info("Starting...")
    # get_photos(creds)
    get_calendar(creds)
    # get_sheets(creds)

    logger.info("Done.")


if __name__ == "__main__":
    main()
