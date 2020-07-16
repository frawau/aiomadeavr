#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# This application is an asyncio library to discover HEOS devices
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

import aiohttp
import asyncio
import logging
import socket
import struct
from xml.dom.minidom import parseString

MULTICAST_PORT = 1900
MULTICAST_ADDR = "239.255.255.250"
MULTICAST6_ADDR = "ff05::c"
# MULTICAST6_ADDR = "ff08::c"
# MULTICAST6_ADDR = "ff0e::c"


class DiscoveryClientProtocol:
    def __init__(self, loop, addr=MULTICAST_ADDR, callb=None, timeout=5):
        """Class representing a device discovery protocol

        :param loop: The asyncio loop
        :type name: asyncio.unix_events._UnixSelectorEventLoop
        :param addr: the broadcast address.
        :type addr: str
        :param callb: callback to register discovered instances
        :type callb: function
        :returns: protocol instance.
        :rtype: DiscoveryClientProtocol

    """
        """
        Here we
        """
        self.loop = loop
        self.transport = None
        self.addr = addr
        self.timeout = timeout
        self.callb = callb

    def connection_made(self, transport):
        """
        Once connected, broadcast the SSDP discovery message
        """

        self.transport = transport
        sock = self.transport.get_extra_info("socket")
        addrinfo = socket.getaddrinfo(self.addr, None)[0]
        ttl = struct.pack("@i", 1)
        if addrinfo[0] == socket.AF_INET:  # IPv4
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        else:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, ttl)
        request = "\r\n".join(
            (
                "M-SEARCH * HTTP/1.1",
                "HOST:{}:{}",
                "ST:upnp:rootdevice",
                # "ST:ssdp:all",
                "MX:2",
                'MAN:"ssdp:discover"',
                "",
                "",
            )
        ).format(self.addr, MULTICAST_PORT)
        self.transport.sendto(request.encode(), (self.addr, MULTICAST_PORT))
        self.loop.call_later(self.timeout, self.endme)

    def datagram_received(self, data, addr):
        """
            After receiving a response to our discovery broadcast, let's
            make surte this is a heos device.
        """
        if "denon-heos" in data.decode().lower():
            for x in data.decode("ascii").split("\r\n"):
                if x.upper().startswith("LOCATION:"):
                    loc = x.replace("LOCATION:", "").strip()
            # We got a possible match. Let's investiate further
            self.loop.create_task(self.get_info(addr[0], loc))

    def error_received(self, exc):
        pass

    def connection_lost(self, exc):
        """
            Dead, we are
        """
        self.transport.close()

    def endme(self):
        """
            Ending discovery
        """
        self.transport.close()

    async def get_info(self, addr, url):
        """
            Let's analyse the data provided by the device
            answering our discovery call

                :param addr: The device IP address
                :type name: str
                :param url: The location URL provided by the device.
                :type url: str
                :returns: Nothing
                :rtype: None
        """

        def getText(nodelist):
            rc = []
            for node in nodelist:
                if node.nodeType == node.TEXT_NODE:
                    rc.append(node.data)
            return "".join(rc)

        try:
            txt = None
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    txt = await response.text()
            if txt:
                data = parseString(txt)
                dev = data.getElementsByTagName("device")[0]
                rdata = {"ip": addr}
                rdata["brand"] = getText(
                    dev.getElementsByTagName("manufacturer")[0].childNodes
                )
                rdata["model"] = getText(
                    dev.getElementsByTagName("modelName")[0].childNodes
                )
                rdata["serial"] = getText(
                    dev.getElementsByTagName("serialNumber")[0].childNodes
                )
                rdata["name"] = getText(
                    dev.getElementsByTagName("friendlyName")[0].childNodes
                )
                logging.debug(f"Got device: {rdata}")
                if self.callb:
                    self.callb(rdata)
        except Exception as e:
            logging.error(f"Error: Error when parsing location XML: {e}")


async def start_discovery(addr=MULTICAST_ADDR, callb=None):
    loop = asyncio.get_event_loop()
    addrinfo = socket.getaddrinfo(MULTICAST_ADDR, None)[0]
    sock = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
    connect = loop.create_datagram_endpoint(
        lambda: DiscoveryClientProtocol(loop, MULTICAST_ADDR, callb=callb), sock=sock
    )

    await connect


if __name__ == "__main__":
    import asyncio as aio

    def cb(data):
        print("Got device {}".format(data))

    loop = aio.get_event_loop()
    loop.run_until_complete(start_discovery(MULTICAST_ADDR, cb))
    try:
        loop.run_until_complete(aio.sleep(6))
    except:
        pass
    finally:
        loop.close()
