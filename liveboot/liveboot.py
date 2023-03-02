
import sys
import json
from datetime import datetime as DateTime
import logging
import typing
import re
from pprint import pformat
from dataclasses import dataclass

import jmespath
import redfish

from .waitloop import WaitLoop

Client = redfish.rest.v1.HttpClient
Response = redfish.rest.v1.RestResponse
OptResponse = typing.Optional[Response]


@dataclass
class LiveBoot:
    ip: str
    username: str
    password: str
    proxy: Client = None

    def __repr__(self):
        return f"Liveboot {self.ip}"


    def login(self):
        if self.proxy:
            return(f"LiveBoot instance already logged in")
        self.proxy = redfish.redfish_client(
            base_url=f"https://{self.ip}/",
            username=self.username,
            password=self.password,
        )
        self.proxy.login(auth='session')

    def logout(self):
        if not self.proxy:
            return(f"cannot logout LiveBoot instance")
        self.proxy.logout()
        self.proxy = None


    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.logout()


    # the generic _getter - using GET
    def _get(
        self, uri,
        #*,
        # extract from the result
        xpath=None,
        ok_codes=(200,),
        # convenience to make our code smaller
        prefix="Systems/System.Embedded.1/",
        # again; if True, do not even insert /redfish/v1
        raw=False,
        # if true, ignore xpath and return the Response object
        return_response=False,
        ):
        if not self.proxy:
            raise RuntimeError(f"can only send commands (name) when connected")
        url = f"{'/redfish/v1' if not raw else ''}/{prefix}{uri}"
        response = self.proxy.get(url)
        if response.status not in ok_codes:
            logging.error(f"{self}: {url} returned {response.status}")
            # xxx not sure if that's relevant, see _post for showing more details ?
            return None
        if return_response:
            return response
        data = json.loads(response.text)
        if not xpath:
            return data
        else:
            return jmespath.search(xpath, data)


    # and the setter - using POST
    def _post(self, uri, payload,
              #*,
              ok_codes=(204,),
              prefix="Systems/System.Embedded.1/") -> OptResponse:
        if not self.proxy:
            raise RuntimeError(f"can only send commands (name) when connected")
        url = f"/redfish/v1/{prefix}{uri}"
        headers = {'content-type': 'application/json'}
        response = self.proxy.post(url, headers=headers, body=payload)
        if response.status in ok_codes:
            return response
        else:
            logging.error(f"{self}: POST {url} returned {response.status}")
            try:
                details = pformat(json.loads(response.text))
                message = "detailed error message (JSON) ---"
            except:
                details = response.text
                message = "detailed error message (RAW) ---"
            logging.warning(details)
            logging.warning(message)
            return False


    # redfish has the notion of monitor() on a Client instance
    # https://github.com/DMTF/python-redfish-library#working-with-tasks
    # but it's hard to grasp what the context is for, so...
    def _wait_for(self, response: Response, timeout=60) -> OptResponse:
        task_uri = response.task_location
        try:
            with WaitLoop(timeout) as waitloop:
                while True:
                    response = self._get(
                        task_uri, prefix="", raw=True,
                        return_response=True, ok_codes=(200, 202))
                    if not response:
                        raise ValueError(f"unexpected return code while waiting for a task")
                    if response.status == 200:
                        return response
                    waitloop.period = response.retry_after or 1
                    # this shows 'Running'
                    # print(response.dict['TaskState'])
                    waitloop.tick()
        except TimeoutError:
            logging.error(f"timeout ({timeout}) occurred while waiting for {task_uri}")
            return False

        return response


    def get_power_state(self) -> str:
        return self._get(
            '', 'PowerState')

    def get_available_power_states(self) -> list[str]:
        return self._get(
            '',
            'Actions."#ComputerSystem.Reset"."ResetType@Redfish.AllowableValues"')

    def set_power_state(self, newstate) -> bool:
        return self._post(
            'Actions/ComputerSystem.Reset',
            {'ResetType': newstate})


    def get_virtual_medias(self) -> list[dict]:
        """
        returns s.t like
            Name: 'VirtualMedia Collection'
            Description: 'Collection of Virtual Media'
            Members:
            - Id: '1'
                Name: 'VirtualMedia Instance 1'
                <snip>
            - Id: '2'
        """
        return self._get(
            "VirtualMedia?$expand=*($levels=1)",
        )

    def get_virtual_media(self, device) -> dict:
        """
        the 'Members' part of the above, for that device
        """
        data = self.get_virtual_medias()
        for media in data['Members']:
            if int(media['Id']) == int(device):
                return media

    def show_virtual_medias(self) -> None:
        medias = self.get_virtual_medias()
        if not medias:
            print("no media")
            return
        for media in medias['Members']:
            media_id = media['Id']
            media_name = media['Name']
            print(f"{media_name}: ", end="")
            match media['ConnectedVia']:
                case 'NotConnected':
                    print(f"not connected")
                case 'URI':
                    print(f"=> {media['Image']}")
                case _:
                    print(f"??? {media['ConnectedVia']=}")

    def _insert_virtual_media(self, device, uri) -> OptResponse:
        if device not in (1, 2):
            logging.error(f"Wrong device index {device} - existing")
            return False
        payload = {'Image': uri, 'Inserted': True, 'WriteProtected': True}
        return self._post(
            f'VirtualMedia/{device}/Actions/VirtualMedia.InsertMedia',
            payload)

    def _eject_virtual_media(self, device: int) -> OptResponse:
        if device not in (1, 2):
            logging.error(f"Wrong device index {device} - existing")
            return False
        return self._post(
            f'VirtualMedia/{device}/Actions/VirtualMedia.EjectMedia',
            # empty payload
            {},
        )

    def insert_virtual_media(self, device, uri) -> OptResponse:
        """
        insert - does a first eject beforhand if needed
        """
        status = self.get_virtual_media(device)
        if status['ConnectedVia'] == 'URI':
            logging.warning(f"device {device} is busy, ejecting first")
            self._eject_virtual_media(device)
        return self._insert_virtual_media(device, uri)

    def eject_virtual_media(self, device) -> OptResponse:
        """
        eject but only if necessay
        """
        status = self.get_virtual_media(device)
        if status['ConnectedVia'] != 'URI':
            logging.warning(f"device {device} already ejected")
            return
        return self._eject_virtual_media(device, uri)



    def set_next_one_time_boot_virtual_media_device(self, device: int) -> bool:
        if device not in (1, 2):
            logging.error(f"Wrong device index {device} - existing")
            return False
        url = 'Actions/Oem/EID_674_Manager.ImportSystemConfiguration'
        device_name = "VCD-DVD" if device == 1 else "vFDD"
        payload = {
            "ShareParameters":
                {"Target": "ALL"},
            "ImportBuffer": (
                f'<SystemConfiguration>'
                f'<Component FQDD="iDRAC.Embedded.1">'
                f'<Attribute Name="ServerBoot.1#BootOnce">Enabled</Attribute>'
                f'<Attribute Name="ServerBoot.1#FirstBootDevice">{device_name}</Attribute>'
                f'</Component></SystemConfiguration>')
            }
        # this request won't return immediately - hence the returned 202
        pass1 = self._post(
            url,
            payload,
            prefix="Managers/iDRAC.Embedded.1/",
            ok_codes=(202,),
        )
        if not pass1:
            return False
        return self._wait_for(pass1)
        # we need to wait for it to complete
        #task_uri = pass1['headers']['Location']


    def reboot(self, wait_for_off=300, wait_for_forceoff=15, check_cycle=3) -> OptResponse:
        """
        reboot the box; tries to be smart

        Parameters:
          - wait_for_off:
              when the node is on, we start turning it - gracefully - off
              if it does not reach the Off state within that time (in seconds),
              use ForceOff instead
          - wait_for_forceoff:
              after issuing a force off we again wait to get a 'Off' status
          - check_cycle:
              how often do we check for progress, in seconds

        Returns:
          - if anything goes wrong, returns None
          - otherwise returns the response of the last 'On' request
        """
        state = self.get_power_state()
        match state:
            case 'On':
                if not self.set_power_state("GracefulShutdown"):
                    logging.error(
                        f"{self}: not rebooting: cannot gracefully shutdown - exiting")
                    return False
                try:
                    with WaitLoop(timeout=wait_for_off, period=check_cycle) as waitloop:
                        while True:
                            waitloop.tick()
                            if self.get_power_state() == 'Off':
                                logging.info(f"{self} reboot: reached 'Off' state")
                                break
                except TimeoutError:
                    # taking too long: resorting to ForceOff
                    if not self.set_power_state('ForceOff'):
                        logging.error(
                            f"{self}: not rebooting: cannot gracefully shutdown - exiting")
                        try:
                            with WaitLoop(timeout=wait_for_forceoff,
                                          period=check_cycle) as waitloop:
                                while True:
                                    waitloop.tick()
                                    if self.get_power_state() == 'Off':
                                        logging.info(f"{self} reboot: reached 'Off' state")
                                        break
                        except TimeoutError:
                            # still not Off: bailing out
                            logging.error(f"{self}: not rebooting: still not Off after ForceOff")
                            return False
                return self.set_power_state('On')
            case 'Off':
                return self.set_power_state('On')
            case _:
                logging.error(f"cannot reboot server in state {state}")
                return False
        pass


    def get_bios_attributes(self):
        return self._get(
            "/Bios",
            xpath="Attributes"
        )

    def _show_bios_attributes(self, pattern="", file=sys.stdout):
        """
        e.g.
        show_bios_attributes(".*Prof.*")
        """
        date = DateTime.now().strftime("%Y %m %d @ %H:%M:%S")
        print(f"BIOS settings captured on {self.ip} on {date}", file=file, end="")
        if pattern:
            print(f" with pattern=`{pattern}`", file=file)
        else:
            print(file=file)
        data = self.get_bios_attributes()
        margin = max(map(lambda k: len(k), data.keys()))
        for k, v in data.items():
            if not pattern or re.match(pattern, k):
                print(f"{k:>{margin}}: {v}", file=file)

    def show_bios_attributes(self, pattern="", filename=None, mode='w'):
        if not filename:
            self._show_bios_attributes(pattern)
        else:
            with open(filename, mode) as writer:
                self._show_bios_attributes(pattern, file=writer)
