#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# Inspired by https://github.com/silvester747/aio_marantz_avr
#
# This is to control Denon/Marantz AVR devices
#
# Copyright (c) 2020 François Wautier
#
# Note large part of this code was taken from scapy and other opensource software
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies
# or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
# IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE

"""Control of an AVR over Telnet."""

import asyncio
import logging
import re
from enum import Enum
from typing import Any, List, Mapping, Optional, Callable
from .enums import InputSource, Power, SurroundMode, ChannelBias, EcoMode, AudioInput

#Some replacement for the surrond sound format
SSTRANSFORM = [("Audio-"," "),("Dd","Dolby Digital "),("DD","Dolby Digital "),("Dts","DTS"),['Mstr','Master '],
                     ("Dsur","Digital Surround "),("Mtrx","Matrix"),("Dscrt","Discrete "),(" Es "," ES ")]
EXTRAS = ["SSINFAI"]

def cc_string(identifier: str) -> str:
    """ From https://stackoverflow.com/questions/29916065/how-to-do-camelcase-split-in-python """
    matches = re.finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', identifier)
    return " ".join([m.group(0) for m in matches])

def only_int(val: str) -> str:
    return "".join([x for x in val if x in ['0','1','2','3','4','5','6','7','8','9']])


class AvrError(Exception):
    """Base class for all errors returned from an AVR."""

    pass

class AvrTimeoutError(AvrError):
    """A request to the AVR has timed out."""

    pass


async def avr_factory(name: str, host: str, port: int = 23, timeout: float = 3.0) -> "MDAVR":
    """Connect to an AVR.

        :param name: The name of this device.
        :type url: str
        :param addr: The device IP address
        :type name: str
        :returns: A device instance or None if connection cannot be established
        :rtype: MDAVR
    """
    try:
        reader, writer = await asyncio.open_connection(host, port=port)
        return MDAVR(name, reader, writer, timeout)
    except:
        return None


def _on_off_from_bool(value: bool) -> str:
    if value:
        return "ON"
    else:
        return "OFF"


def _on_off_to_bool(value: str) -> bool:
    return value == "ON"


class _CommandDef:
    code: str
    label: str
    vals: Optional[Enum]

    def __init__(self,  label: str, vals: Any):
        self.label = label
        self.values = vals


class MDAVR:
    """Connection to a Marantz AVR over Telnet.

    Uses `connect` to create a connection to the AVR.
    """

    CMDS_DEFS: Mapping[str,_CommandDef] = {
        "PW": _CommandDef("Power", Power),
        "MU": _CommandDef("Mute", None),
        "MV": _CommandDef("Volume", None),
        "SI": _CommandDef("Source", InputSource),
        "MS": _CommandDef("Surround Mode", SurroundMode),
        "CV": _CommandDef("Channel Bias", ChannelBias),
        "ECO": _CommandDef("Eco Mode", EcoMode),
    }

    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    _timeout: float

    def __init__(
        self, name: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, timeout: float,
    ):
        self.name = name
        self._reader = reader
        self._writer = writer
        self._timeout = timeout
        self.status = {}
        self.maxvol = 98      #Good default ;)
        self.alive = True
        self.queue = []
        for x in self.CMDS_DEFS:
            self.status[self.CMDS_DEFS[x].label]="-"
        self.cvend = True
        self.notify = None
        #Start reading
        self.rtask = asyncio.get_event_loop().create_task(self._do_read())

    def _get_current(self,cmd):
        return self.status[self.CMDS_DEFS[cmd].label]

    def _get_list(self,cmd):
        return [cc_string(x.name) for x in list(self.CMDS_DEFS[cmd].values)]

    #API Starts here
    @property
    def power(self) -> Optional[Power]:
        """Power state of the AVR."""
        return self._get_current("PW")

    @property
    def muted(self) -> Optional[bool]:
        """Boolean if volume is currently muted."""
        return self._get_current("MU")

    @property
    def volume(self) -> Optional[float]:
        """Volume level of the AVR zone (00..max_volume)."""
        return self._get_current("MV")

    @property
    def max_volume(self) -> Optional[float]:
        """Maximum volume level of the AVR zone."""
        return self.maxvol

    @property
    def source(self) -> str:
        """Name of the current input source."""
        return self._get_current("SI")

    @property
    def source_list(self) -> List[str]:
        """List of available input sources."""
        return self._get_list("SI")

    @property
    def sound_mode(self) -> str:
        """Name of the current sound mode."""
        return self._get_current("MS")

    @property
    def sound_mode_list(self) -> List[str]:
        """List of available sound modes."""
        return self._get_list("MS")

    @property
    def eco_mode(self) -> str:
        """Current ECO mode."""
        return self._get_current("ECO")

    @property
    def eco_mode_list(self) -> List[str]:
        """List of available exo modes."""
        return self._get_list("ECO")

    @property
    def channels_bias(self) -> Mapping[str,float]:
        return self._get_current("CV")

    @property
    def channels_bias_list(self) -> List[str]:
        """List of currently available."""
        return [x for x in self._get_current("CV").keys()]


    async def refresh(self) -> None:
        """Refresh all properties from the AVR."""

        for cmd_def in self.CMDS_DEFS:
            fut = await self._send_command(cmd_def,"?")
            try:
                await self._wait_for_response_with_timeout(fut)
            except asyncio.TimeoutError:
                self._clean_fut(fut)
                raise AvrTimeoutError

    async def turn_on(self) -> None:
        """Turn the AVR on."""
        fut = await self._send_command("PW", "ON")
        try:
            await self._wait_for_response_with_timeout(fut)
        except asyncio.TimeoutError:
            self._clean_fut(fut)
            raise AvrTimeoutError

    async def turn_off(self) -> None:
        """Turn the AVR off."""
        fut = await self._send_command("PW", "STANDBY")
        try:
            await self._wait_for_response_with_timeout(fut)
        except asyncio.TimeoutError:
            self._clean_fut(fut)
            raise AvrTimeoutError


    async def mute_volume(self, mute: bool) -> None:
        """Mute or unmute the volume.

        Arguments:
        mute -- True to mute, False to unmute.
        """
        fut = await self._send_command("MU", _on_off_from_bool(mute))
        try:
            await self._wait_for_response_with_timeout(fut)
        except asyncio.TimeoutError:
            self._clean_fut(fut)
            raise AvrTimeoutError

    async def set_volume(self, level: float) -> None:
        """Set the volume level.

        Arguments:
        level -- An integer value between 0 and `max_volume`.
        """
        if level > self.maxvol:
            level = maxvol
        if int(10*level)%10:
            #Needs to be a nultiple of 5
            level = int(5*round(10*level/5))
        else:
            level = int(level)
        fut = await self._send_command("MV",f"{level:02}")
        try:
            await self._wait_for_response_with_timeout(fut)
        except asyncio.TimeoutError:
            self._clean_fut(fut)
            raise AvrTimeoutError

    async def volume_up(self) -> None:
        """Turn the volume level up one notch."""
        fut = await self._send_command("MV","UP")
        try:
            await self._wait_for_response_with_timeout(fut)
        except asyncio.TimeoutError:
            self._clean_fut(fut)
            raise AvrTimeoutError

    async def volume_down(self) -> None:
        """Turn the volume level down one notch."""
        fut = await self._send_command("MV","DOWN")
        try:
            await self._wait_for_response_with_timeout(fut)
        except asyncio.TimeoutError:
            self._clean_fut(fut)
            raise AvrTimeoutError

    async def set_channel_bias(self, chan: str, level: float) -> None:
        """Set the volume level.

        Arguments:
        chan  -- channel to set
        level -- A float value between -12.0 and +12.0
        """
        if chan not in self.channels_bias:
            logging.warning(f"Channel {chan} is not available right now.")
            await asyncio.sleep(0)
            return


        if self.channels_bias[chan] != level:
            chan = chan.replace(" ","")
            level = level+50 #50 is 0dB
            if level < 38:
                level = 38
            elif level > 62:
                level = 62
            if int(10*level)%10:
                #Needs to be a nultiple of 5
                level = int(5*round(10*level/5))
            else:
                level = int(level)

            cmd = None
            for x in self.CMDS_DEFS["CV"].values:
                if x.name == chan:
                    cmd = x.value
                    break
            if cmd:
                fut = await self._send_command("CV", f"{cmd} {level:02}")
                try:
                    await self._wait_for_response_with_timeout(fut)
                except asyncio.TimeoutError:
                    self._clean_fut(fut)
                    raise AvrTimeoutError
            else:
                logging.error(f"Channel {chan} should exist. This should not have happened.")

    async def channel_bias_up(self, chan: str) -> None:
        """Turn the volume level up one notch."""
        if chan not in self.channels_bias:
            logging.warning(f"Channel {chan} is not available right now.")
            await asyncio.sleep(0)
            return
        if self.channels_bias[chan] == 12:
            #We are at the limit. It won't respond
            logging.debugf(f"Channel {chan} it at the upper limit.")
            await asyncio.sleep(0)
            return

        chan = chan.replace(" ","")
        cmd = None
        for x in self.CMDS_DEFS["CV"].values:
            if x.name == chan:
                cmd = x.value
                break
        if cmd:
            fut = await self._send_command("CV", f"cmd UP")
            try:
                await self._wait_for_response_with_timeout(fut)
            except asyncio.TimeoutError:
                self._clean_fut(fut)
                raise AvrTimeoutError
        else:
            logging.error(f"Channel {chan} should exist. This should not have happened.")

    async def channel_bias_down(self, chan: str) -> None:
        """Turn the volume level down one notch."""
        if chan not in self.channels_bias:
            logging.warning(f"Channel {chan} is not available right now.")
            await asyncio.sleep(0)
            return
        if self.channels_bias[chan] == -12:
            #We are at the limit. It won't respond
            logging.debugf(f"Channel {chan} it at the lowewr limit.")
            await asyncio.sleep(0)
            return

        chan = chan.replace(" ","")
        cmd = None
        for x in self.CMDS_DEFS["CV"].values:
            if x.name == chan:
                cmd = x.value
                break
        if cmd:
            fut = await self._send_command("CV",f"{cmd} DOWN")
            try:
                await self._wait_for_response_with_timeout(fut)
            except asyncio.TimeoutError:
                self._clean_fut(fut)
                raise AvrTimeoutError
        else:
            logging.error(f"Channel {chan} should exist. This should not have happened.")

    async def channels_bias_reset(self):
        fut = await self._send_command("CV", "ZRL")
        try:
            await self._wait_for_response_with_timeout(fut)
        except asyncio.TimeoutError:
            self._clean_fut(fut)
            raise AvrTimeoutError

    async def select_source(self, source: str) -> None:
        """Select the input source."""
        try:
            source = self.CMDS_DEFS["SI"].values[source.replace(" ","")]
        except:
            logging.warning(f"Warning: {source} is not a valid source")
            await asyncio.sleep(0)
            return
        fut = await self._send_command("SI", source.value)
        try:
            await self._wait_for_response_with_timeout(fut)
        except asyncio.TimeoutError:
            #Source might not be available
            logging.warning(f"Warning: {source} may not be a valid source for this device.")
            self._clean_fut(fut)

    async def select_sound_mode(self, mode: str) -> None:
        """Select the sound mode."""
        try:
            mode = self.CMDS_DEFS["MS"].values[mode.replace(" ","")]
        except:
            logging.warning(f"Warning: {mode} is not a valid mode")
            await asyncio.sleep(0)
            return
        fut = await self._send_command("MS", mode.value)
        try:
            await self._wait_for_response_with_timeout(fut)
        except:
            logging.warning(f"Warning: {mode} may not be a valid surround mode for this device.")
            self._clean_fut(fut)

    async def select_eco_mode(self, mode: str) -> None:
        """Select the sound mode."""
        try:
            mode = SurroundMode[mode]
        except:
            logging.warning(f"Warning: {mode} is not a valid eco  mode")
            await asyncio.sleep(0)
            return
        fut = await self._send_command("ECO", mode.value)
        await self._wait_for_response_with_timeout(fut)

    def notifyme(self, func: Callable) -> None:
        """Register a callback for when an event happens. The callable should have 2 parameters,
        The label of the the changing value and the new value
        """
        self.notify = func

    def close(self):
        self.alive = False
        self._writer.close()
        self.rtask.cancel()

    #API ends here

    async def _send_command(self, cmd: str, val: Any) -> asyncio.Future:
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self.queue.append([cmd,fut])
        tosend=f"{cmd}{val}\r"
        logging.debug(f"Sending {tosend}")
        self._writer.write(tosend.encode())
        await self._writer.drain()
        return fut

    async def _with_timeout(self, fut) -> Optional[Any]:
        try:
            return await asyncio.wait_for(fut, self._timeout)
        except asyncio.TimeoutError:
            raise AvrTimeoutError

    async def _wait_for_response_with_timeout(self, fut: asyncio.Future) -> None:
        await self._with_timeout(self._wait_for_response(fut))

    async def _wait_for_response(self, fut: asyncio.Future) -> None:
        await fut

    def _process_response(self, response: str) -> Optional[str]:
        matches = [cmd for cmd in self.CMDS_DEFS.keys() if response.startswith(cmd)] + \
                    [cmd for cmd in EXTRAS if response.startswith(cmd)]

        if not matches:

            return None

        if len(matches) > 1:
            matches.sort(key=len, reverse=True)
        match = matches[0]

        if getattr(self,"_parse_"+match, None):
            getattr(self,"_parse_"+match)(response.strip()[len(match):])
        else:
            #A few special cases ... for now
            if response.startswith("SSINFAISFSV"):
                try:
                    sr = int(response.split(" ")[-1])
                    if sr > 200:
                        sr = round(sr/10,1)
                    else:
                        sr = float(sr)
                    self.status["Sampling Rate"] = sr
                except Exception as e:
                    logging.debug(f"Error with sampling rate: {e}")
            else:
                logging.warning(f"Warning _parse_{match} is not defined.")

        return match

    def _parse_many(self, cmd: str, resp: str) -> None:
        for x in self.CMDS_DEFS[cmd].values:
            if resp == x.value:
                lbl = self.CMDS_DEFS[cmd].label
                if self.status[lbl] != cc_string(x.name):
                    self.status[lbl] = cc_string(x.name)
                    if self.notify:
                        self.notify(lbl,self.status[lbl])

    def _parse_MV(self, resp: str) -> None:
        level = only_int(resp)

        if level:
            if len(level)>2:
                level=int(level)/10
            else:
                level=float(level)

            if resp.startswith("MAX"):
                self.maxvol = level
            else:
                lbl = self.CMDS_DEFS["MV"].label
                if self.status[lbl] != level:
                    self.status[lbl] = level
                    if self.notify:
                        self.notify(lbl,self.status[lbl])

    def _parse_PW(self, resp: str) -> None:
        self._parse_many("PW",resp)

    def _parse_ECO(self, resp: str) -> None:
        self._parse_many("ECO",resp)

    def _parse_SI(self, resp: str) -> None:
        self._parse_many("SI",resp)

    def _parse_MU(self, resp: str) -> None:
        nval = resp == "ON"
        lbl = self.CMDS_DEFS["MU"].label
        if self.status[lbl] != nval:
            self.status[lbl] = nval
            if self.notify:
                self.notify(lbl,self.status[lbl])

    def _parse_CV(self, resp: str) -> None:
        """ Different here... Needs to be reset"""
        if resp=="END":
            self.cvend = True
            if self.notify:
                lbl = self.CMDS_DEFS["CV"].label
                self.notify(lbl,self.status[lbl])
        else:
            if self.cvend:
                self.status[self.CMDS_DEFS["CV"].label] = {}
                self.cvend = False
            spkr, level = resp.split(" ")

            if level:
                if len(level)>2:
                    level=int(level)/10
                else:
                    level=float(level)
            level -= 50
            for x in self.CMDS_DEFS["CV"].values:
                if x.value == spkr:
                    spkrname = cc_string(x.name)
                    break
            try:
                self.status[self.CMDS_DEFS["CV"].label][spkrname] = level
            except:
                logging.debug(f"Unknown speaker code {spkr}")

    def _parse_MS(self, resp: str) -> None:
        """ Different here... What we get is not what we send. So we try to transform
        the result through semi-cllever string manipulation
        """

        resp = resp.replace("+", " ")
        resp = " ".join([x.title() for x in resp.split(" ")])
        for old,new in SSTRANSFORM:
            resp = resp.replace(old,new)
        #Clean up spaces
        resp = re.sub(r'[_\W]+', ' ', resp)
        lbl = self.CMDS_DEFS["MS"].label
        if self.status[lbl] != resp:
            self.status[lbl]=resp
            if self.notify:
                self.notify(lbl,self.status[lbl])

    def _clean_fut(self,fut):
        for idx in range(len(self.queue)):
            if self.queue[idx][1] == fut:
                self.queue[idx][1].cancel()
                del(self.queue[idx])
                break

    async def _do_read(self):
        """ Keep on reading the info coming from the AVR"""

        asyncio.get_event_loop().create_task(self.refresh())
        while self.alive:
            data =b''
            while not data or data[-1] != ord('\r'):
                if self.queue:
                    try:
                        data += await asyncio.wait_for(self._reader.read(1), self._timeout)
                    except asyncio.TimeoutError:
                        #Gone
                        self.alive = False
                        self._writer.close()
                        await self._writer.wait_close()
                        break
                else:
                    data += await self._reader.read(1)

            logging.debug(f"Received: {data}")
            match = self._process_response(data.decode().strip("\r"))

            for idx in range(len(self.queue)):
                cmd, fut = self.queue[idx]
                if cmd == match:
                    fut.set_result(True)
                    del(self.queue[idx])
                    break
