# -*- coding: utf-8 -*-

import ee
import math
import eemont

class FWICalculator:
    """
    FWI Calculator based on the Canadian Fire Weather Index System
    using Google Earth Engine

    ...

    Attributes
    ----------
    temp : ee.Image
        temperature in degree Celsius observed at noon
    rhum : ee.Image
        relative humidity in percent observed at noon
    wind : ee.Image
        wind speed in kph observed at noon
    rain : ee.Image
        total precipitation from past 24 hours in mm observed at noon
    """

    def __init__(self, date, temp, rhum, wind, rain):
        """
        Constructs all the necessary attributes for the
        FWICalculator object.

        Parameters
        ----------
        date_time : datetime.date
            the current date of observation
        temp : ee.Image
            temperature in degree Celsius observed at noon
        rhum : ee.Image
            relative humidity in percent observed at noon
        wind : ee.Image
            wind speed in kph observed at noon
        rain : ee.Image
            total precipitation past 24 hours in mm observed at noon
        """
        self.date = date
        self.temp = temp
        self.rhum = rhum
        self.wind = wind
        self.rain = rain

    def set_boundary(self, bounds):
        """
        Adds a boundary from a Geometry object

        Parameters
        ----------
        bounds : ee.Geometry
            polygon boundary defined by an ee.Geometry
        Returns
        -------
        None
        """
        self.bounds = bounds

    def set_initial_ffmc(self, ffmc_prev):
        """
        Sets the initial value for Fine Fuel Moisture Code

        Parameters
        ----------
        ffmc : ee.Image
            the initial value for FFMC
        Returns
        -------
        None
        """
        self.ffmc_prev = ee.Image(ffmc_prev)

    def set_initial_dmc(self, dmc_prev):
        """
        Sets the initial value for Duff Moisture Code

        Parameters
        ----------
        dmc : ee.Image
            the initial value for DMC
        Returns
        -------
        None
        """
        self.dmc_prev = ee.Image(dmc_prev)

    def set_initial_dc(self, dc_prev):
        """
        Sets the initial value for Drought Code

        Parameters
        ----------
        dc : ee.Image
            the initial value for DC
        Returns
        -------
        None
        """
        self.dc_prev = ee.Image(dc_prev)

    def __update_drying_factor(self):
        """
        Updates the drying factor if the month is changed
        """
        try:
            cal = (self.date- self.date_prev).month > 0
        except AttributeError:
            cal = 1

        if cal == 1:
            self.__calculate_drying_factor()

    def __update_day_length(self):
        """
        Updates the day length if the month is changed
        """
        try:
            cal = (self.date - self.date_prev).month > 0
        except AttributeError:
            cal = 1

        if cal == 1:
            self.__calculate_day_length()

    def __calculate_drying_factor(self):
        '''
        Calculates an ee.Image containing the drying factor
        with bounds and date
        '''

        latitude = ee.Image.pixelLonLat() \
                    .select('latitude')

        LfN = [-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, \
               6.4, 5.0, 2.4, 0.4, -1.6, -1.6]
        LfS = [6.4, 5.0, 2.4, 0.4, -1.6, -1.6, \
               -1.6, -1.6, -1.6, 0.9, 3.8, 5.8]

        mask_1 = latitude.gt(0)
        mask_2 = latitude.lte(0)

        factor_1 = mask_1 * ee.Image(LfN[self.date.month - 1])
        factor_2 = mask_2 * ee.Image(LfS[self.date.month - 1])

        self.drying_factor = factor_1 + factor_2

    def __calculate_day_length(self):
        '''
        Calculates an ee.Image containing an approximation
        of the day length with bounds and date
        '''
        DayLength46N = [ 6.5,  7.5,  9.0, 12.8, 13.9, 13.9, \
                        12.4, 10.9,  9.4,  8.0,  7.0,  6.0]
        DayLength20N = [ 7.9,  8.4,  8.9,  9.5,  9.9, 10.2, \
                        10.1,  9.7,  9.1,  8.6,  8.1,  7.8]
        DayLength20S = [10.1,  9.6,  9.1,  8.5,  8.1,  7.8, \
                        7.9,  8.3,  8.9,  9.4,  9.9, 10.2]
        DayLength40S = [11.5, 10.5,  9.2,  7.9,  6.8,  6.2, \
                        6.5,  7.4,  8.7, 10.0, 11.2, 11.8]

        latitude = ee.Image.pixelLonLat() \
                    .select('latitude')

        mask_1 = latitude.lte(90.0) * latitude.gt(33.0)
        mask_2 = latitude.lte(33.0) * latitude.gt(0)
        mask_3 = latitude.lte(0) * latitude.gt(-30.0)
        mask_4 = latitude.lte(-30.0) * latitude.gt(-90.0)

        index = self.date.month - 1
        length_1 = mask_1 * ee.Image(DayLength46N[index])
        length_2 = mask_2 * ee.Image(DayLength20N[index])
        length_3 = mask_3 * ee.Image(DayLength20S[index])
        length_4 = mask_4 * ee.Image(DayLength40S[index])
        self.day_length = length_1 + length_2 + length_3 + length_4

    def calculate_fine_fuel_moisture_code(self):
        """
        Calculates the Fine Fuel Moisture Code
        """
        # Get the moisture content from previous day (m_o)
        m_o = 147.2 * (101.0 - self.ffmc_prev) / \
            (59.5 + self.ffmc_prev)

        # Raining Phase
        rain = self.rain.gt(0.5)
        negligible_rain = rain.Not()

        r_f = rain * (self.rain - 0.5)

        comp = rain * m_o.gt(150.0)
        normal = rain * comp.Not()

        # The effect of rain to moisture content
        delta_m_rf = 42.5 * math.exp(1) ** (-100.0 / (251 - m_o)) * \
            (1 - math.exp(1) ** (-6.93 / r_f))
        corrective = 0.0015 * (m_o - 150.0) ** 2 * r_f ** 0.5

        delta_m = comp * (delta_m_rf * r_f  + corrective) + \
                    normal * (delta_m_rf * r_f) + \
                    negligible_rain * 0.0

        # Moisture content after raining phase
        mo = m_o + delta_m
        mo = mo.min(ee.Image(250.0))

        # Drying / Wetting Phase
        E_d = 0.942 * self.rhum ** 0.679 + \
            11.0 * math.exp(1) ** ((self.rhum - 100) / 10) + \
            0.18 * (21.1 - self.temp) * \
            (1 - math.exp(1) ** (-0.115 * self.rhum))

        E_w = 0.618 * self.rhum ** 0.753 + \
            10.0 * math.exp(1) ** ((self.rhum - 100) / 10) + \
            0.18 * (21.1 - self.temp) * \
            (1 - math.exp(1) ** (-0.115 * self.rhum))

        k_1 = 0.424 * (1 - ((100 - self.rhum) / 100) ** 1.7) + \
            0.0694 * self.wind ** 0.5 * \
            (1 - ((100 - self.rhum)/100) ** 8)

        k_o = 0.424 * (1 - ((100 - self.rhum) / 100) ** 1.7) + \
            0.0694 * self.wind ** 0.5 * (1 - (self.rhum / 100) ** 8)

        # Wetting and drying rate
        k_d = k_o * 0.581 * math.exp(1) ** (0.0365 * self.temp)
        k_w = k_1 * 0.581 * math.exp(1) ** (0.0365 * self.temp)

        # Calculate the drying/wetting phase based on moisture content
        drying = mo.gt(E_d)
        wetting = mo.lt(E_w)
        no_change = (drying + wetting).Not()

        m_drying = drying * (E_d + (mo - E_d) / 10 ** k_d)
        m_wetting = wetting * (E_w - (E_w - mo) / 10 ** k_w)
        m_no_change = no_change * mo

        m = m_drying + m_wetting + m_no_change
        self.ffmc = 59.5 * (250.0 - m) / (147.2 + m)

    def calculate_duff_moisture_code(self):
        """
        Calculates the Duff Moisture Code
        """
        M_o = 20.0 + 280.0 / (math.exp(1) ** (0.023 * self.dmc_prev))

        # Raining phase
        rain = self.rain.gt(1.5)
        negligible_rain = rain.Not()

        r_e = rain * 0.92 * self.rain - 1.27

        piece_wise_1 = self.dmc_prev.lte(33.0)
        piece_wise_2 = self.dmc_prev.lte(65.0) * \
            self.dmc_prev.gt(33.0)
        piece_wise_3 = self.dmc_prev.gt(65.0)

        b_1 = 100.0 / (0.5 + 0.3 * self.dmc_prev)
        b_2 = 14.0 - 1.3 * self.dmc_prev.log()
        b_3 = 6.2 * self.dmc_prev.log() - 17.2

        b = piece_wise_1 * b_1 + \
            piece_wise_2 * b_2 + \
            piece_wise_3 * b_3

        # Calculating the effect of rain to Duff Moisture Content
        M_r = rain * M_o + 1000 * r_e / (48.77 + b * r_e)

        # Workaround to prevent None
        M_r_abs = (M_r - 20.0).abs()

        P_rain = rain * (244.72 - 43.43 * (M_r_abs).log())
        P_rain = P_rain.max(0.0)
        P_negligible_rain = negligible_rain * self.dmc_prev

        P_prev = P_rain + P_negligible_rain

        # Drying phase
        log_drying_rate = self.temp.gt(-1.1)
        negligible = log_drying_rate.Not()

        self.__update_day_length()

        K = log_drying_rate * 1.894 * (self.temp + 1.1) \
            * (100.0 - self.rhum) * self.day_length * 1e-6 \
            + negligible * 0.0

        self.dmc = P_prev + 100.0 * K

    def calculate_drought_code(self):
        """
        Calculates the Drought Code
        """
        Q_o = (800.0 * math.exp(1) ** (-1 * self.dc_prev / 400.0))

        # Raining phase
        rain = self.rain.gt(2.8)
        negligible_rain = rain.Not()

        r_d = (0.83 * self.rain - 1.27)
        Q_r = Q_o + 3.937 * r_d

        D_rain = rain * (400.0 * (800.0 / Q_r).log())
        D_rain = D_rain.max(0.0)
        D_negligible_rain = negligible_rain * self.dc_prev

        D_prev = D_rain + D_negligible_rain

        # Drying phase
        drying_phase = self.temp.gt(-2.8)
        negligible = drying_phase.Not()

        self.__update_drying_factor()

        V = drying_phase * (0.36 * (self.temp + 2.8) + \
            self.drying_factor) + negligible_rain * self.drying_factor

        self.dc = D_prev + 0.5 * V

    def calculate_initial_spread_index(self):
        """
        Calculates the Initial Spread Index
        """
        f_Wind = math.exp(1) ** (0.05039 * self.wind)

        # Get moisture content from FFMC
        try:
            m = 147.2 * (101.0 - self.ffmc) / (59.5 + self.ffmc)
        except AttributeError:
            self.calculate_fine_fuel_moisture_code()
            m = 147.2 * (101.0 - self.ffmc) / (59.5 + self.ffmc)

        f_F = 91.9 * math.exp(1) ** (-0.1386 * m) * \
                (1.0 + m ** 5.31 / (4.93 * 1e7))
        self.isi = 0.208 * f_Wind * f_F

    def calculate_buildup_index(self):
        """
        Calculates the Buildup Index
        """
        try:
            cond = self.dmc.lte(0.4 * self.dc)
        except AttributeError:
            self.calculate_duff_moisture_code()
            self.calculate_drought_code()
            cond = self.dmc.lte(0.4 * self.dc)
        finally:
            not_cond = cond.Not()

        self.bui = cond * (0.8 * self.dmc * self.dc / \
            (self.dmc + 0.4 * self.dc)) + not_cond * (self.dmc - \
            (1.0 - 0.8 * self.dc / (self.dmc + 0.4 * self.dc)) * \
            (0.92 + (0.0114 * self.dmc) ** 1.7))

    def calculate_fire_weather_index(self):
        """
        Calculates the Fire Weather Index
        """

        try:
            heat_transfer = self.bui.gt(80)
        except AttributeError:
            self.calculate_buildup_index()
            heat_transfer = self.bui.gt(80)
        finally:
            original = heat_transfer.Not()

        # Use the heat transfer for BUI value above 80, else use normal function
        fD = original * (0.626 * self.bui ** 0.809 + 2.0) + \
                heat_transfer * (1000.0 / (25.0 + 108.64 * \
                math.exp(1) ** (-0.023 * self.bui)))

        try:
            B = 0.1 * self.isi * fD
        except AttributeError:
            self.calculate_initial_spread_index()
            B = 0.1 * self.isi * fD

        # Use S-scale for FWI for B > 1, if not use B-scale FWI
        use_log = B > 1.0
        dn_use_log = use_log.Not()

        B_log = use_log * B.log()
        S = math.exp(1) ** (2.72 * 0.434 * B_log) ** 0.647

        self.fwi = dn_use_log * B + use_log * S

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
        self.ffmc = self.ffmc.resample('bicubic') \
            .reproject(crs = 'EPSG:4326', scale = scale) \
            .rename('FFMC')

        self.dmc = self.dmc.resample('bicubic') \
            .reproject(crs = 'EPSG:4326', scale = scale) \
            .rename('DMC')

        self.dc = self.dc.resample('bicubic') \
            .reproject(crs = 'EPSG:4326', scale = scale) \
            .rename('DC')

        self.isi = self.isi.resample('bicubic') \
            .reproject(crs = 'EPSG:4326', scale = scale) \
            .rename('ISI')

        self.bui = self.bui.resample('bicubic') \
            .reproject(crs = 'EPSG:4326', scale = scale) \
            .rename('BUI')

        self.fwi = self.fwi.resample('bicubic') \
            .reproject(crs = 'EPSG:4326', scale = scale) \
            .rename('FWI')

    def __export_geotiff(self, image, prefix, bucket):
        """
        Export an image as GeoTIFF

        Parameters
        ----------
        image : ee.Image
            Image to be exported
        prefix : str
            Prefix for file_name

        Returns
        -------
        task : ee.batch.Export.task
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

    def export_codes(self, bucket):
        """
        Export all codes and indices calculated
        """
        tasks = []

        tasks.append(self.__export_geotiff(self.ffmc, 'FFMC', bucket))
        tasks.append(self.__export_geotiff(self.dmc, 'DMC', bucket))
        tasks.append(self.__export_geotiff(self.dc, 'DC', bucket))
        tasks.append(self.__export_geotiff(self.isi, 'ISI', bucket))
        tasks.append(self.__export_geotiff(self.bui, 'BUI', bucket))
        tasks.append(self.__export_geotiff(self.fwi, 'FWI', bucket))

        return tasks

    def update_daily_parameters(self, date, temp, rhum, wind, rain):
        """
        Updates the daily parameters required to calculate FWI

        Parameters
        ----------
        date : datetime.date
            the current date of observation
        temp : ee.Image
            temperature in degree Celsius observed at noon
        rhum : ee.Image
            relative humidity in percent observed at noon
        wind : ee.Image
            wind speed in kph observed at noon
        rain : ee.Image
            total precipitation past 24 hours in mm observed at noon
        """
        self.ffmc_prev = self.ffmc
        self.dmc_prev = self.dmc
        self.dc_prev = self.dc
        self.date_prev = self.date

        self.date = date
        self.temp = temp
        self.rhum = rhum
        self.wind = wind
        self.rain = rain

        delattr(self, 'ffmc')
        delattr(self, 'dmc')
        delattr(self, 'dc')
        delattr(self, 'isi')
        delattr(self, 'bui')
        delattr(self, 'fwi')
