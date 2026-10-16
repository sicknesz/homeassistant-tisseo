"""Platform for sensor integration."""
from datetime import timedelta
import logging
import voluptuous as vol
import asyncio
import logging
import aiohttp
import async_timeout
import urllib.parse
import sys
import json
import datetime

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_DEPARTURES = "departs"
ATTR_RETURNS = "retours"
ATTR_MESSAGES = "messages"

REQUEST_TIMEOUT = 5

BASE_URL = "https://api.tisseo.fr/v2/"
CONF_APIKEY = "api_key"
CONF_STOPNAME = "stop_name"
CONF_LINENAME = "bus_line"
DEFAULT_NAME = "TisseoHoraires"

ICON = "mdi:bus"

SCAN_INTERVAL = timedelta(seconds=90)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_APIKEY): cv.string,
        vol.Required(CONF_STOPNAME): cv.string,
        vol.Required(CONF_LINENAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

def sec_to_hours(seconds):
    a=str(seconds//3600)
    b=str((seconds%3600)//60)
    c=str((seconds%3600)%60)
    d="{} heures {} minutes {} secondes".format(a, b, c)
    return d


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    apiKey = config.get(CONF_APIKEY)
    stopName = config.get(CONF_STOPNAME)
    lineName = config.get(CONF_LINENAME)
    name = config.get(CONF_NAME)
    _LOGGER.debug("Sensor Integration Setup Done. Using: key:%s stop:%s line:%s, sensor name : %s", apiKey, stopName, lineName, name)

    session = async_get_clientsession(hass)
    async_add_entities([TisseoSensor(apiKey, stopName, lineName, name, session, hass.loop)])


class TisseoSensor(Entity):
    """Representation of a Sensor."""
    
    def __init__(self, apiKey, stopName, lineName, name, session, loop):
        """Initialize the sensor."""
        self._apiKey = apiKey
        self._stopName = stopName
        self._lineName = lineName
        self._name = name
        self._state = None
        self._session = session
        self._departuresData = []
        self._returnData = []
        self._messages = []
        self._loop = loop

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return (
            self._state
            if self._state is not None
            else None
        )
        
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DEPARTURES: self._departuresData,
            ATTR_RETURNS: self._returnData,
            ATTR_MESSAGES: self._messages
        }
        
        
    async def http_async_get(self, url):
        
        try:
            with async_timeout.timeout(REQUEST_TIMEOUT):
              response = await self._session.get(url, raise_for_status=True)
              return await response.json()

        except asyncio.TimeoutError:
            _LOGGER.error("Can not load data from api.tisseo.fr")
        
        except aiohttp.ClientError as aiohttpClientError:
            _LOGGER.error("Response from api.tisseo.fr: %s", aiohttpClientError)  


    async def async_update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        try:
            
          # GET the lineId
          data = await self.http_async_get(f"{BASE_URL}lines.json?key={self._apiKey}&shortName={self._lineName}")
          lineId = data['lines']['line'][0]['id']

          # get the stops ids (both directions)
          data = await self.http_async_get(f"{BASE_URL}stop_points.json?key={self._apiKey}&lineId={lineId}")
          stopsArray = data['physicalStops']['physicalStop']

          # reset results on each request
          self._messages = []
          self._departuresData = []
          self._returnData = []
          
	      # get the important message if any
          #data = await self.http_async_get(f"{BASE_URL}messages.json?key={self._apiKey}&displayImportantOnly=1")
          #data = {
          #  "message": data['messages'][0]['message']['content'], 
          #  "title": data['messages'][0]['message']['title'], 
          #  "url": data['messages'][0]['message']['url']
          #}
          
          #self._messages.append(data)

          # parse stops and find id
          for j, subjobj in enumerate(stopsArray):
              if(self._stopName == stopsArray[j]['name']):
                  stopIndex = j
                  stopId = stopsArray[stopIndex]['id']
                  data = await self.http_async_get( f"{BASE_URL}stops_schedules.json?key={self._apiKey}&stopsList={stopId}")

                  depsArray = data['departures']['departure']
                  
                  for i, subjobj in enumerate(depsArray):
                    if(self._lineName == depsArray[i]['line']['shortName']):
                      date_time_str = depsArray[i]['dateTime']
                      date_time_obj = datetime.datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')   
                      now = datetime.datetime.now()
                      datetime_str = date_time_obj.strftime("%HH%M")
                      relative_date = date_time_obj - now
                      delta_minutes = round(relative_date.seconds/60)
                      #_LOGGER.debug(f"relative_date {relative_date} relative_str {relative_str}")   
                      
                      data_set = {"ligne": self._lineName, "heure": datetime_str, "direction": depsArray[i]['destination'][0]['name'], "eta": sec_to_hours(60*delta_minutes)}
                      _LOGGER.debug(f"adding {json.dumps(data_set)} to state")   

                      if j == 0 or j == 2:
                        self._departuresData.append(data_set) 
                      else: 
                        self._returnData.append(data_set)
                      
                      self._state = len(self._departuresData)
                      _LOGGER.debug("sent %d elements to state", len(self._departuresData) + len(self._returnData))
                      
          self._departuresData.reverse()
          self._returnData.reverse()
          _LOGGER.debug(f"dump return data {json.dumps(self._returnData)}.")  
          
        except Exception as e:
            self._state = "Error {e}"
            _LOGGER.error(f"Unable to retrieve data from api.tisseo.fr Error : {e}")
            
                 
        
