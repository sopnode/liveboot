# pylint: disable=missing-function-docstring
# pylint: disable=logging-fstring-interpolation

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
class Idrac:
    ip: str
    username: str
    password: str
    proxy: Client = None

    def __repr__(self):
        return f"Liveboot {self.ip}"


    def login(self):
        if self.proxy:
            return(f"Idrac {self} already logged in")
        self.proxy = redfish.redfish_client(
            base_url=f"https://{self.ip}/",
            username=self.username,
            password=self.password,
        )
        self.proxy.login(auth='session')

    def logout(self):
        if not self.proxy:
            return(f"cannot logout Idrac {self}")
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
            #*,  somehow adding this creates a lot of trouble...
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


    # and the setter - using POST (or PATCH it patch is set)
    def _post(self, uri, payload,
            #*,  somehow adding this creates a lot of trouble...
            ok_codes=(204,),
            prefix="Systems/System.Embedded.1/",
            patch=False) -> OptResponse:
        """
        send a POST request, unless patch is set in which case it is a PATCH request
        """
        if not self.proxy:
            raise RuntimeError(f"can only send commands (name) when connected")
        url = f"/redfish/v1/{prefix}{uri}"
        headers = {'content-type': 'application/json'}
        if patch:
            msg = "PATCH"
            response = self.proxy.patch(url, headers=headers, body=payload)
        else:
            msg = "POST"
            response = self.proxy.post(url, headers=headers, body=payload)
        if response.status in ok_codes:
            return response
        else:
            logging.error(f"{self}: {msg} {url} returned {response.status}")
            try:
                details = pformat(json.loads(response.text))
                message = "detailed error message (JSON) ---"
            except json.JSONDecodeError:
                details = response.text
                message = "detailed error message (RAW) ---"
            logging.warning(details)
            logging.warning(message)
            return False


    # redfish has the notion of monitor() on a Client instance
    # https://github.com/DMTF/python-redfish-library#working-with-tasks
    # but it's hard to grasp what the context is for, so...
    def _wait_for(self, response: Response, timeout=60, check_cycle=1) -> OptResponse:
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
                    waitloop.period = response.retry_after or check_cycle
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
            "Members",
        )

    def get_virtual_media(self, device) -> dict:
        """
        the 'Members' part of the above, for that device
        """
        for media in self.get_virtual_medias():
            if int(media['Id']) == int(device):
                return media

    @staticmethod
    def virtual_media_status(media) -> dict:
        """
        given a raw media dict as returned by get_virtual_medias
        we return a single dictionary like e.g.
        { 'Vmedia slot 1': None}
        or
        { 'Vmedia slot 2: 'http://blabla'}
        """
        media_id = media['Id']
        name = f"Vmedia slot {media_id}"
        match media['ConnectedVia']:
            case 'NotConnected':
                return {name: None}
            case 'URI':
                return {name: media['Image']}
            case _:
                return {name: f"??? {media['ConnectedVia']=}"}


    def show_virtual_medias(self) -> None:
        medias = self.get_virtual_medias()
        if not medias:
            print("no media")
            return
        for media in medias:
            # only one key, but that's still the simplest way...
            for k, v in self.virtual_media_status(media).items():
                print(f"{k}: {v or 'not connected'}")

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
            logging.info(f"device {device} is busy, ejecting first")
            self._eject_virtual_media(device)
        return self._insert_virtual_media(device, uri)

    def eject_virtual_media(self, device) -> OptResponse:
        """
        eject but only if necessay
        """
        status = self.get_virtual_media(device)
        if status['ConnectedVia'] != 'URI':
            logging.info(f"device {device} already ejected")
            return
        return self._eject_virtual_media(device)



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



    def on(self) -> bool:
        """
        turn on the box
        """
        if not self.set_power_state('On'):
            logging.error( f"{self}: cannot turn ON")
            return False
        return True


    def off(self, wait_for_off=300, wait_for_forceoff=15, check_cycle=3) -> bool:
        """
        turn off the box
        first try to use GracefulShutdown, then ForceOff if that fails

        Parameters:
          - wait_for_off:
              when the node is on, we start turning it - gracefully - off
              if it does not reach the Off state within that time (in seconds),
              use ForceOff instead
          - wait_for_forceoff:
              after issuing a force off we again wait to get a 'Off' status
          - check_cycle:
              how often do we check for progress, in seconds

        """
        if not self.set_power_state("GracefulShutdown"):
            logging.error(
                f"{self}: cannot turn off gracefully")
            return False
        try:
            with WaitLoop(timeout=wait_for_off, period=check_cycle) as waitloop:
                while True:
                    waitloop.tick()
                    if self.get_power_state() == 'Off':
                        logging.info(f"{self} reboot: reached 'Off' state")
                        return True
        except TimeoutError:
            # taking too long: resorting to ForceOff
            if not self.set_power_state('ForceOff'):
                logging.error(
                    f"{self}: cannot turn off forcefully")
                return False
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
                logging.error(f"{self}: still not Off after ForceOff and {wait_for_forceoff} s")
                return False


    def reboot(self, wait_for_off=300, wait_for_forceoff=15, check_cycle=3) -> OptResponse:
        """
        reboot the box; tries to be smart

        Parameters:
          - see off() above
        Returns:
          - if anything goes wrong, returns None
          - otherwise returns the response of the last 'On' request
        """
        state = self.get_power_state()
        match state:
            case 'On':
                if not self.off(wait_for_off, wait_for_forceoff, check_cycle):
                    logging.error(f"{self}: could not turn off, not rebooting")
                return self.set_power_state('On')
            case 'Off':
                return self.set_power_state('On')
            case _:
                logging.error(f"cannot reboot server in state {state}")
                return False



    def get_bios_attributes(self, pattern=None) -> dict:
        all_attributes = self._get(
            "/Bios",
            xpath="Attributes"
        )
        return {
            k: v for k, v in all_attributes.items()
            if not pattern or re.search(pattern, k, flags=re.I)
        }

    def show_bios_attributes(self, pattern=None):
        """
        e.g.
        show_bios_attributes(".*Prof.*")
        """
        date = DateTime.now().strftime("%Y %m %d @ %H:%M:%S")
        print(f"BIOS settings captured on {self.ip} on {date}", end="")
        if pattern:
            print(f" with pattern=`{pattern}`")
        else:
            print()
        data = self.get_bios_attributes(pattern)
        margin = max(map(len, data.keys()), default=0)
        for k, v in data.items():
            print(f"{k:>{margin}}: {v}")


    def set_bios_attributes(self, new_values: dict) -> bool:
        """
        Parameters:
          - a dictionary that has the values to be changed
            e.g. {'MemTest': 'Disabled'}
        """
        # minimal type checking: the registry
        # explains the available settings, with some
        # details about their type and admissible value
        registry = self._get(
            "Bios/BiosRegistry",
            xpath="RegistryEntries.Attributes"
        )
        logging.info("BIOS registry retrieved (for type conversion and values checking)")
        def find_in_registry(setting):
            for D in registry:
                if D['AttributeName'].lower() == setting.lower():
                    return D
        def find_in_enumeration(value, enumeration):
            for item in enumeration:
                if value.lower() == item.lower():
                    return item
        # because we tolerate lowercase input, we must build
        # a near-copy of new_values
        new_values_checked = {}
        for setting, value in new_values.items():
            spec = find_in_registry(setting)
            if not spec:
                logging.error(f"Unknown setting {setting} - exiting")
                return False
            if spec['Type'] == 'Integer':
                new_value = int(value)
            elif spec['Type'] == 'Enumeration':
                admissible = {D['ValueName'] for D in spec['Value']}
                new_value = find_in_enumeration(value, admissible)
                if not new_value:
                    logging.error(f"Unexpected value {value} for setting {setting}")
                    logging.error(f"should be among {admissible}")
                    return False
            else:
                new_value = value
            new_values_checked[spec['AttributeName']] = new_value

        # create a job that tells the box to apply the settings upon next reset
        payload = {"@Redfish.SettingsApplyTime": {"ApplyTime": "OnReset"}}
        payload['Attributes'] = new_values_checked
        response = self._post(
            "Bios/Settings",
            payload=payload,
            patch=True,
            ok_codes=(200, 202),
        )
        if not response:
            logging.error(f"Could not create config job")
            return False
        # wait for a confirmation that the config job was created allright
        task_uri = response.task_location
        task_id = task_uri.split('/')[-1]
        logging.info(f"waiting for job {task_id} to be successfully scheduled")
        try:
            with WaitLoop() as waitloop:
                while True:
                    response = self._get(task_uri, prefix="", raw=True,
                        xpath="Oem.Dell",
                        ok_codes=(200, 202,),
                    )
                    if not response:
                        raise ValueError(f"unexpected return code while waiting for a task")
                    if response['Message'] == 'Task successfully scheduled.':
                        return True
                    waitloop.tick()
        except TimeoutError:
            logging.error("Config job not confirmed...")
            return False


    def bios_reset(self) -> OptResponse:
        return self._post(
            "Bios/Actions/Bios.ResetBios",
            payload={},
            ok_codes=(200,),
        )


    def get_queue(self):
        return self._get(
            "Jobs?$expand=*($levels=1)",
            prefix="Managers/iDRAC.Embedded.1/",
            xpath="Members",
        )

    def show_queue(self, show_all=False):
        def oneliner(job):
            return f"complete {job['PercentComplete']:3}% {job['Name']} - {job['JobType']} ({job['Id']})"
        # show past jobs if requested
        if show_all:
            print(f"{' Past jobs ':-^60}")
            for job in self.get_queue():
                if job['PercentComplete'] == 100:
                    print(oneliner(job))
        # the others
        print(f"{' Current jobs ':-^60}")
        for job in self.get_queue():
            if job['PercentComplete'] != 100:
                print(oneliner(job))

    def clear_queue(self, job_id=None):
        payload = dict(JobID = str(job_id) if job_id else "JID_CLEARALL")
        return self._post(
            "DellJobService/Actions/DellJobService.DeleteJobQueue",
            payload=payload,
            prefix="Dell/Managers/iDRAC.Embedded.1/",
            ok_codes=(200,)
        )
