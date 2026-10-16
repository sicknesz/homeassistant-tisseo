import requests
import json
from datetime import date
import datetime
import os

BASE_URL = "https://api.tisseo.fr/v2/"
API_KEY=os.environ['API_KEY']
LIGNE = "L1"
STOP_NAME = "Achiary"

# TODO : handle error properly 

# GET the lineId
r = requests.get(f"{BASE_URL}lines.json?key={API_KEY}&shortName={LIGNE}")
r_dictionary= r.json()

lines = json.loads(r.text)
lineId = lines['lines']['line'][0]['id']


# GET the stopId
r = requests.get(f"{BASE_URL}stop_points.json?key={API_KEY}&lineId={lineId}")
r_dictionary= r.json()

stops = json.loads(r.text)
stopsArray = stops['physicalStops']['physicalStop']

foundDepartures = []

# parse stops and find id
for i, subjobj in enumerate(stopsArray):
    if(STOP_NAME == stopsArray[i]['name']):
        #print(f"Found {stopsArray[i]['id']} stopId at {STOP_NAME}.")
        stopIndex = i
        stopId = stopsArray[stopIndex]['id']
        # https://api.tisseo.fr/v1/stops_schedules.json?key=clef&stopsList=3377704015495611
        stopQuery = f"{BASE_URL}stops_schedules.json?key={API_KEY}&stopsList={stopId}"
        #print(stopQuery)
        r = requests.get(f"{BASE_URL}stops_schedules.json?key={API_KEY}&stopsList={stopId}")
        #print(r.text)
        r_dictionary= r.json()
        #print(json.dumps(r.json(), indent=2))
        departures = json.loads(r.text)
        depsArray = departures['departures']['departure']
        for i, subjobj in enumerate(depsArray):
          if(LIGNE == depsArray[i]['line']['shortName']):
            foundDepartures.append(f"{LIGNE} - {depsArray[i]['dateTime']} Direction : {depsArray[i]['destination'][0]['name']}")            
            date_time_str = depsArray[i]['dateTime']
            date_time_obj = datetime.datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')   
            now = datetime.datetime.now()
            datetime_str = date_time_obj.strftime("%HH%M")
            relative_date = date_time_obj - now
            delta_minutes = round(relative_date.seconds/60)
            print(f"will be in {delta_minutes} minutes")
            

            data_set = {"line": LIGNE, "dateTime": datetime_str, "direction": depsArray[i]['destination'][0]['name'], "delta": delta_minutes}
            print(f"dateTime found {depsArray[i]['line']['shortName']} parsed: {datetime_str}")           

#print(foundDepartures)
url = f"{BASE_URL}messages.json?key={API_KEY}&displayImportantOnly=true"
r = requests.get(url)
print(json.dumps(r.json(), indent=2))
