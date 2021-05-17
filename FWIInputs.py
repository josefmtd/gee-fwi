import ee
import eemont
import math
import datetime

class FWI_GFS:
    """
    NOAA/NASA Global Forecast System (384-Hour Predicted Atmosphere Data)
    from Google Earth Engine for Canadian Fire Weather Index System calculation

    Attributes
    ----------
    date_time : datetime
        the datetime in noon local time for the observation
    bounds : ee.Geometry
        the boundary used to limit the ee.Image file
    use_gsmap : boolean
        use gsmap data for precipitation
    temp : ee.Image
        temperature in degree Celsius observed in noon
    rhum : ee.Image
        relative humidity in percent observed in noon
    wind : ee.Image
        wind speed in kph observed in noon
    rain : ee.Image
        total precipitation in mm in the past 24 hours, observed in noon
    """

    def __init__(self, date_time, bounds, use_gsmap):
        """
        Constructs all the necessary attributes to get the raster data
        observed at a certain datetime inside a boundary

        Attributes
        ----------
        date_time : datetime
            the datetime in noon local time for the observation
        bounds : ee.Geometry
            the boundary used to limit the ee.Image file
        use_gsmap : boolean
            use gsmap or ERA5 for total precipitation
        """
        self.date_time = date_time
        self.__time_stamp = int(self.date_time.timestamp()) * 1000
        self.bounds = bounds
        self.use_gsmap = use_gsmap

        self.dataset = ee.ImageCollection('NOAA/GFS0P25')
        self.__get_fwi_inputs()

    def __calculate_temperature(self):
        """
        Calculates the GFS temperature
        """
        self.temp = self.dataset.select('temperature_2m_above_ground') \
                        .closest(self.date_time.isoformat()) \
                        .filterMetadata('forecast_time', 'equals', \
                            self.__time_stamp).first() \
                        .clip(self.bounds).rename('GFS_T')

    def __calculate_relative_humidity(self):
        """
        Calculates the GFS relative humidity
        """
        self.rhum = self.dataset.select('relative_humidity_2m_above_ground') \
                        .closest(self.date_time.isoformat()) \
                        .filterMetadata('forecast_time', 'equals', \
                            self.__time_stamp).first() \
                        .clip(self.bounds).rename('GFS_RH')

    def __calculate_rain(self):
        """
        Calculates the GFS total rain
        """
        one_hour_ms = 3.6e6

        self.rain = self.dataset.select('total_precipitation_surface') \
                        .filterMetadata('forecast_time', 'equals', \
<<<<<<< HEAD
                            self.__time_stamp + one_hour_ms) \
=======
                            local_time_stamp + one_hour_ms) \
>>>>>>> 769b571519358236deb88df0709ca11d676050f1
                        .filterMetadata('forecast_hours', 'equals', 24) \
                        .first().clip(self.bounds).rename('GFS_R24H')

    def __calculate_wind(self):
        """
        Adds two vectors to find the wind speed scalar magnitude
        and convert from m/s to kph
        """
        u_comp = self.dataset.select('u_component_of_wind_10m_above_ground') \
                        .closest(self.date_time.isoformat()) \
                        .filterMetadata('forecast_time', 'equals', \
                            self.__time_stamp).first() \
                        .clip(self.bounds)

        v_comp = self.dataset.select('v_component_of_wind_10m_above_ground') \
                        .closest(self.date_time.isoformat()) \
                        .filterMetadata('forecast_time', 'equals', \
                            self.__time_stamp).first() \
                        .clip(self.bounds)

        self.wind = (((u_comp ** 2 + v_comp ** 2) ** 0.5) * 3.6).rename('GFS_W')

    def __calculate_rain_gsmap(self):
        """
        Use JAXA GSMaP to get past 24 hours rain in mm
        """
        start = self.date_time - datetime.timedelta(days = 1)

        self.rain = ee.ImageCollection("JAXA/GPM_L3/GSMaP/v6/operational") \
                        .select('hourlyPrecipRate') \
                        .filterDate(start.isoformat(), \
                                    self.date_time.isoformat()) \
                        .reduce(ee.Reducer.sum()) \
                        .clip(self.bounds).rename('GSMAP_R24H')

    def __get_fwi_inputs(self):
        """
        Calculate all the inputs required for FWI Calculation
        """
        self.__calculate_temperature()
        self.__calculate_relative_humidity()
        self.__calculate_wind()
        if self.use_gsmap:
            self.__calculate_rain_gsmap()
        else:
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

    def __init__(self, date_time, bounds, use_gsmap):
        """
        Constructs all the necessary attributes to get the raster data
        observed at a certain datetime inside a boundary

        Attributes
        ----------
        date_time : datetime
            the datetime in noon local time for the observation
        bounds : ee.Geometry
            the boundary used to limit the ee.Image file
        use_gsmap : boolean
            use gsmap or ERA5 for total precipitation
        """
        self.date_time = date_time
        self.bounds = bounds
        self.use_gsmap = use_gsmap

        self.dataset = ee.ImageCollection('ECMWF/ERA5_LAND/HOURLY')
        self.__get_fwi_inputs()

    def __calculate_temperature(self):
        """
        Calculates the ERA5 temperature from Kelvin to Celsius
        """
        temp = self.dataset.select('temperature_2m') \
                    .closest(self.date_time.isoformat()) \
                    .first().clip(self.bounds)
        self.temp = (temp - 273.15).rename('ERA5_T')

    def __calculate_relative_humidity(self):
        """
        Calculates the Relative Humidity from Dewpoint and temperature
        in Celsius
        """
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
        self.rhum = self.rhum.rename('ERA5_RH')

    def __calculate_rain(self):
        """
        Adds total_precipitation from past 24 hours and convert from m to mm
        """
        start = self.date_time - datetime.timedelta(days = 1)

        rain_24h = self.dataset.select('total_precipitation') \
                        .filterDate(start.isoformat(), \
                                    self.date_time.isoformat()) \
                        .reduce(ee.Reducer.sum()) \
                        .clip(self.bounds)

        self.rain = (rain_24h * 1000.0).rename('ERA5_R')

    def __calculate_wind(self):
        """
        Adds two vectors to find the wind speed scalar magnitude
        and convert from m/s to kph
        """
        u_comp = self.dataset.select('u_component_of_wind_10m') \
                        .closest(self.date_time.isoformat()) \
                        .first().clip(self.bounds)
        v_comp = self.dataset.select('v_component_of_wind_10m') \
                        .closest(self.date_time.isoformat()) \
                        .first().clip(self.bounds)
        self.wind = ((u_comp ** 2 + v_comp ** 2) ** 0.5) * 3.6
        self.wind = self.wind.rename('ERA5_W')

    def __calculate_rain_gsmap(self):
        """
        Use JAXA GSMaP to get past 24 hours rain in mm
        """
        start = self.date_time - datetime.timedelta(days = 1)

        self.rain = ee.ImageCollection("JAXA/GPM_L3/GSMaP/v6/operational") \
                        .select('hourlyPrecipRate') \
                        .filterDate(start.isoformat(), \
                                    self.date_time.isoformat()) \
                        .reduce(ee.Reducer.sum()) \
                        .clip(self.bounds)

    def __get_fwi_inputs(self):
        """
        Calculate all the inputs required for FWI Calculation
        """
        self.__calculate_temperature()
        self.__calculate_relative_humidity()
        self.__calculate_wind()
        if self.use_gsmap:
            self.__calculate_rain_gsmap()
        else:
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
