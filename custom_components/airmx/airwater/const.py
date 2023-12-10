from enum import IntEnum, IntFlag, StrEnum


class AirWaterFeature(IntFlag):
    HEATER = 1
    ANION = 2
    FAN_SPEED_PERCENTAGE = 4
    FAN_SPEED_STEPS = 8


class AirWaterModel(StrEnum):
    A2 = "AirWater A2"
    A3 = "AirWater A3"
    A3S = "AirWater A3S"
    A3S_V2 = "A3S_V2"
    A5 = "AirWater A5"

    @property
    def human_readable(self) -> str:
        if self == self.A3S_V2:
            return "AirWater A3S_V2 / Tion Iris"

        return self

    @property
    def features(self) -> int:
        features = 0
        if self in [self.A2, self.A5]:
            features |= AirWaterFeature.HEATER

        if self not in [self.A5]:
            features |= AirWaterFeature.ANION

        if self in [self.A5]:
            features |= AirWaterFeature.FAN_SPEED_STEPS
        else:
            features |= AirWaterFeature.FAN_SPEED_PERCENTAGE

        return features


class AirWaterCommand(IntEnum):
    CONTROL = 1000
    STATUS_INFO = 1001
    SET = 1002
    SET_INFO = 1003
    GET_STATUS = 1008
    STERILIZATION = 1011
    STERILIZATION_INFO = 1012


class AirWaterMode(IntEnum):
    MANUAL = 0
    AUTO = 1
    SLEEP = 2
    MALFUNCTION = 5


class WaterType(IntEnum):
    FILTERED = 1
    TAP = 2

    @property
    def cleaning_time(self) -> int:
        if self == self.FILTERED:
            return 300

        return 150
