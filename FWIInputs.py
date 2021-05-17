import ee
import eemont
import math
import datetime

class FWI_ERA5:
    """
    ECMWF ERA5 Reanalysis Hourly Dataset from Google Earth Engine
    for Canadian Fire Weather Index System calculation

    Attributes
    ----------
    date_time : datetime
        the datetime in noon local time for the observation
    bounds : ee.Geometry
        the boundary used to limit the ee.Image file
    temp : ee.Image
        temperature in degree Celsius observed in noon
    rhum : ee.Image
        relative humidity in percent observed in noon
    wind : ee.Image
        wind speed in kph observed in noon
    rain : ee.Image
        total precipitation in mm in the past 24 hours, observed in noon
    """

    def __init__(self, date_time, bounds):
        """
        Constructs all the necessary attributes to get the raster data
        observed at a certain datetime inside a boundary

        Attributes
        ----------
        date_time : datetime
            the datetime in noon local time for the observation
        bounds : ee.Geometry
            the boundary used to limit the ee.Image file
        """
        self.dataset = ee.ImageCollection('ECMWF/ERA5_LAND/HOURLY')
        self.date_time = date_time
        self.bounds = bounds
        self.__get_fwi_inputs()

    def __calculate_temperature(self):
        temp = self.dataset.select('temperature_2m') \
                    .closest(self.date_time.isoformat()) \
                    .first().clip(self.bounds)
        self.temp = temp - 273.15

    def __calculate_relative_humidity(self):
        try:
            temp = self.temp
        except AttributeError:
            self.__calculate_temperature()
            temp = self.temp

        dew = self.dataset.select('dewpoint_temperature_2m') \
                    .closest(self.date_time.isoformat()) \
                    .first().clip(self.bounds) - 273.15

        self.rhum = 100 * (math.exp(1) ** ((17.625 * dew) / (243.04 + dew)) / \
                    math.exp(1) ** ((17.625 * temp) / (243.04 + temp)))

    def __calculate_rain(self):
        start = self.date_time - datetime.timedelta(days = 1)

        rain_24h = self.dataset.select('total_precipitation') \
                        .filterDate(start.isoformat(), \
                                    self.date_time.isoformat()) \
                        .reduce(ee.Reducer.sum())

        self.rain = (rain_24h * 1000.0).clip(self.bounds)

    def __calculate_wind(self):
        u_comp = self.dataset.select('u_component_of_wind_10m') \
                        .closest(self.date_time.isoformat()) \
                        .first().clip(self.bounds)
        v_comp = self.dataset.select('v_component_of_wind_10m') \
                        .closest(self.date_time.isoformat()) \
                        .first().clip(self.bounds)
        self.wind = ((u_comp ** 2 + v_comp ** 2) ** 0.5) * 3.6

    def __get_fwi_inputs(self):
        self.__calculate_temperature()
        self.__calculate_relative_humidity()
        self.__calculate_wind()
        self.__calculate_rain()

    def update_fwi_inputs(self, date_time):
        """
        Updates the value of FWI input variables

        Parameters
        ----------
        date_time : datetime
            next date and time for observation data request
        Returns
        -------
        None
        """
        self.dataset = ee.ImageCollection('ECMWF/ERA5_LAND/HOURLY')
        self.date_time = date_time
        self.__get_fwi_inputs()
