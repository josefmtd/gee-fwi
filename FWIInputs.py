import ee
import eemont
import math
from datetime import datetime, date, timedelta

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

    def __init__(self, date, bounds):
        """
        Constructs all the necessary attributes to get the raster data
        observed at a certain date inside a boundary

        Attributes
        ----------
        date : datetime.date
            the date for observation
        bounds : ee.Geometry
            the boundary used to limit the ee.Image file
        """
        self.date = date
        self.bounds = bounds

        self.__get_fwi_inputs()

    def __calculate_temperature(self):
        """
        Calculates the GFS temperature
        """
        temp_band = 'temperature_2m_above_ground'
        self.temp = self.gfs.select(temp_band) \
            .rename('GFS_T')

    def __calculate_relative_humidity(self):
        """
        Calculates the GFS relative humidity
        """
        rhum_band = 'relative_humidity_2m_above_ground'
        self.rhum = self.gfs.select(rhum_band) \
            .rename('GFS_RH')

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
        self.wind = wind.rename('GFS_W')

    def __calculate_rain_gsmap(self):
        """
        Use JAXA GSMaP to get past 24 hours rain in mm
        """
        self.rain = self.gsmap.reduce(ee.Reducer.sum()) \
                        .rename('GSMAP_R24H')

    def __get_fwi_inputs(self):
        """
        Calculate all the inputs required for FWI Calculation
        """
        # Noon WIB
        utc_datetime = datetime(self.date.year, self.date.month, \
            self.date.day, hour = 5)
        start_datetime = utc_datetime - timedelta(days = 1)

        image_id = f'{self.date.year}' + \
                    f'{str(self.date.month).zfill(2)}' + \
                    f'{str(self.date.day).zfill(2)}00F005'
        self.gfs = ee.Image(f'NOAA/GFS0P25/{image_id}')

        gsmap = 'JAXA/GPM_L3/GSMaP/v6/operational'
        self.gsmap = ee.ImageCollection(gsmap) \
            .filterDate(start_datetime.isoformat(), \
                utc_datetime.isoformat()) \
            .select('hourlyPrecipRateGC')

        self.__calculate_temperature()
        self.__calculate_relative_humidity()
        self.__calculate_wind()
        self.__calculate_rain_gsmap()

    def preprocess(self, crs, scale):
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
        self.temp = self.temp.resample('bicubic') \
            .reproject(crs = crs, scale = scale)

        self.rhum = self.rhum.resample('bicubic') \
            .reproject(crs = crs, scale = scale)

        self.wind = self.wind.resample('bicubic') \
            .reproject(crs = crs, scale = scale)

        self.rain = self.rain.resample('bicubic') \
            .reproject(crs = crs, scale = scale)

    def __export_geotiff(self, image, prefix, bucket):
        """
        Export image as GeoTIFF
        """
        date_string = f'{self.date.year}' + \
            f'_{str(self.date.month).zfill(2)}' + \
            f'_{str(self.date.day).zfill(2)}'
        file_name = f'{prefix}_{date_string}'

        task = ee.batch.Export.image.toCloudStorage(**{
            'image' : image,
            'description' : file_name,
            'bucket' : bucket,
            'region' : self.bounds,
            'fileFormat' : 'GeoTIFF',
            'scale' : 1000,
            'maxPixels' : 10e10
        })

        task.start()
        return task

    def export_inputs(self, bucket):
        """
        Export all inputs as GeoTIFF to a Google Cloud Storage Bucket
        """
        tasks = []

        tasks.append(self.__export_geotiff(self.temp, 'TEMP', bucket))
        tasks.append(self.__export_geotiff(self.rhum, 'RHUM', bucket))
        tasks.append(self.__export_geotiff(self.wind, 'WIND', bucket))
        tasks.append(self.__export_geotiff(self.rain, 'RAIN', bucket))

        return tasks

    def update_fwi_inputs(self, date):
        """
        Updates the value of FWI input variables

        Parameters
        ----------
        date: datetime.date
            next date and time for observation data request
        Returns
        -------
        None
        """
        self.date = date
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

    def __init__(self, date, bounds):
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
        self.__get_fwi_inputs()

    def __calculate_temperature(self):
        """
        Calculates the ERA5 temperature from Kelvin to Celsius
        """
        temp = self.era5.select('temperature_2m') - 273.15
        self.temp = temp.rename('ERA5_T')

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
        self.rhum = rhum.rename('ERA5_RH')

    def __calculate_rain(self):
        """
        Adds total_precipitation from past 24 hours and convert from m to mm
        """
        rain_24h = self.era5_rain.select('total_precipitation') \
                        .reduce(ee.Reducer.sum())

        self.rain = (rain_24h * 1000.0).rename('ERA5_R')

    def __calculate_wind(self):
        """
        Adds two vectors to find the wind speed scalar magnitude
        and convert from m/s to kph
        """
        u_comp = self.era5.select('u_component_of_wind_10m')
        v_comp = self.era5.select('v_component_of_wind_10m')

        wind = ((u_comp ** 2 + v_comp ** 2) ** 0.5) * 3.6
        self.wind = wind.rename('ERA5_W')

    def __get_fwi_inputs(self):
        """
        Calculate all the inputs required for FWI Calculation
        """
        # Noon WIB
        utc_datetime = datetime(self.date.year, self.date.month, \
            self.date.day, hour = 5)
        start_datetime = utc_datetime - timedelta(days = 1)

        image_id = f'{self.date.year}' + \
                    f'{str(self.date.month).zfill(2)}' + \
                    f'{str(self.date.day).zfill(2)}T05'

        self.era5_rain = ee.ImageCollection('ECMWF/ERA5_LAND/HOURLY') \
            .filterDate(start_datetime.isoformat(), \
                utc_datetime.isoformat())

        self.era5 = ee.Image(f'ECMWF/ERA5_LAND/HOURLY/{image_id}')

        self.__calculate_temperature()
        self.__calculate_relative_humidity()
        self.__calculate_wind()
        self.__calculate_rain()

    def update_fwi_inputs(self, date):
        """
        Updates the value of FWI input variables

        Parameters
        ----------
        date : datetime.date
            next date for observation data request
        Returns
        -------
        None
        """
        self.date = date
        self.__get_fwi_inputs()

    def preprocess(self, scale):
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
        self.temp = self.temp.resample('bicubic') \
            .reproject(crs = 'EPSG:4326', scale = scale)

        self.rhum = self.rhum.resample('bicubic') \
            .reproject(crs = 'EPSG:4326', scale = scale)

        self.wind = self.wind.resample('bicubic') \
            .reproject(crs = 'EPSG:4326', scale = scale)

        self.rain = self.rain.resample('bicubic') \
            .reproject(crs = 'EPSG:4326', scale = scale)

    def __export_geotiff(self, image, scale, prefix, suffix, bucket):
        """
        Export image as GeoTIFF
        """
        date_string = f'{self.date.year}' + \
            f'_{str(self.date.month).zfill(2)}' + \
            f'_{str(self.date.day).zfill(2)}'
        file_name = f'{prefix}_{date_string}_{suffix}'

        task = ee.batch.Export.image.toCloudStorage(**{
            'image' : image,
            'description' : file_name,
            'bucket' : bucket,
            'region' : self.bounds,
            'fileFormat' : 'GeoTIFF',
            'scale' : scale,
            'maxPixels' : 10e10
        })

        task.start()
        return task

    def export_inputs(self, scale, prefix, bucket):
        """
        Export all inputs as GeoTIFF to a Google Cloud Storage Bucket
        """
        tasks = []

        tasks.append(self.__export_geotiff(self.temp, scale, prefix, 'T', bucket))
        tasks.append(self.__export_geotiff(self.rhum, scale, prefix, 'H', bucket))
        tasks.append(self.__export_geotiff(self.wind, scale, prefix, 'W', bucket))
        tasks.append(self.__export_geotiff(self.rain, scale, prefix, 'R', bucket))

        return tasks
