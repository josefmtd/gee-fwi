import ee
import eemont

class FWI_ERA5:
    def __init__(self, date_time, bounds):
        self.dataset = ee.ImageCollection('ECMWF/ERA5_LAND/HOURLY') \
                        # .closest(date_time.isoformat()) \
                        # .first()
        self.date_time = date_time
        self.bounds = bounds
        self.get_fwi_inputs()

    def __calculate_temperature(self):
        temp = self.dataset.select('temperature_2m') \
                    .closest(self.date_time.isoformat()) \
                    .first()
                    
    def __calculate_temperature(self):
        self.temp = self.dataset.select('temperature_2m').clip(self.bounds) - \
                    273.15

    def __calculate_relative_humidity(self):
        dew = self.dataset.select('dewpoint_temperature_2m').clip(self.bounds) - \
                273.15
        self.rhum = 100 * (math.exp(1) ** ((17.625 * dew) / (243.04 + dew)) / \
                    math.exp(1) ** ((17.625 * self.temp) / (243.04 + self.temp)))

    def __calculate_rain(self):
        self.rain = self.dataset.select('total_precipitation').clip(self.bounds) * \
                    1000.0

    def __calculate_wind(self):
        u_comp = self.dataset.select('u_component_of_wind_10m').clip(self.bounds)
        v_comp = self.dataset.select('v_component_of_wind_10m').clip(self.bounds)
        self.wind = ((u_comp ** 2 + v_comp ** 2) ** 0.5) * 3.6

    def get_fwi_inputs(self):
        self.__calculate_temperature()
        self.__calculate_relative_humidity()
        self.__calculate_wind()
        self.__calculate_rain()

    def update_fwi_inputs(self, date_time):
        self.dataset = ee.ImageCollection('ECMWF/ERA5_LAND/HOURLY') \
                        .closest(date_time.isoformat()) \
                        .first()
        self.get_fwi_inputs()
