import ee
import eemont
import math
from datetime import datetime, date, timedelta
import dateutil

class FWI_GFS_GSMAP:
    """
    NOAA/NASA Global Forecast System (384-Hour Predicted Atmosphere Data)
    from Google Earth Engine for Canadian Fire Weather Index System calculation

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

    def __init__(self, date, timezone, bounds):
        """
        Constructs all the necessary attributes to get the raster data
        observed at a certain date inside a boundary

        Attributes
        ----------
        date : datetime.date
            the date for observation
        timezone : dateutil.tz
            timezone
        bounds : ee.Geometry
            the boundary used to limit the ee.Image file
        """
        self.date = date
        self.bounds = bounds
        self.timezone = timezone

        self.__get_fwi_inputs()

    def __calculate_temperature(self):
        """
        Calculates the GFS temperature
        """
        temp_band = 'temperature_2m_above_ground'
        self.temp = self.gfs.select(temp_band) \
            .rename('T')

    def __calculate_relative_humidity(self):
        """
        Calculates the GFS relative humidity
        """
        rhum_band = 'relative_humidity_2m_above_ground'
        self.rhum = self.gfs.select(rhum_band) \
            .rename('H')

    def __calculate_wind(self):
        """
        Adds two vectors to find the wind speed scalar magnitude
        and convert from m/s to kph
        """
        u_comp_band = 'u_component_of_wind_10m_above_ground'
        v_comp_band = 'v_component_of_wind_10m_above_ground'
        u_comp = self.gfs.select(u_comp_band)
        v_comp = self.gfs.select(v_comp_band)

        wind = ((u_comp ** 2 + v_comp ** 2) ** 0.5) * 3.6
        self.wind = wind.rename('W')

    def __calculate_rain(self):
        """
        Use JAXA GSMaP to get past 24 hours rain in mm
        """
        self.rain = self.gsmap.reduce(ee.Reducer.sum()) \
                        .rename('R')

    def __get_fwi_inputs(self):
        """
        Calculate all the inputs required for FWI Calculation
        """
        # Create noon local standard datetime
        local_noon = datetime(self.date.year, self.date.month, \
            self.date.day, hour = 12, tzinfo = dateutil.tz.gettz( \
            self.timezone))
        utc_datetime = local_noon.astimezone(dateutil.tz.UTC)
        forecast_time = int(utc_datetime.timestamp() * 1000)

        start_datetime = utc_datetime - timedelta(days = 1)

        self.gfs = ee.ImageCollection(f'NOAA/GFS0P25') \
            .filterMetadata('forecast_time', 'equals', forecast_time) \
            .closest(start_datetime.isoformat()).first()

        self.gsmap = ee.ImageCollection('JAXA/GPM_L3/GSMaP/v6/operational') \
            .filterDate(start_datetime.isoformat(), utc_datetime.isoformat()) \
            .select('hourlyPrecipRateGC')

        self.__calculate_temperature()
        self.__calculate_relative_humidity()
        self.__calculate_wind()
        self.__calculate_rain()

    def preprocess(self, interpolation, crs, scale):
        """
        Resample the rasters to a scale

        Parameters
        ----------
        scale: int
            the scale in meters
        Returns
        -------
        None
        """
        self.temp = self.temp.resample(interpolation) \
            .reproject(crs = crs, scale = scale)

        self.rhum = self.rhum.resample(interpolation) \
            .reproject(crs = crs, scale = scale)

        self.wind = self.wind.resample(interpolation) \
            .reproject(crs = crs, scale = scale)

        self.rain = self.rain.resample(interpolation) \
            .reproject(crs = crs, scale = scale)

    def get_fwi_weather_data_input(self):
        """
        Return a single ee.Image for FWI weather data input
        """
        return ee.Image([self.temp, self.rhum, self.wind, self.rain])

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

    def __init__(self, date, timezone, bounds):
        """
        Constructs all the necessary attributes to get the raster data
        observed at a certain datetime inside a boundary

        Attributes
        ----------
        date : datetime.date
            the date for the observation
        bounds : ee.Geometry
            the boundary used to limit the ee.Image file
        """
        self.date = date
        self.bounds = bounds
        self.timezone = timezone
        self.__get_fwi_inputs()

    def __calculate_temperature(self):
        """
        Calculates the ERA5 temperature from Kelvin to Celsius
        """
        temp = self.era5.select('temperature_2m') - 273.15
        self.temp = temp.rename('T')

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

        dew = self.era5.select('dewpoint_temperature_2m') - 273.15

        rhum = 100 * (math.exp(1) ** ((17.625 * dew) / (243.04 + dew)) / \
                    math.exp(1) ** ((17.625 * temp) / (243.04 + temp)))
        self.rhum = rhum.rename('H')

    def __calculate_rain(self):
        """
        Adds total_precipitation from past 24 hours and convert from m to mm
        """
        rain_24h = self.era5_rain.select('total_precipitation') \
                        .reduce(ee.Reducer.sum())

        self.rain = (rain_24h * 1000.0).rename('R')

    def __calculate_wind(self):
        """
        Adds two vectors to find the wind speed scalar magnitude
        and convert from m/s to kph
        """
        u_comp = self.era5.select('u_component_of_wind_10m')
        v_comp = self.era5.select('v_component_of_wind_10m')

        wind = ((u_comp ** 2 + v_comp ** 2) ** 0.5) * 3.6
        self.wind = wind.rename('W')

    def __get_fwi_inputs(self):
        """
        Calculate all the inputs required for FWI Calculation
        """
        # Create noon local standard datetime
        local_noon = datetime(self.date.year, self.date.month, \
            self.date.day, hour = 12, tzinfo = dateutil.tz.gettz( \
            self.timezone))
        utc_datetime = local_noon.astimezone(dateutil.tz.UTC)
        start_datetime = utc_datetime - timedelta(days = 1)

        image_id = f'{utc_datetime.year}' + \
                    f'{str(utc_datetime.month).zfill(2)}' + \
                    f'{str(utc_datetime.day).zfill(2)}T' + \
                    f'{str(utc_datetime.hour).zfill(2)}'

        self.era5_rain = ee.ImageCollection('ECMWF/ERA5_LAND/HOURLY') \
            .filterDate(start_datetime.isoformat(), \
                utc_datetime.isoformat())

        self.era5 = ee.Image(f'ECMWF/ERA5_LAND/HOURLY/{image_id}')

        self.__calculate_temperature()
        self.__calculate_relative_humidity()
        self.__calculate_wind()
        self.__calculate_rain()

    def preprocess(self, interpolation, crs, scale):
        """
        Resample the rasters to a scale

        Parameters
        ----------
        crs: string
            EPSG code in string e.g. 'EPSG:4326'
        scale: int
            the scale in meters
        Returns
        -------
        None
        """
        self.temp = self.temp.resample(interpolation) \
            .reproject(crs = crs, scale = scale)

        self.rhum = self.rhum.resample(interpolation) \
            .reproject(crs = crs, scale = scale)

        self.wind = self.wind.resample(interpolation) \
            .reproject(crs = crs, scale = scale)

        self.rain = self.rain.resample(interpolation) \
            .reproject(crs = crs, scale = scale)

    def get_fwi_weather_data_input(self):
        """
        Return a single ee.Image for FWI weather data input
        """
        return ee.Image([self.temp, self.rhum, self.wind, self.rain])
