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
from .enums import (
    InputSource,
    Power,
    SurroundMode,
    ChannelBias,
    EcoMode,
    AudioInput,
    PictureMode,
)

# Some replacement for the surround sound format
SSTRANSFORM = [
    ("Audio-", " "),
    ("Dd", "Dolby Digital "),
    ("DD", "Dolby Digital "),
    ("Dts", "DTS"),
    ["Mstr", "Master "],
    ("Dsur", "Digital Surround "),
    ("Mtrx", "Matrix"),
    ("Dscrt", "Discrete "),
    ("Mch", "Multi-Channel "),
    (" Es ", " ES "),
]
EXTRAS = ["SSINFAI"]


def cc_string(identifier: str) -> str:
    """ From https://stackoverflow.com/questions/29916065/how-to-do-camelcase-split-in-python """
    matches = re.finditer(
        ".+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)", identifier
    )
    return " ".join([m.group(0) for m in matches])


def only_int(val: str) -> str:
    return "".join(
        [x for x in val if x in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]]
    )


class AvrError(Exception):
    """Base class for all errors returned from an AVR."""

    pass


class AvrTimeoutError(AvrError):
    """A request to the AVR has timed out."""

    pass


async def avr_factory(
    name: str, host: str, port: int = 23, timeout: float = 3.0
) -> "MDAVR":
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

    def __init__(self, label: str, vals: Any):
        self.label = label
        self.values = vals


class MDAVR:
    """Connection to a Marantz AVR over Telnet.

    Uses `connect` to create a connection to the AVR.
    """

    CMDS_DEFS: Mapping[str, _CommandDef] = {
        "PW": _CommandDef("Power", Power),
        "ZM": _CommandDef("Main Zone", Power),
        "Z2": _CommandDef("Zone 2", Power),
        "Z3": _CommandDef("Zone 3", Power),
        "MU": _CommandDef("Muted", None),
        "Z2MU": _CommandDef("Z2 Muted", None),
        "Z3MU": _CommandDef("Z3 Muted", None),
        "MV": _CommandDef("Volume", None),
        "Z2MV": _CommandDef("Z2 Volume", None),
        "Z3MV": _CommandDef("Z3 Volume", None),
        "SI": _CommandDef("Source", InputSource),
        "Z2SI": _CommandDef("Z2 Source", InputSource),
        "Z3SI": _CommandDef("Z3 Source", InputSource),
        "MS": _CommandDef("Surround Mode", SurroundMode),
        "CV": _CommandDef("Channel Bias", ChannelBias),
        "PV": _CommandDef("Picture Mode", PictureMode),
        "ECO": _CommandDef("Eco Mode", EcoMode),
        "SSSOD": _CommandDef("Available Source", InputSource),
    }

    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    _timeout: float

    def __init__(
        self,
        name: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        timeout: float,
    ):
        self.name = name
        self._reader = reader
        self._writer = writer
        self._timeout = timeout
        self.status = {}
        self.maxvol = 98  # Good default ;)
        self.alive = True
        self.write_queue = asyncio.Queue()
        for x in self.CMDS_DEFS:
            if len(x) < 5:
                self.status[self.CMDS_DEFS[x].label] = "-"
        self.cvend = True
        self.notify = None
        self.mysources = []
        # Start reading
        self.wtask = asyncio.get_event_loop().create_task(self._do_write())
        self.rtask = asyncio.get_event_loop().create_task(self._do_read())
        self._get_capabilities()
        self.refresh()

    def _get_capabilities(self):
        """
        Here we try to get the various capabilities of the device connected.
        """
        # Let's get the available Sources
        self.write_queue.put_nowait(("SSSOD", " ?"))

    def _get_current(self, cmd):
        return self.status[self.CMDS_DEFS[cmd].label]

    def _get_list(self, cmd):
        return [cc_string(x.name) for x in list(self.CMDS_DEFS[cmd].values)]

    # API Starts here
    @property
    def power(self) -> Optional[Power]:
        """Power state of the AVR."""
        return self._get_current("PW")

    @property
    def zmain(self) -> Optional[Power]:
        """Power state of the AVR."""
        return self._get_current("ZM")

    @property
    def z2(self) -> Optional[Power]:
        """Power state of the AVR."""
        return self._get_current("Z2")

    @property
    def z3(self) -> Optional[Power]:
        """Power state of the AVR."""
        return self._get_current("Z3")

    @property
    def muted(self) -> Optional[bool]:
        """Boolean if volume is currently muted."""
        return self._get_current("MU")

    @property
    def z2_muted(self) -> Optional[bool]:
        """Boolean if volume is currently muted."""
        return self._get_current("Z2MU")

    @property
    def z3_muted(self) -> Optional[bool]:
        """Boolean if volume is currently muted."""
        return self._get_current("Z3MU")

    @property
    def volume(self) -> Optional[float]:
        """Volume level of the AVR zone (00..max_volume)."""
        return self._get_current("MV")

    @property
    def z2_volume(self) -> Optional[float]:
        """Volume level of the AVR zone (00..max_volume)."""
        return self._get_current("Z2MV")

    @property
    def z2_volume(self) -> Optional[float]:
        """Volume level of the AVR zone (00..max_volume)."""
        return self._get_current("Z2MV")

    @property
    def max_volume(self) -> Optional[float]:
        """Maximum volume level of the AVR zone."""
        return self.maxvol

    @property
    def source(self) -> str:
        """Name of the current input source."""
        return self._get_current("SI")

    @property
    def z2_source(self) -> str:
        """Name of the current input source."""
        return self._get_current("Z2SI")

    @property
    def z2_source(self) -> str:
        """Name of the current input source."""
        return self._get_current("Z3SI")

    @property
    def source_list(self) -> List[str]:
        """List of available input sources."""
        if self.mysources:
            return self.mysources
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
    def picture_mode(self) -> str:
        """Name of the current sound mode."""
        return self._get_current("PV")

    @property
    def picture_mode_list(self) -> List[str]:
        """List of available sound modes."""
        return self._get_list("PV")

    @property
    def eco_mode(self) -> str:
        """Current ECO mode."""
        return self._get_current("ECO")

    @property
    def eco_mode_list(self) -> List[str]:
        """List of available exo modes."""
        return self._get_list("ECO")

    @property
    def channels_bias(self) -> Mapping[str, float]:
        return self._get_current("CV")

    @property
    def channels_bias_list(self) -> List[str]:
        """List of currently available."""
        return [x for x in self._get_current("CV").keys()]

    def refresh(self) -> None:
        """Refresh all properties from the AVR."""

        for cmd_def in self.CMDS_DEFS:
            fut = self.write_queue.put_nowait((cmd_def, "?"))

    def turn_on(self) -> None:
        """Turn the AVR on."""
        self.write_queue.put_nowait(("PW", "ON"))

    def turn_off(self) -> None:
        """Turn the AVR off."""
        self.write_queue.put_nowait(("PW", "STANDBY"))

    def main_turn_on(self) -> None:
        """Turn the AVR on."""
        self.write_queue.put_nowait(("ZM", "ON"))

    def main_turn_off(self) -> None:
        """Turn the AVR off."""
        self.write_queue.put_nowait(("ZM", "OFF"))

    def z2_turn_on(self) -> None:
        """Turn the AVR on."""
        self.write_queue.put_nowait(("Z2", "ON"))

    def z2_turn_off(self) -> None:
        """Turn the AVR off."""
        self.write_queue.put_nowait(("Z2", "OFF"))

    def z3_turn_on(self) -> None:
        """Turn the AVR on."""
        self.write_queue.put_nowait(("Z3", "ON"))

    def z3_turn_off(self) -> None:
        """Turn the AVR off."""
        self.write_queue.put_nowait(("Z3", "OFF"))

    def mute_volume(self, mute: bool) -> None:
        """Mute or unmute the volume.

        Arguments:
        mute -- True to mute, False to unmute.
        """
        self.write_queue.put_nowait(("MU", _on_off_from_bool(mute)))

    def _zone_mute_volume(self, zone: str, mute: bool) -> None:
        """Mute or unmute the volume.

        Arguments:
        mute -- True to mute, False to unmute.
        """
        self.write_queue.put_nowait((zone, _on_off_from_bool(mute)))

    def z2_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the volume.

        Arguments:
        mute -- True to mute, False to unmute.
        """
        self._zone_mute_volume("Z2MU", mute)

    def z3_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the volume.

        Arguments:
        mute -- True to mute, False to unmute.
        """
        self._zone_mute_volume("Z3MU", mute)

    def set_volume(self, level: float) -> None:
        """Set the volume level.

        Arguments:
        level -- An integer value between 0 and `max_volume`.
        """
        if level > self.maxvol:
            level = maxvol
        if int(10 * level) % 10:
            # Needs to be a nultiple of 5
            level = int(5 * round(10 * level / 5))
        else:
            level = int(level)
        self.write_queue.put_nowait(("MV", f"{level:02}"))

    def volume_up(self) -> None:
        """Turn the volume level up one notch."""
        self._zone_volume("MV", "UP")

    def volume_down(self) -> None:
        """Turn the volume level down one notch."""
        self._zone_volume("MV", "DOWN")

    def z2_set_volume(self, level: float) -> None:
        """Set the volume level.

        Arguments:
        level -- An integer value between 0 and `max_volume`.
        """
        self._zone_set_volume("Z2", level)

    def z3_set_volume(self, level: float) -> None:
        """Set the volume level.

        Arguments:
        level -- An integer value between 0 and `max_volume`.
        """
        self._zone_set_volume("Z3", level)

    def z2_volume_up(self) -> None:
        """Turn the volume level down one notch."""
        self._zone_volume("Z2", "UP")

    def z3_volume_up(self) -> None:
        """Turn the volume level down one notch."""
        self._zone_volume("Z3", "UP")

    def z2_volume_down(self) -> None:
        """Turn the volume level down one notch."""
        self._zone_volume("Z2", "DOWN")

    def z3_volume_down(self) -> None:
        """Turn the volume level down one notch."""
        self._zone_volume("Z3", "DOWN")

    def set_channel_bias(self, chan: str, level: float) -> None:
        """Set the volume level.

        Arguments:
        chan  -- channel to set
        level -- A float value between -12.0 and +12.0
        """
        if chan not in self.channels_bias:
            logging.warning(f"Channel {chan} is not available right now.")
            return

        if self.channels_bias[chan] != level:
            chan = chan.replace(" ", "")
            level = level + 50  # 50 is 0dB
            if level < 38:
                level = 38
            elif level > 62:
                level = 62
            if int(10 * level) % 10:
                # Needs to be a nultiple of 5
                level = int(5 * round(10 * level / 5))
            else:
                level = int(level)

            cmd = None
            for x in self.CMDS_DEFS["CV"].values:
                if x.name == chan:
                    cmd = x.value
                    break
            if cmd:
                self.write_queue.put_nowait(("CV", f"{cmd} {level:02}"))
            else:
                logging.error(
                    f"Channel {chan} should exist. This should not have happened."
                )

    def channel_bias_up(self, chan: str) -> None:
        """Turn the volume level up one notch."""
        if chan not in self.channels_bias:
            logging.warning(f"Channel {chan} is not available right now.")
            return
        if self.channels_bias[chan] == 12:
            # We are at the limit. It won't respond
            logging.debugf(f"Channel {chan} it at the upper limit.")
            return

        chan = chan.replace(" ", "")
        cmd = None
        for x in self.CMDS_DEFS["CV"].values:
            if x.name == chan:
                cmd = x.value
                break
        if cmd:
            self.write_queue.put_nowait(("CV", f"{cmd} UP"))
        else:
            logging.error(
                f"Channel {chan} should exist. This should not have happened."
            )

    def channel_bias_down(self, chan: str) -> None:
        """Turn the volume level down one notch."""
        if chan not in self.channels_bias:
            logging.warning(f"Channel {chan} is not available right now.")
            return
        if self.channels_bias[chan] == -12:
            # We are at the limit. It won't respond
            logging.debugf(f"Channel {chan} it at the lowewr limit.")
            return

        chan = chan.replace(" ", "")
        cmd = None
        for x in self.CMDS_DEFS["CV"].values:
            if x.name == chan:
                cmd = x.value
                break
        if cmd:
            self.write_queue.put_nowait(("CV", f"{cmd} DOWN"))
        else:
            logging.error(
                f"Channel {chan} should exist. This should not have happened."
            )

    def channels_bias_reset(self):
        self.write_queue.put_nowait(("CV", "ZRL"))

    def select_source(self, source: str) -> None:
        """Select the input source."""
        try:
            source = self.CMDS_DEFS["SI"].values[source.replace(" ", "")]
        except:
            logging.warning(f"Warning: {source} is not a valid source")
            return
        self.write_queue.put_nowait(("SI", source.value))

    def z2_select_source(self, source: str) -> None:
        """Select the input source."""
        try:
            source = self.CMDS_DEFS["SI"].values[source.replace(" ", "")]
        except:
            logging.warning(f"Warning: {source} is not a valid source")
            return
        self.write_queue.put_nowait(("Z2", source.value))

    def z3_select_source(self, source: str) -> None:
        """Select the input source."""
        try:
            source = self.CMDS_DEFS["SI"].values[source.replace(" ", "")]
        except:
            logging.warning(f"Warning: {source} is not a valid source")
            return
        self.write_queue.put_nowait(("Z3", source.value))

    def select_sound_mode(self, mode: str) -> None:
        """Select the sound mode."""
        try:
            mode = self.CMDS_DEFS["MS"].values[mode.replace(" ", "")]
        except:
            logging.warning(f"Warning: {mode} is not a valid mode")
            return
        self.write_queue.put_nowait(("MS", mode.value))

    def select_picture_mode(self, mode: str) -> None:
        """Select the sound mode."""
        try:
            mode = self.CMDS_DEFS["PV"].values[mode.replace(" ", "")]
        except:
            logging.warning(f"Warning: {mode} is not a valid mode")
            return
        self.write_queue.put_nowait(("PV", mode.value))

    def select_eco_mode(self, mode: str) -> None:
        """Select the sound mode."""
        try:
            mode = self.CMDS_DEFS["ECO"].values[mode.replace(" ", "").title()]
        except:
            logging.warning(f"Warning: {mode} is not a valid eco  mode")
            return
        self.write_queue.put_nowait(("ECO", mode.value))

    def notifyme(self, func: Callable) -> None:
        """Register a callback for when an event happens. The callable should have 2 parameters,
        The label of the the changing value and the new value
        """
        self.notify = func

    def close(self):
        self.alive = False
        self._writer.close()
        self.rtask.cancel()
        self.wtask.cancel()
        logging.debug(f"Closed device {self.name}")

    # API ends here

    def _zone_volume(self, zone: str, uod: str) -> None:
        """Turn the volume level up one notch."""
        self.write_queue.put_nowait((zone, uod))

    def _zone_set_volume(self, zone: str, level: float) -> None:
        """Set the volume level.

        Arguments:
        zone -- The zone affected
        level -- An integer value between 0 and `max_volume`.
        """
        if level > self.maxvol:
            level = maxvol
        level = int(level)
        self.write_queue.put_nowait((zone, f"{level:02}"))

    async def _send_command(self, cmd: str, val: Any) -> asyncio.Future:
        tosend = f"{cmd}{val}\r"
        logging.debug(f"Sending {tosend}")
        self._writer.write(tosend.encode())
        await self._writer.drain()
        logging.debug("Write drained")

    def _process_response(self, response: str) -> Optional[str]:
        matches = [cmd for cmd in self.CMDS_DEFS.keys() if response.startswith(cmd)] + [
            cmd for cmd in EXTRAS if response.startswith(cmd)
        ]

        if not matches:

            return None

        if len(matches) > 1:
            matches.sort(key=len, reverse=True)
        match = matches[0]

        if getattr(self, "_parse_" + match, None):
            getattr(self, "_parse_" + match)(response.strip()[len(match) :])
        else:
            # A few special cases ... for now
            if response.startswith("SSINFAISFSV"):
                try:
                    sr = int(only_int(response.split(" ")[-1]))
                    if sr > 200:
                        sr = round(sr / 10, 1)
                    else:
                        sr = float(sr)
                    self.status["Sampling Rate"] = sr
                except Exception as e:
                    if response.split(" ")[-1] == "NON":
                        elf.status["Sampling Rate"] = "-"
                    else:
                        logging.debug(f"Error with sampling rate: {e}")
            else:
                self._parse_many(match, response.strip()[len(match) :])
                logging.debug(f"Warning _parse_{match} is not defined.")

        return match

    def _parse_many(self, cmd: str, resp: str) -> None:
        for x in self.CMDS_DEFS[cmd].values:
            if resp == x.value:
                lbl = self.CMDS_DEFS[cmd].label
                if self.status[lbl] != cc_string(x.name):
                    self.status[lbl] = cc_string(x.name)
                    if self.notify:
                        self.notify(lbl, self.status[lbl])

    def _parse_MV(self, resp: str) -> None:
        level = only_int(resp)

        if level:
            if len(level) > 2:
                level = int(level) / 10
            else:
                level = float(level)

            if resp.startswith("MAX"):
                self.maxvol = level
            else:
                lbl = self.CMDS_DEFS["MV"].label
                if self.status[lbl] != level:
                    self.status[lbl] = level
                    if self.notify:
                        self.notify(lbl, self.status[lbl])

    # def _parse_PW(self, resp: str) -> None:
    # self._parse_many("PW", resp)

    # def _parse_ECO(self, resp: str) -> None:
    # self._parse_many("ECO", resp)

    # def _parse_SI(self, resp: str) -> None:
    # self._parse_many("SI", resp)

    # def _parse_PV(self, resp: str) -> None:
    # self._parse_many("PV", resp)

    def _parse_MU(self, resp: str) -> None:
        nval = resp == "ON"
        lbl = self.CMDS_DEFS["MU"].label
        if self.status[lbl] != nval:
            self.status[lbl] = nval
            if self.notify:
                self.notify(lbl, self.status[lbl])

    def _parse_Z2MU(self, resp: str) -> None:
        nval = resp == "ON"
        lbl = self.CMDS_DEFS["Z2MU"].label
        if self.status[lbl] != nval:
            self.status[lbl] = nval
            if self.notify:
                self.notify(lbl, self.status[lbl])

    def _parse_Z3MU(self, resp: str) -> None:
        nval = resp == "ON"
        lbl = self.CMDS_DEFS["Z3MU"].label
        if self.status[lbl] != nval:
            self.status[lbl] = nval
            if self.notify:
                self.notify(lbl, self.status[lbl])

    def _parse_zone(self, zone: str, resp: str) -> None:
        """ Naturaly, those idiots had tn  overload the zone prefix for
        power, volume and source...
        """
        if resp in ["ON", "OFF"]:
            self._parse_many(zone, resp)
            return

        if resp.startswith("SMART"):
            # not handled
            return

        if resp.startswith("FAVORITE"):
            # not handled, learn to spell!
            return

        try:
            logging.debug(f"Checking level for {zone}")
            level = only_int(resp)
            if len(level) > 2:
                level = int(level) / 10
            else:
                level = float(level)

            lbl = self.CMDS_DEFS[zone + "MV"].label
            if self.status[lbl] != level:
                self.status[lbl] = level
                if self.notify:
                    self.notify(lbl, self.status[lbl])
        except:
            # Probably the source
            try:
                self._parse_many(zone + "SI", resp)
            except Exception as e:
                logging.debug(f"Failed when parsing {zone}: {e}")

    def _parse_Z2(self, resp: str) -> None:
        self._parse_zone("Z2", resp)

    def _parse_Z3(self, resp: str) -> None:
        self._parse_zone("Z3", resp)

    def _parse_CV(self, resp: str) -> None:
        """ Different here... Needs to be reset"""
        if resp == "END":
            self.cvend = True
            if self.notify:
                lbl = self.CMDS_DEFS["CV"].label
                self.notify(lbl, self.status[lbl])
        else:
            if self.cvend:
                self.status[self.CMDS_DEFS["CV"].label] = {}
                self.cvend = False
            spkr, level = resp.split(" ")

            if level:
                if len(level) > 2:
                    level = int(level) / 10
                else:
                    level = float(level)
            level -= 50
            for x in self.CMDS_DEFS["CV"].values:
                if x.value == spkr:
                    spkrname = cc_string(x.name)
                    break
            try:
                self.status[self.CMDS_DEFS["CV"].label][spkrname] = level
            except:
                logging.debug(f"Unknown speaker code {spkr}")

    def _parse_SSSOD(self, resp: str) -> None:
        """ Different here..."""
        if resp == " END":
            self.mysources.sort()
            logging.debug(f"My source is now {self.mysources}")
            return
        si, f = resp.split(" ")
        if f == "USE":
            for x in self.CMDS_DEFS["SSSOD"].values:
                if si == x.value:
                    self.mysources.append(cc_string(x.name))
                    break

    def _parse_MS(self, resp: str) -> None:
        """ Different here... What we get is not what we send. So we try to transform
        the result through semi-cllever string manipulation
        """

        resp = resp.replace("+", " ")
        resp = " ".join([x.title() for x in resp.split(" ")])
        for old, new in SSTRANSFORM:
            resp = resp.replace(old, new)
        # Clean up spaces
        resp = re.sub(r"[_\W]+", " ", resp)
        lbl = self.CMDS_DEFS["MS"].label
        if self.status[lbl] != resp:
            self.status[lbl] = resp
            if self.notify:
                self.notify(lbl, self.status[lbl])

    async def _do_read(self):
        """ Keep on reading the info coming from the AVR"""

        while self.alive:
            data = b""
            while not data or data[-1] != ord("\r"):
                char = await self._reader.read(1)
                if char == b"":
                    break
                data += char

            if data == b"":
                # Gone
                self.close()
                return

            logging.debug(f"Received: {data}")
            try:
                match = self._process_response(data.decode().strip("\r"))
            except Exception as e:
                logging.debug(f"Problem processing respionse: {e}")

    async def _do_write(self):
        """ Keep on reading the info coming from the AVR"""

        while self.alive:
            cmd, param = await self.write_queue.get()
            if cmd:
                await self._send_command(cmd, param)
            self.write_queue.task_done()
