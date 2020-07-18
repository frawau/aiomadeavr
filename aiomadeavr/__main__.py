#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# This application is an example on how to use aiomadeavr
#
# Copyright (c) 2020 François Wautier
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
import sys
import asyncio as aio
import aiomadeavr as avr
from functools import partial
import argparse
import logging


def quick_print(val, depth=1):
    if isinstance(val, dict):
        for k, v in val.items():
            if isinstance(v, dict):
                print("\t" * depth + k + ": ")
                quick_print(v, depth + 1)
            else:
                print("\t" * depth + f"{k}:\t{v}")


# Simple device control from console
class devices:
    """ A simple class with a register and  unregister methods
    """

    def __init__(self, debug):
        self.devices = {}
        self.doi = None  # device of interest
        self.secondary = None  # Either "source", "surround", or channel
        self.debug = debug

    def register(self, info):
        if "serial" in info and info["serial"].lower() not in self.devices:
            aio.create_task(self.set_device(info))
        else:
            if not self.devices[info["serial"].lower()].alive:
                aio.create_task(self.set_device(info))

    def unregister(self, mac):
        if mac.lower() in self.devices:
            logging.debug("%s is gone" % self.devices[mac.lower()].name)
            self.devices[mac.lower()].stop()
            del self.devices[mac.lower()]

    async def set_device(self, info):
        logging.debug(f"Adding {info}")
        try:
            newdev = await avr.avr_factory(info["name"], info["ip"])
            if newdev:
                self.devices[info["serial"].lower()] = newdev
                if self.debug:
                    self.devices[info["serial"].lower()].notifyme(notification)
        except:
            logging.warning(f"Could not connect to {info['ip']}.")

    def stop(self):
        for dev in self.devices.values():
            dev.close()


def readin():
    """Reading from stdin and displaying menu"""

    selection = sys.stdin.readline().strip("\n")

    loaddr = [x for x in MyDevices.devices.keys()]
    loaddr.sort()
    lov = [x for x in selection.split(" ") if x != ""]
    if lov:
        if MyDevices.doi:
            if MyDevices.secondary:
                if MyDevices.secondary == "source":
                    loi = MyDevices.doi.source_list
                    loi.sort()
                    try:
                        sel = int(lov[0]) - 1
                        if sel >= 0 and sel < len(loi):
                            source = loi[sel]
                            MyDevices.doi.select_source(source)
                        else:
                            print("\nError: Source selection incorrect.\n")
                    except:
                        print("\nError: Source selection must be a number.\n")
                elif MyDevices.secondary == "surround":
                    loi = MyDevices.doi.sound_mode_list
                    loi.sort()
                    try:
                        sel = int(lov[0]) - 1
                        if sel >= 0 and sel < len(loi):
                            mode = loi[sel]
                            MyDevices.doi.select_sound_mode(mode)
                        else:
                            print("\nError: Surround Mode  selection incorrect.\n")
                    except:
                        print("\nError: Surround Mode selection must be a number.\n")
                elif MyDevices.secondary == "channel":
                    loi = MyDevices.doi.channels_bias_list
                    loi.sort()
                    try:
                        sel = int(lov[0]) - 1
                        if sel == len(loi):
                            MyDevices.doi.channels_bias_reset()
                        elif sel >= 0 and sel < len(loi):
                            if lov[1].lower() == "up":
                                MyDevices.doi.channel_bias_up(loi[sel])
                            elif lov[1].lower() == "down":
                                MyDevices.doi.channel_bias_down(loi[sel])
                            else:
                                level = float(lov[1])
                                MyDevices.doi.set_channel_bias(loi[sel], level)
                    except:
                        print(
                            "\nError: Channel Bias meeds a channel and a level (float, up or down).\n"
                        )
                elif MyDevices.secondary == "picture":
                    loi = MyDevices.doi.picture_mode_list
                    loi.sort()
                    try:
                        sel = int(lov[0]) - 1
                        if sel >= 0 and sel < len(loi):
                            mode = loi[sel]
                            MyDevices.doi.select_picture_mode(mode)
                        else:
                            print("\nError: Picture mode selection incorrect.\n")
                    except:
                        print("\nError: Picture mode selection must be a number.\n")

                MyDevices.doi = None
                MyDevices.secondary = None

            else:
                # try:
                if int(lov[0]) == 0:
                    MyDevices.doi = None
                elif int(lov[0]) == 1:
                    if len(lov) > 1:
                        if lov[1].lower() in ["1", "on", "true"]:
                            MyDevices.doi.turn_on()
                        else:
                            MyDevices.doi.turn_off()
                        MyDevices.doi = None
                    else:
                        print("Error: For power you must indicate on or off\n")
                elif int(lov[0]) == 2:
                    MyDevices.doi.mute_volume(not MyDevices.doi.is_volume_muted)
                    MyDevices.doi = None
                elif int(lov[0]) == 3:
                    if len(lov) > 1:
                        if lov[1].lower() == "up":
                            MyDevices.doi.volume_up()
                        elif lov[1].lower() == "down":
                            MyDevices.doi.volume_down()
                        else:
                            try:
                                lvl = float(lov[1])
                                MyDevices.doi.set_volume(lvl)
                            except:
                                print(f"Error: {lov[1]} is not a float.")
                                print(
                                    "Error: For volume you must specify 'up', 'down' or a float value.\n"
                                )
                    else:
                        print(
                            "Error: For volume you must specify 'up', 'down' or a float value.\n"
                        )
                    MyDevices.doi = None

                elif int(lov[0]) == 4:
                    MyDevices.secondary = "source"
                    los = MyDevices.doi.source_list
                    los.sort()
                    print("Select source for {}:".format(MyDevices.doi.name))
                    idx = 1
                    for src in los:
                        print(f"\t[{idx}]\t{src}")
                        idx += 1
                elif int(lov[0]) == 5:
                    MyDevices.secondary = "surround"
                    los = MyDevices.doi.sound_mode_list
                    los.sort()
                    print("Select sound mode for {}:".format(MyDevices.doi.name))
                    idx = 1
                    for src in los:
                        print(f"\t[{idx}]\t{src}")
                        idx += 1
                elif int(lov[0]) == 6:
                    MyDevices.secondary = "channel"
                    los = MyDevices.doi.channels_bias_list
                    los.sort()
                    print("Select channel bias mode for {}:".format(MyDevices.doi.name))
                    idx = 1
                    for src in los:
                        print(f"\t[{idx}]\t{src} <level>|up|down")
                        idx += 1
                    print(f"\t[{idx}]\tReset all channels")
                elif int(lov[0]) == 7:
                    MyDevices.secondary = "picture"
                    los = MyDevices.doi.picture_mode_list
                    los.sort()
                    print("Select picture mode for {}:".format(MyDevices.doi.name))
                    idx = 1
                    for src in los:
                        print(f"\t[{idx}]\t{src}")
                        idx += 1

                elif int(lov[0]) == 8:
                    if lov[1].strip().lower() in ["on", "off", "auto"]:
                        MyDevices.doi.select_eco_mode(lov[1].strip())
                    else:
                        print(
                            "\nError: Eco mode must be one of 'on', 'off' or 'auto'..\n"
                        )
                    MyDevices.doi = None
                elif int(lov[0]) == 9:
                    print(f"Status for {MyDevices.doi.name}")
                    quick_print(MyDevices.doi.status)
                    MyDevices.doi = None
                # except:
                # print ("\nError: Selection must be a number.\n")
        else:
            try:
                if int(lov[0]) > 0:
                    if int(lov[0]) <= len(MyDevices.devices):
                        MyDevices.doi = MyDevices.devices[loaddr[int(lov[0]) - 1]]
                    else:
                        print("\nError: Not a valid selection.\n")

            except:
                print("\nError: Selection must be a number.\n")

    if MyDevices.doi:
        if MyDevices.secondary is None:
            print("Select Function for {}:".format(MyDevices.doi.name))
            print("\t[1]\tPower (0 or 1)")
            print("\t[2]\tToggle Mute")
            print("\t[3]\tVolume [float val|up|down]")
            print("\t[4]\tSource")
            print("\t[5]\tSurround Mode")
            print("\t[6]\tChannel Bias")
            print("\t[7]\tPicture Mode")
            print("\t[8]\tEco mode (on|off|auto)")
            print("\t[9]\tInfo")
            print("")
            print("\t[0]\tBack to device selection")
    else:
        idx = 1
        print("Select Device:")
        for x in loaddr:
            print("\t[{}]\t{}".format(idx, MyDevices.devices[x].name or x))
            idx += 1
    print("")
    print("Your choice: ", end="", flush=True)


def notification(lbl, value):
    print(f"Value for {lbl} changed to {value}")


parser = argparse.ArgumentParser(
    description="Track and interact with Marantz/Denon devices."
)
parser.add_argument(
    "-v",
    "--verbose",
    default=False,
    action="store_true",
    help="Print more information.",
)
parser.add_argument(
    "-d", "--debug", default=False, action="store_true", help="Print debug information."
)

try:
    opts = parser.parse_args()
except Exception as e:
    parser.error("Error: " + str(e))

if opts.debug:
    logging.basicConfig(level=logging.DEBUG)
elif opts.verbose:
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=logging.ERROR)


MyDevices = devices(opts.debug or opts.verbose)
loop = aio.get_event_loop()
loop.run_until_complete(avr.start_discovery(callb=MyDevices.register))
try:
    loop.add_reader(sys.stdin, readin)
    print('Hit "Enter" to start')
    print("Use Ctrl-C to quit")
    loop.run_forever()
except:
    print("Exiting at user's request.")
finally:
    MyDevices.stop()
    loop.remove_reader(sys.stdin)
    loop.run_until_complete(aio.sleep(2))
    loop.close()
