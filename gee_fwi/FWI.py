import ee
import eemont

class FineFuelMoistureCode:
    """
    Fine Fuel Moisture Code Calculation

    Attributes
    ----------
    inputs : FWIInputs
        daily observed weather inputs at noon
    ffmc_prev : ee.Image
        yesterday's fine fuel moisture code
    """
    def __init__(self, inputs, ffmc_prev):
        """
        Initializes the FFMC calculation object

        Attributes
        ----------
        inputs : FWIInputs
            daily observed weather inputs at noon
        ffmc_prev : ee.Image
            yesterday's fine fuel moisture code
        """
        self.ffmc_prev = ee.Image(ffmc_prev)
        self.temp = inputs.temp
        self.rhum = inputs.rhum
        self.wind = inputs.wind
        self.rain = inputs.rain

    def __raining_phase(self):
        # Convert FFMC to moisture content
        m_o = 147.2 * (101.0 - self.ffmc_prev) / \
            (59.5 + self.ffmc_prev)

        # Calculate effective rain
        rain_mask = self.rain.gt(0.5)
        negligible = rain_mask.Not()
        r_f = rain_mask * (self.rain - 0.5)

        # Calculate moisture change
        comp_mask = m_o.gt(150.0)
        normal = comp_mask.Not()

        delta_m_rain = 42.5 * (-100.0 / (251 - m_o)).exp() * \
            (1 - (-6.93 / r_f).exp()) * r_f
        corrective = 0.0015 * (m_o - 150.0) ** 2 * r_f ** 0.5

        delta_m_c = delta_m_rain + corrective
        delta_m_r = delta_m_rain
        delta_m_n = 0.0 * negligible
        delta_m = rain_mask * ( comp_mask * delta_m_c + \
            normal * delta_m_r) + delta_m_n

        # Moisture content after rain
        self.mo = (m_o + delta_m).min(ee.Image(250.0))

    def __drying_phase(self):
        # Equilibrium moisture content for drying and wetting phase
        E_d = 0.942 * self.rhum ** 0.679 + \
            11.0 * ((self.rhum - 100) / 10).exp() + \
            0.18 * (21.1 - self.temp) * \
            (1 - (-0.115 * self.rhum).exp())

        E_w = 0.618 * self.rhum ** 0.753 + \
            10.0 * ((self.rhum - 100) / 10).exp() + \
            0.18 * (21.1 - self.temp) * \
            (1 - (-0.115 * self.rhum).exp())

        # Calculate the log drying/wetting rate
        k_1 = 0.424 * (1 - ((100 - self.rhum) / 100) ** 1.7) + \
            0.0694 * self.wind ** 0.5 * \
            (1 - ((100 - self.rhum) / 100) ** 8)
        k_0 = 0.424 * (1 - (self.rhum / 100) ** 1.7) + \
            0.0694 * self.wind ** 0.5 * \
            (1 - (self.rhum / 100) ** 8)
        k_d = k_0 * 0.581 * (0.0365 * self.temp).exp()
        k_w = k_1 * 0.581 * (0.0365 * self.temp).exp()

        # Wetting and drying conditions
        drying = self.mo.gt(E_d)
        wetting = self.mo.lt(E_w)
        no_change = (drying + wetting).Not()

        # Moisture content after drying
        m_drying = drying * (E_d + (self.mo - E_d) / 10 ** k_d)
        m_wetting = wetting * (E_w - (E_w - self.mo) / 10 ** k_w)
        m_no_change = no_change * self.mo
        m = m_drying + m_wetting + m_no_change

        # Calculate today's Fine Fuel Moisture Code
        self.ffmc = (59.5 * (250.0 - m) / (147.2 + m)) \
            .min(ee.Image(101.0)).rename( \
            'fine_fuel_moisture_code')

    def compute(self):
        """
        Computes the Fine Fuel Moisture Code

        Returns
        -------
        ffmc : ee.Image
            today's fine fuel moisture code
        """
        self.__raining_phase()
        self.__drying_phase()
        return self.ffmc

class DuffMoistureCode:
    """
    Duff Moisture Code Calculation

    Attributes
    ----------
    inputs : FWIInputs
        daily observed weather inputs at noon
    dmc_prev : ee.Image
        yesterday's duff moisture code
    equatorial : bool
        use equatorial mode to calculate day length
    obs : datetime.date
        observed date
    """
    def __init__(self, inputs, dmc_prev, equatorial, obs):
        """
        Initializes the DMC calculation object

        Attributes
        ----------
        inputs : FWIInputs
            daily observed weather inputs at noon
        dmc_prev : ee.Image
            yesterday's duff moisture code
        equatorial : bool
            use equatorial mode to calculate day length
        obs : datetime.date
            observed date
        """
        self.dmc_prev = ee.Image(dmc_prev)
        self.temp = inputs.temp
        self.rhum = inputs.rhum
        self.rain = inputs.rain
        self.equatorial = equatorial
        self.obs = obs

    def __get_day_length(self):
        if self.equatorial:
            self.day_length = ee.Image(9.0)
        else:
            self.__calculate_day_length()

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

        index = self.obs.month - 1
        length_1 = mask_1 * ee.Image(DayLength46N[index])
        length_2 = mask_2 * ee.Image(DayLength20N[index])
        length_3 = mask_3 * ee.Image(DayLength20S[index])
        length_4 = mask_4 * ee.Image(DayLength40S[index])
        self.day_length = length_1 + length_2 + length_3 + length_4

    def __raining_phase(self):
        # Convert DMC to moisture content
        M_o = 20.0 + 280.0 / (0.023 * self.dmc_prev).exp()

        # Calculate effective rain
        rain_mask = self.rain.gt(1.5)
        negligible = rain_mask.Not()
        r_e = 0.92 * self.rain - 1.27

        # Piecewise equation
        pw_1 = self.dmc_prev.lte(33.0)
        pw_2 = self.dmc_prev.lte(65.0) * self.dmc_prev.gt(33.0)
        pw_3 = self.dmc_prev.gt(65.0)
        b_1 = (100.0 / (0.5 + 0.3 * self.dmc_prev)) \
            * rain_mask * pw_1
        b_2 = (14.0 - 1.3 * self.dmc_prev.log()) \
            * rain_mask * pw_2
        b_3 = (6.2 * self.dmc_prev.log() - 17.2) \
            * rain_mask * pw_3
        b = b_1 + b_2 + b_3

        # Calculates the moisture change after rain
        M_r = (M_o + 1000.0 * r_e / (48.77 + b * r_e))

        # Calculate DMC after rain
        P_r = rain_mask * (244.72 - 43.43 * (M_r - 20.0).log())
        P_r = P_r.max(0.0)
        P_n = negligible * self.dmc_prev
        self.P_prev = P_r + P_n

    def __drying_phase(self):
        log_drying_rate = self.temp.gt(-1.1)
        negligible = log_drying_rate.Not()

        self.__get_day_length()

        # Calculates the log drying rate
        k_d = log_drying_rate * 1.894 * (self.temp + 1.1) \
            * (100.0 - self.rhum) * self.day_length * 1e-6
        k_n = negligible * 0.0
        K = k_d + k_n

        # Calculates today's Duff Moisture Code
        self.dmc = (self.P_prev + 100.0 * K).rename(\
            'duff_moisture_code')

    def compute(self):
        """
        Computes the Duff Moisture Code

        Returns
        -------
        dmc : ee.Image
            today's duff moisture code
        """
        self.__raining_phase()
        self.__drying_phase()
        return self.dmc

class DroughtCode:
    """
    Drought Code Calculation

    Attributes
    ----------
    inputs : FWIInputs
        daily observed weather inputs at noon
    dc_prev : ee.Image
        yesterday's drought code
    equatorial : bool
        use equatorial mode to calculate drying factor
    obs : datetime.date
        observed date
    """
    def __init__(self, inputs, dc_prev, equatorial, obs):
        """
        Initializes the DC calculation object

        Attributes
        ----------
        inputs : FWIInputs
            daily observed weather inputs at noon
        dmc_prev : ee.Image
            yesterday's drought code
        equatorial : bool
            use equatorial mode to calculate drying factor
        obs : datetime.date
            observed date
        """
        self.dc_prev = ee.Image(dc_prev)
        self.temp = inputs.temp
        self.rain = inputs.rain
        self.equatorial = equatorial
        self.obs = obs

    def __get_drying_factor(self):
        if self.equatorial:
            self.drying_factor = ee.Image(1.39)
        else:
            self.__calculate_drying_factor()

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

        factor_1 = mask_1 * ee.Image(LfN[self.obs.month - 1])
        factor_2 = mask_2 * ee.Image(LfS[self.obs.month - 1])

        self.drying_factor = factor_1 + factor_2

    def __raining_phase(self):
        # Converts DC to moisture content
        Q_o = (800.0 * (-1 * self.dc_prev / 400.0).exp())

        # Calculate effective rain
        rain_mask = self.rain.gt(2.8)
        negligible = rain_mask.Not()
        r_d = rain_mask * (0.83 * self.rain - 1.27)

        # Calculates moisture change
        Q_r = Q_o + 3.937 * r_d

        # Calculates DC after rain
        D_rain = rain_mask * (400.0 * (800.0 / Q_r).log())
        D_rain = D_rain.max(0.0)
        D_negligible = negligible * self.dc_prev
        self.D_prev = D_rain + D_negligible

    def __drying_phase(self):
        drying_phase = self.temp.gt(-2.8)
        negligible = drying_phase.Not()

        self.__get_drying_factor()

        # Calculates drying equation
        V_d = (0.36 * (self.temp + 2.8) + self.drying_factor) \
            * drying_phase
        V_n = self.drying_factor * negligible
        V = V_d + V_n

        # Calculate today's Drought Code
        self.dc = (self.D_prev + 0.5 * V).rename(\
            'drought_code')

    def compute(self):
        """
        Computes the Drought Code

        Returns
        -------
        dc : ee.Image
            today's drought code
        """
        self.__raining_phase()
        self.__drying_phase()
        return self.dc

class InitialSpreadIndex:
    """
    Initial Spread Index Calculation

    Attributes
    ----------
    wind : FWIInputs.wind
        wind speed observed at noon in kph
    ffmc : FineFuelMoistureCode.ffmc
        today's fine fuel moisture code
    """
    def __init__(self, wind, ffmc):
        """
        Initializes the ISI calculation object

        Attributes
        ----------
        wind : FWIInputs.wind
            wind speed observed at noon in kph
        ffmc : FineFuelMoistureCode.ffmc
            today's fine fuel moisture code
        """
        self.wind = wind
        self.ffmc = ffmc

    def compute(self):
        """
        Computes the Initial Spread Index

        Returns
        -------
        isi : ee.Image
            today's initial spread index
        """
        f_Wind = (0.05039 * self.wind).exp()

        m = 147.2 * (101.0 - self.ffmc) / (59.5 + self.ffmc)
        f_F = 91.9 * (-0.1386 * m).exp() * (1.0 + m ** 5.31 / \
            (4.93 * 1e7))

        self.isi = (0.208 * f_Wind * f_F) \
            .rename('initial_spread_index')
        return self.isi

class BuildupIndex:
    """
    Buildup Index Calculation

    Attributes
    ----------
    dmc : ee.Image
        today's duff moisture code
    dc : ee.Image
        today's drought code
    """
    def __init__(self, dmc, dc):
        """
        Initializes BUI calculation object

        Attributes
        ----------
        dmc : ee.Image
            today's duff moisture code
        dc : ee.Image
            today's drought code
        """
        self.dmc = dmc
        self.dc=  dc

    def compute(self):
        """
        Computes the Buildup Index

        Returns
        -------
        bui : ee.Image
            today's buildup index
        isi : ee.Image
            today's initial spread index
        """
        cond = self.dmc.lte(0.4 * self.dc)
        not_cond = cond.Not()

        B_1 = (0.8 * self.dmc * self.dc / \
            (self.dmc + 0.4 * self.dc)) * cond
        B_2 = (self.dmc - (1.0 - 0.8 * self.dc / \
            (self.dmc + 0.4 * self.dc)) * \
            (0.92 + (0.0114 * self.dmc) ** 1.7)) * not_cond

        self.bui = (B_1 + B_2).rename('buildup_index')
        return self.bui

class FireWeatherIndex:
    """
    Fire Weather Index Calculation

    Attributes
    ----------
    isi : ee.Image
        today's initial spread index
    bui : ee.Image
        today's buildup index
    """
    def __init__(self, isi, bui):
        """
        Initializes FWI calculation object

        Attributes
        ----------
        isi : ee.Image
            today's initial spread index
        bui : ee.Image
            today's buildup index
        """
        self.isi = isi
        self.bui = bui

    def __heat_transfer(self):
        return 1000.0 / (25.0 + 108.64 * (-0.023 * self.bui).exp())

    def __normal(self):
        return 0.626 * self.bui ** 0.809 + 2.0

    def compute(self):
        """
        Computes the Fire Weather Index

        Returns
        -------
        fwi : ee.Image
            today's fire weather index
        """
        heat_transfer = self.bui.gt(80)
        normal = heat_transfer.Not()

        fD_n = normal * self.__normal()
        fD_h = heat_transfer * self.__heat_transfer()
        fD = fD_n + fD_h

        B = 0.1 * self.isi * fD

        S_scale = B.gt(1.0)
        B_scale = S_scale.Not()

        fwi_s = ((2.72 * (0.434 * B.log()) ** 0.647).exp()) * S_scale
        fwi_b = B * B_scale
        self.fwi = (fwi_s + fwi_b).rename('fire_weather_index')
        return self.fwi

class FWICalculator:
    """
    FWI Calculator based on the Canadian Fire Weather Index System
    using Google Earth Engine
    ...

    Attributes
    ----------
    obs: datetime.date
        the observation date
    inputs : FWIInputs
        daily observed weather inputs at noon
    """

    def __init__(self, obs, inputs):
        """
        Constructs all the necessary attributes for the
        FWICalculator object.

        Parameters
        ----------
        date : datetime.date
            the observation date
        temp : ee.Image
            temperature in degree Celsius observed at noon
        rhum : ee.Image
            relative humidity in percent observed at noon
        wind : ee.Image
            wind speed in kph observed at noon
        rain : ee.Image
            total precipitation past 24 hours in mm observed at noon
        """
        self.obs = obs
        self.inputs = inputs
        self.equatorial = True

    def set_initial_codes(self, ffmc_prev, dmc_prev, dc_prev):
        """
        Sets the initial value for Fine Fuel Moisture Code,
        Duff Moisture Code, and Drought Code
        Parameters
        ----------
        ffmc_prev : ee.Image or float
            the initial value for FFMC
        dmc_prev : ee.Image or float
            the initial value for FFMC
        dc_prev : ee.Image or float
            the initial value for FFMC
        Returns
        -------
        None
        """
        self.ffmc_prev = ee.Image(ffmc_prev)
        self.dmc_prev = ee.Image(dmc_prev)
        self.dc_prev = ee.Image(dc_prev)

    def set_equatorial_mode(self, equatorial):
        """
        Sets the equatorial mode to use drying factor
        and day length constant

        Parameters
        ----------
        equatorial : bool
            enable equatorial mode
        Returns
        -------
        None
        """
        self.equatorial = equatorial

    def calculate_fine_fuel_moisture_code(self):
        ffmc = FineFuelMoistureCode(self.inputs, self.ffmc_prev)
        self.ffmc = ffmc.compute()

    def calculate_duff_moisture_code(self):
        dmc = DuffMoistureCode(self.inputs,
            self.dmc_prev, self.equatorial, self.obs)
        self.dmc = dmc.compute()

    def calculate_drought_code(self):
        dc = DroughtCode(self.inputs, self.dc_prev,
            self.equatorial, self.obs)
        self.dc = dc.compute()

    def calculate_initial_spread_index(self):
        isi = InitialSpreadIndex(self.inputs.wind, self.ffmc)
        self.isi = isi.compute()

    def calculate_buildup_index(self):
        bui = BuildupIndex(self.dmc, self.dc)
        self.bui = bui.compute()

    def calculate_fire_weather_index(self):
        fwi = FireWeatherIndex(self.isi, self.bui)
        self.fwi = fwi.compute()

    def compute(self):
        """
        Calculates all the Fire Weather Indices

        Returns
        -------
        fwi : ee.Image
            Observed date's Fire Weather Index
        """
        self.calculate_fine_fuel_moisture_code()
        self.calculate_duff_moisture_code()
        self.calculate_drought_code()
        self.calculate_initial_spread_index()
        self.calculate_buildup_index()
        self.calculate_fire_weather_index()
        return self.fwi

    def update_daily_parameters(self, obs, inputs):
        """
        Updates the daily parameters required to calculate FWI

        Parameters
        ----------
        obs : datetime.date
            Next observed date
        inputs : FWIInputs
            daily observed weather inputs at noon
        """
        self.ffmc_prev = self.ffmc
        self.dmc_prev = self.dmc
        self.dc_prev = self.dc
        self.date_prev = self.date

        self.obs = obs
        self.inputs = inputs
