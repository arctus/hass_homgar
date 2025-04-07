import binascii
import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional, List

import requests

from api.devices import HomgarHome, MODEL_CODE_MAPPING, HomgarHubDevice, TemperatureAirSensor
from api.logutil import TRACE, get_logger, logging

logger = get_logger(__file__)


class HomgarApiException(Exception):
    def __init__(self, code, msg):
        super().__init__()
        self.code = code
        self.msg = msg
        logger.error(f"HomgarApiException: code={code}, msg={msg}")

    def __str__(self):
        s = f"HomGar API returned code {self.code}"
        if self.msg:
            s += f" ('{self.msg}')"
        return s


class HomgarApi:
    def __init__(
            self,
            auth_cache: Optional[dict] = None,
            api_base_url: str = "https://region3.homgarus.com",
            requests_session: requests.Session = None
    ):
        """
        Create an object for interacting with the Homgar API
        :param auth_cache: A dictionary in which authentication information will be stored.
            Save this dict on exit and supply it again next time constructing this object to avoid logging in
            if a valid token is still present.
        :param api_base_url: The base URL for the Homgar API. Omit trailing slash.
        :param requests_session: Optional requests lib session to use. New session is created if omitted.
        """
        self.session = requests_session or requests.Session()
        self.cache = auth_cache or {}
        self.base = api_base_url
        logger.info("Initialized HomgarApi with base URL: %s", self.base)

    def _request(self, method, url, with_auth=True, headers=None, **kwargs):
        """
        Make a HTTP request and log the details.
        :param method: HTTP method (GET, POST, etc.)
        :param url: The URL to request.
        :param with_auth: Boolean to include auth token in headers.
        :param headers: Optional additional headers.
        """
        logger.log(TRACE, "%s %s %s", method, url, kwargs)
        headers = {"lang": "en", "appCode": "1", **(headers or {})}
        if with_auth:
            headers["auth"] = self.cache["token"]
        response = self.session.request(method, url, headers=headers, **kwargs)
        logger.log(TRACE, "-[%03d]-> %s", response.status_code, response.text)
        return response

    def _request_json(self, method, path, **kwargs):
        """
        Make a HTTP request expecting a JSON response and log the outcome.
        :param method: HTTP method (GET, POST, etc.)
        :param path: The API path to request.
        """
        response = self._request(method, self.base + path, **kwargs).json()
        code = response.get('code')
        if code != 0:
            logger.error("API returned error code %d with message: %s", code, response.get('msg'))
            raise HomgarApiException(code, response.get('msg'))
        return response.get('data')

    def _get_json(self, path, **kwargs):
        """
        Perform a GET request expecting a JSON response.
        :param path: The API path to request.
        """
        logger.info("GET request for path: %s", path)
        return self._request_json("GET", path, **kwargs)

    def _post_json(self, path, body, **kwargs):
        """
        Perform a POST request expecting a JSON response.
        :param path: The API path to request.
        :param body: The JSON body to send in the POST request.
        """
        logger.info("POST request for path: %s with body: %s", path, body)
        return self._request_json("POST", path, json=body, **kwargs)

    def login(self, email: str, password: str, area_code="31") -> None:
        """
        Perform a new login and cache the authentication tokens.
        :param email: Account e-mail.
        :param password: Account password.
        :param area_code: Phone country code associated with the account.
        """
        logger.info("Attempting to login with email: %s", email)
        data = self._post_json("/auth/basic/app/login", {
            "areaCode": area_code,
            "phoneOrEmail": email,
            "password": hashlib.md5(password.encode('utf-8')).hexdigest(),
            "deviceId": binascii.b2a_hex(os.urandom(16)).decode('utf-8')
        }, with_auth=False)
        self.cache['email'] = email
        self.cache['token'] = data.get('token')
        self.cache['token_expires'] = datetime.utcnow().timestamp() + data.get('tokenExpired')
        self.cache['refresh_token'] = data.get('refreshToken')
        logger.info("Login successful, token cached")

    def get_homes(self) -> List[HomgarHome]:
        """
        Retrieves all HomgarHome objects associated with the logged in account.
        Requires prior login.
        :return: List of HomgarHome objects.
        """
        logger.info("Fetching list of homes")
        data = self._get_json("/app/member/appHome/list")
        homes = [HomgarHome(hid=h.get('hid'), name=h.get('homeName')) for h in data]
        logger.info("Retrieved %d homes", len(homes))
        return homes

    def get_devices_for_hid(self, hid: str) -> List[HomgarHubDevice]:
        """
        Retrieves a device tree associated with the home identified by the given hid (home ID).
        :param hid: The home ID to retrieve hubs and associated subdevices for.
        :return: List of hubs with associated subdevices.
        """
        logger.info("Fetching devices for home ID: %s", hid)
        data = self._get_json("/app/device/getDeviceByHid", params={"hid": str(hid)})
        hubs = []

        def device_base_props(dev_data):
            return dict(
                model=dev_data.get('model'),
                model_code=dev_data.get('modelCode'),
                name=dev_data.get('name'),
                did=dev_data.get('did'),
                mid=dev_data.get('mid'),
                address=dev_data.get('addr'),
                port_number=dev_data.get('portNumber'),
                alerts=dev_data.get('alerts'),
            )

        def get_device_class(dev_data):
            model_code = dev_data.get('modelCode')
            if model_code not in MODEL_CODE_MAPPING:
                logger.warning("Unknown device '%s' with modelCode %d", dev_data.get('model'), model_code)
                return None
            return MODEL_CODE_MAPPING[model_code]

        for hub_data in data:
            subdevices = []
            for subdevice_data in hub_data.get('subDevices', []):
                did = subdevice_data.get('did')
                if did == 1:
                    # Skip hub itself
                    continue
                subdevice_class = get_device_class(subdevice_data)
                if subdevice_class is None:
                    continue
                subdevices.append(subdevice_class(**device_base_props(subdevice_data)))

            hub_class = get_device_class(hub_data)
            if hub_class is None:
                hub_class = HomgarHubDevice

            hubs.append(hub_class(
                **device_base_props(hub_data),
                subdevices=subdevices
            ))

        logger.info("Retrieved %d hubs for home ID: %s", len(hubs), hid)
        return hubs

    def get_device_status(self, hub: HomgarHubDevice) -> None:
        """
        Updates the device status of all subdevices associated with the given hub device.
        :param hub: The hub to update.
        """
        logger.info("Fetching device status for hub ID: %s", hub.mid)
        data = self._get_json("/app/device/getDeviceStatus", params={"mid": str(hub.mid)})
        id_map = {status_id: device for device in [hub, *hub.subdevices] for status_id in device.get_device_status_ids()}

        for subdevice_status in data['subDeviceStatus']:
            device = id_map.get(subdevice_status['id'])
            if device is not None:
                device.set_device_status(subdevice_status)
        logger.info("Device status updated for hub ID: %s", hub.mid)

    def ensure_logged_in(self, email: str, password: str, area_code: str = "31") -> None:
        """
        Ensures this API object has valid credentials.
        If invalid, attempts to login.
        :param email: Account e-mail.
        :param password: Account password.
        :param area_code: Phone country code associated with the account.
        """
        logger.info("Ensuring login status for email: %s", email)
        if (
                self.cache.get('email') != email or
                datetime.fromtimestamp(self.cache.get('token_expires', 0)) - datetime.utcnow() < timedelta(minutes=60)
        ):
            logger.info("Token expired or email mismatch, logging in again")
            self.login(email, password, area_code=area_code)
        else:
            logger.info("Already logged in with valid credentials")