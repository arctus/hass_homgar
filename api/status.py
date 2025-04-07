from enum import IntEnum
from datetime import datetime
import struct
from typing import List, Optional

class DpStatusCode(IntEnum):
    CHG = 0
    RAIN = 1
    ALARM = 2
    CHECK = 3
    RM_TIME = 8
    TEM = 9
    RH = 10
    PH = 11
    ATMOS = 12
    TOTAL_RAIN = 13
    V_FLOW = 14
    LAST_USAGE = 15
    CURRENT = 16
    POWER = 17
    ENERGY = 18
    DURATION = 19
    WATER_TOTAL = 20
    EVENT_TIME = 21
    TREND = 22
    SENSOR_F = 23
    V_WIND = 24
    ILLUMINANCE = 25
    TOTAL_TODAY = 26
    CO2 = 27
    PM25 = 28
    VOLTAGE = 29
    WK_STATE = 30
    BAT = 31
    RSSI = 32
    MAX_TEM = 33
    MAX_RH = 34
    MAX_STATE_MOS = 35
    MAX_WIND = 36
    WATER_ZONES = 37
    TS_DET = 38
    STA_VALVE = 39
    STA_JOB = 40
    STA_CALL = 41
    STA_WATER_PS = 42
    HOUR_RAIN = 43
    DAY_RAIN = 44
    WEEK_RAIN = 45
    STA_CUR_FLOW = 46
    MAX_CO2 = 47
    MAX_PM25 = 48
    STA_LAST_DURATION = 49
    STA_OTHER_TOTAL = 50
    STA_RSSI2 = 51

class RecDeviceDpModel:
    def __init__(self, dp_code, dp_id, dp_port, dp_type):
        self.dp_code = dp_code
        self.dp_id = dp_id
        self.dp_port = dp_port
        self.dp_type = dp_type
    
    def __eq__(self, other):
        if self is other:
            return True
        if not isinstance(other, RecDeviceDpModel):
            return False
        return (self.dp_code == other.dp_code and 
                self.dp_id == other.dp_id and 
                self.dp_port == other.dp_port and 
                self.dp_type == other.dp_type)
    
    def __hash__(self):
        return hash((self.dp_code, self.dp_id, self.dp_port, self.dp_type))

class T4Date:

    @staticmethod
    def get_t4_date_by_param(timestamp):
        t4_date = T4Date()
        t4_date.second = int(timestamp & 0x3F)
        t4_date.minute = int((timestamp >> 6) & 0x3F)
        t4_date.hour = int((timestamp >> 12) & 0x1F)
        t4_date.date = int((timestamp >> 17) & 0x1F)
        t4_date.month = int((timestamp >> 22) & 0xF)
        t4_date.year = int((timestamp >> 26) & 0x3F) + 2020
        return t4_date
    
    def __init__(self, second=0, minute=0, hour=0, date=0, month=0, year=2020):
        self.second = second
        self.minute = minute
        self.hour = hour
        self.date = date
        self.month = month
        self.year = year
    
    def __str__(self):
        return f"{self.year:04d}-{self.month:02d}-{self.date:02d} {self.hour:02d}:{self.minute:02d}:{self.second:02d}"
    
    def __lt__(self, other):
        return str(self) < str(other)
    
    def __eq__(self, other):
        if self is other:
            return True
        if not isinstance(other, T4Date):
            return False
        return (self.second == other.second and
                self.minute == other.minute and
                self.hour == other.hour and
                self.date == other.date and
                self.month == other.month and
                self.year == other.year)
    
    def __hash__(self):
        return (self.second * 31 + 
                self.minute) * 31 + self.hour * 31 + self.date * 31 + self.month * 31 + self.year
    
    def get_timestamp(self):
        dt = datetime(self.year, self.month, self.date, 
                     self.hour, self.minute, self.second)
        return int(dt.timestamp() * 1000)
    
    def get_date_timestamp(self):
        dt = datetime(self.year, self.month, self.date)
        return int(dt.timestamp() * 1000)
    
class DpDeviceStatus:
    
    def __init__(self, dp_id=0, type_code=-1, type_len=0, type_value=None):
        self.dp_id = dp_id
        self.type_code = type_code
        self.type_len = type_len
        self.type_value = type_value
    
    @staticmethod
    def analyze_dp_device_status(hex_str, has_dp_id=False):
        result = []
        if not hex_str:
            return result
        comma_pos = hex_str.find(',')
        if comma_pos != -1:
            hex_str = hex_str[:comma_pos]
        length = len(hex_str) // 2
        byte_array = bytearray(length)
        for i in range(length):
            pos = i * 2
            substring = hex_str[pos:pos+2]
            byte_array[i] = int(substring, 16) & 0xFF
        i = 0
        while i < length:
            dp_status = DpDeviceStatus()
            
            if has_dp_id:
                buffer = bytearray(8)
                buffer[0] = byte_array[i]
                dp_status.dp_id = int.from_bytes(buffer, byteorder='little')
                i += 1
            
            b = byte_array[i]
            if ((b >> 7) & 1) == 0:
                dp_status.type_code = (b >> 4) & 7
                dp_status.type_len = 1
                dp_status.type_value = bytes([b])
                i += 1
            else:
                type_code_part = (b >> 2) & 31
                len_bytes = (b & 3) + 1
                dp_status.type_len = len_bytes
                
                if type_code_part <= 30:
                    dp_status.type_code = type_code_part + 8
                    total_len = len_bytes + 1
                    dp_status.type_value = byte_array[i:i+total_len]
                else:
                    i += 1
                    dp_status.type_code = byte_array[i] + 39
                    total_len = len_bytes + 1
                    dp_status.type_value = byte_array[i-1:i+len_bytes]
                
                i += total_len - 1 if type_code_part <= 30 else len_bytes
            
            result.append(dp_status)
            i += 1
        
        return result
    
    def __eq__(self, other):
        if self is other:
            return True
        if not isinstance(other, DpDeviceStatus):
            return False
        return (self.dp_id == other.dp_id and
                self.type_code == other.type_code and
                self.type_len == other.type_len)
    
    def __hash__(self):
        result = ((self.dp_id * 31 + self.type_code) * 31 + self.type_len) * 31
        if self.type_value is not None:
            return result + hash(bytes(self.type_value))
        return result
    
    def __str__(self):
        return (f"DpDeviceStatus(dp_id={self.dp_id}, type_code={self.type_code}, "
                f"type_len={self.type_len}, type_value={self.type_value})")
    
class NotImplementedError(Exception):
    pass


class DevicePanel:
    def get_model(self, model_code: int) -> Optional[List[RecDeviceDpModel]]:
        if model_code == 271:
            models = []
            models.append(RecDeviceDpModel(DpStatusCode.RSSI.value, 23, 0, 1))
            models.append(RecDeviceDpModel(DpStatusCode.BAT.value, 24, 0, 1))
            models.append(RecDeviceDpModel(DpStatusCode.WK_STATE.value, 25, 1, 1))
            models.append(RecDeviceDpModel(DpStatusCode.WK_STATE.value, 26, 2, 1))
            models.append(RecDeviceDpModel(DpStatusCode.WK_STATE.value, 27, 3, 1))
            models.append(RecDeviceDpModel(DpStatusCode.ALARM.value, 29, 1, 1))
            models.append(RecDeviceDpModel(DpStatusCode.ALARM.value, 30, 2, 1))
            models.append(RecDeviceDpModel(DpStatusCode.ALARM.value, 31, 3, 1))
            models.append(RecDeviceDpModel(DpStatusCode.EVENT_TIME.value, 33, 1, 1))
            models.append(RecDeviceDpModel(DpStatusCode.EVENT_TIME.value, 34, 2, 1))
            models.append(RecDeviceDpModel(DpStatusCode.EVENT_TIME.value, 35, 3, 1))
            models.append(RecDeviceDpModel(DpStatusCode.DURATION.value, 37, 1, 1))
            models.append(RecDeviceDpModel(DpStatusCode.DURATION.value, 38, 2, 1))
            models.append(RecDeviceDpModel(DpStatusCode.DURATION.value, 39, 3, 1))
            return models
        return None

    def is_dp_status(self, status: str) -> bool:
        return status.find("#") == 2

    def is_return_default(self, model: int, status: str) -> bool:
        if model != 0:
            return status == ""
        return True

    def is_water_leak(self, pcode: int, model: int, status: str, timestamp: int, port: int) -> bool:
        if self.is_return_default(model, status):
            return False
        try:
            if self.is_dp_status(status):
                dp_device_status = self.get_dp_device_status(model, status, DpStatusCode.ALARM, port)
                if dp_device_status is None or dp_device_status.type_value is None:
                    return False
                type_value = dp_device_status.type_value
                if len(type_value) < 1:
                    return False
                return (type_value[0] & 1) == 1
            else:
                raise NotImplementedError()
        except Exception:
            return False

    def is_water_shortage(self, pcode: int, model: int, status: str, timestamp: int, port: int) -> bool:
        if self.is_return_default(model, status):
            return False
        try:
            if self.is_dp_status(status):
                dp_device_status = self.get_dp_device_status(model, status, DpStatusCode.ALARM, port)
                if dp_device_status is None or dp_device_status.type_value is None:
                    return False
                type_value = dp_device_status.type_value
                if len(type_value) < 1:
                    return False
                return ((type_value[0] >> 1) & 1) == 1
            else:
                raise NotImplementedError()
        except Exception:
            return False

    def get_bat(self, pcode: int, model: int, status: str, timestamp: int) -> int:
        if self.is_return_default(model, status):
            return 0
        try:
            if not self.is_dp_status(status):
                raise NotImplementedError()
            dp_device_status = self.get_dp_device_status(model, status, DpStatusCode.BAT, 0)
            if dp_device_status is None or dp_device_status.type_value is None:
                return 0
            type_value = dp_device_status.type_value
            if len(type_value) < 2:
                return 0
            # Convert byte to int using struct
            return struct.unpack('<Q', type_value[1:2] + b'\x00' * 7)[0]
        except Exception:
            return 0

    def get_rssi(self, pcode: int, model: int, status: str, timestamp: int) -> int:
        if self.is_return_default(model, status):
            return 0
        try:
            if not (pcode == 1 or pcode == 3):
                if not self.is_dp_status(status):
                    raise NotImplementedError()
                dp_device_status = self.get_dp_device_status(model, status, DpStatusCode.RSSI, 0)
                if dp_device_status is None or dp_device_status.type_value is None:
                    return 0
                type_value = dp_device_status.type_value
                if len(type_value) < 2:
                    return 0
                return type_value[1]
            
            if not self.is_dp_status(status):
                raise NotImplementedError()
            dp_device_status = self.get_dp_device_status(model, status, DpStatusCode.RSSI, 0)
            if dp_device_status is None or dp_device_status.type_value is None:
                return 0
            type_value = dp_device_status.type_value
            if len(type_value) < 2:
                return 0
            return type_value[1]
        except Exception:
            return 0

    def get_work_mode(self, pcode: int, model: int, status: str, timestamp: int, port: int) -> int:
        if self.is_return_default(model, status):
            return 0
        try:
            if self.is_dp_status(status):
                dp_device_status = self.get_dp_device_status(model, status, DpStatusCode.WK_STATE, port)
                if dp_device_status is None or dp_device_status.type_value is None:
                    return 0
                type_value = dp_device_status.type_value
                if len(type_value) < 2:
                    return 0
                return type_value[1] & 15
            else:
                raise NotImplementedError()
        except Exception:
            return 0

    def get_work_duration(self, pcode: int, model: int, status: str, timestamp: int, port: int) -> int:
        if not self.is_return_default(model, status):
            try:
                if self.is_dp_status(status):
                    dp_device_status = self.get_dp_device_status(model, status, DpStatusCode.DURATION, port)
                    if dp_device_status is not None and dp_device_status.type_value is not None and dp_device_status.type_len > 0:
                        type_len = dp_device_status.type_len
                        type_value = dp_device_status.type_value
                        bytes_array = type_value[1:1+type_len]
                        # Extend to at least 8 bytes for struct unpacking
                        padded_bytes = bytes_array + b'\x00' * (max(type_len, 8) - len(bytes_array))
                        return struct.unpack('<Q', padded_bytes[:8])[0]
                else:
                    raise NotImplementedError()
            except Exception:
                pass
        return -1

    def get_current_water_duration(self, pcode: int, model: int, status: str, timestamp: int, port: int) -> int:
        if self.is_return_default(model, status):
            return 0
        try:
            if not self.is_dp_status(status):
                raise NotImplementedError()
            dp_device_status = self.get_dp_device_status(model, status, DpStatusCode.DURATION, port)
            if dp_device_status is None or dp_device_status.type_value is None or dp_device_status.type_len <= 0:
                return 0
            type_len = dp_device_status.type_len
            type_value = dp_device_status.type_value
            bytes_array = type_value[1:1+type_len]
            # Extend to at least 8 bytes for struct unpacking
            padded_bytes = bytes_array + b'\x00' * (max(type_len, 8) - len(bytes_array))
            return struct.unpack('<Q', padded_bytes[:8])[0]
        except Exception:
            return 0

    def get_irrigation_end_time(self, pcode: int, model: int, status: str, timestamp: int, port: int) -> int:
        if not self.is_return_default(model, status):
            try:
                if self.is_dp_status(status):
                    dp_device_status = self.get_dp_device_status(model, status, DpStatusCode.EVENT_TIME, port)
                    if self.get_work_mode(pcode, model, status, timestamp, port) > 0:
                        if dp_device_status is not None and dp_device_status.type_value is not None:
                            type_value = dp_device_status.type_value
                            if len(type_value) >= 5:
                                bytes_array = type_value[1:5]
                                # Extend to 8 bytes for struct unpacking
                                padded_bytes = bytes_array + b'\x00' * 4
                                time_value = struct.unpack('<Q', padded_bytes)[0]
                                t4_date = T4Date.get_t4_date_by_param(time_value)
                                time_stamp = t4_date.get_timestamp() - timestamp
                                return time_stamp
                else:
                    raise NotImplementedError()
            except Exception:
                pass
        return -1

    def get_water_state_time(self, pcode: int, model: int, status: str, timestamp: int, port: int) -> T4Date:
        if not self.is_return_default(model, status):
            try:
                if self.is_dp_status(status):
                    dp_device_status = self.get_dp_device_status(model, status, DpStatusCode.EVENT_TIME, port)
                    if dp_device_status is not None and dp_device_status.type_value is not None:
                        type_value = dp_device_status.type_value
                        if len(type_value) >= 5:
                            bytes_array = type_value[1:5]
                            # Extend to 8 bytes for struct unpacking
                            padded_bytes = bytes_array + b'\x00' * 4
                            time_value = struct.unpack('<Q', padded_bytes)[0]
                            return T4Date.get_t4_date_by_param(time_value)
                else:
                    raise NotImplementedError()
            except Exception:
                pass
        return T4Date()

    def get_dp_device_status(self, model: int, status: str, dp_status_code: DpStatusCode, port: int) -> Optional[DpDeviceStatus]:
        is_versioned = True
        if port == 0:
            port = 1
        
        rec_device_dp_model = None
        model_list = self.get_model(model)
        
        if model_list is not None:
            for device_dp_model in model_list:
                rec_device_dp_model = device_dp_model
                dp_port = rec_device_dp_model.dp_port if rec_device_dp_model.dp_port != 0 else 1
                if (rec_device_dp_model.dp_type == 1 and 
                    rec_device_dp_model.dp_code == dp_status_code.value and
                    dp_port == port):
                    break
        
        if rec_device_dp_model is None:
            return None
        
        status_param = status
        if "#" in status_param:
            substring = status_param[1:2]
            status_param = status_param[3:]
            is_versioned = substring == "1"
        
        for device_status in DpDeviceStatus.analyze_dp_device_status(status_param, is_versioned):
            if is_versioned:
                if (device_status.type_code == dp_status_code.value and 
                    device_status.dp_id == rec_device_dp_model.dp_id):
                    return device_status
            else:
                if device_status.type_code == dp_status_code.value:
                    return device_status
        
        return None