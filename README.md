# aiomadeavr

A library/utility to control Marantz/Denon devices over the telnet port.

[![PyPI version fury.io](https://badge.fury.io/py/aiomadeavr.svg)](https://pypi.python.org/pypi/aiomadeavr)
[![MIT license](https://img.shields.io/badge/License-MIT-blue.svg)](https://lbesson.mit-licen)
[![GITHUB-BADGE](https://github.com/frawau/aiomadeavr/workflows/black/badge.svg)](https://github.com/psf/black)


# Installation

We are on PyPi so

    pip3 install aiomadeavr

# Why?

Another project [aio_marantz_avr](https://github.com/silvester747/aio_marantz_avr) targets the
same problem. Unfortunately, it has a few shortcomings for my intended use. For one thing, whilst
it is using asyncio, it is not really asynchronous as  you need to poll the device to get data. Second,
there is no automatic discovery of devices.

So I decided to write my own.

Note that I lifted some code from [aio_marantz_avr](https://github.com/silvester747/aio_marantz_avr), but
in the end, it is so far from the original that it made no sense to create this as a PR.

# Running

This has been tested with a Marantz SR7013 receiver.

Although aiomadeavr is meant to be use as a library, the module can be ran, just do


    python3 -m aiomadeavr

After a moment, if you type "enter", you should see a list of the device that have been
discovered. You will be able to power the device on/off, mute/unmute it, set the volume, choose
the source and select the surround mode. You will also be able to change the sound channels bias.

# Discovery

There is actually no way to discover the telnet service of those devices. So aiomadeavr cheats.
As far as I can tell all recent Marantz/Denon networked devices support Denon's
[HEOS](https://www.denon.com/en-gb/heos). That service advertises itself over the [Simple Service Discovery Protocol](https://en.wikipedia.org/wiki/Simple_Service_Discovery_Protocol). Discovery looks for those services
and, hopefoolly, the devices we can telnet to will answer the Denon/Marantz serial protocol.

# Documentation

Here are the exposed API functions and object

## avr_factory

This is a coroutine. It is how one creates devices instances.

Parameters are:

    name: The friendly name of the instances, a string
    addr: The IP asddress, a string

These 2 are required, there are also 2 optional parameters:

    port: The port to connect to. An integer. Default is 23
    timeout: A timeout, in seconds, for communicatiojn with the device. A float, default 3.0

If anything goes wrong, avr_factory will return None. If things go right, it will return an MDAVR object

## MDAVR

This is the class used to communicate with the device.

When created with avr_factory, the object will connect to the device and start reading the information
coming from the device. It will then issue a list of command to get the current state of the device.

All communications with a device must be performed through a MDAVR instance.

Here are the exposed attributes and method of the MDAVR class.

### String Attr: name

The friendly name of the device. This was passed to avr_factory at creation time.

### Dictionary Attr: status

Current status of the device. Below is a pretty printed example:

        Power:  On
        Mute:   False
        Volume: 68.0
        Source: Bluray
        Surround Mode:  Stereo
        Channel Bias:
                Front Left:     0.0
                Front Right:    0.0
        Eco Mode:       Off


### String Attr: power

Current status status of the device, one of 'On' or 'Standby'

### Bool Attr: muted

Current "muted" status of the device: True or False

### Float Attr: volume

Current master volume of the device. From 0.0 to max_volume by 0,5 increments

### Float Attr: max_volume

Maximum of the volume range.

### String Attr: source

Current source of the device, for instance Bluray, CD, Set Top Box,...

### List Attr: source_list

List of all the possible sources. When setting a source, the name MUST BE in this list.

Not all sources are available to all devices. aiomadeave will try to get the list of inputs available to the device.

### String Attr: sound_mode

Current sound processing mode, for instance: Stereo, DTS, Pure Direct,...

### List Attr: sound_mode_list

List of all the possible sound_mode. When setting a sound_mode, the name MUST BE in this list.

Not all sound_mode are available to all devices.

### String Attr: picture_mode

Current video processing mode, for instance: Custum, Vivid, ISF Day,...

### List Attr: picture_mode_list

List of all the possible picture_mode. When setting a picture_mode, the name MUST BE in this list.

Not all picture_mode are available to all devices.

### String Attr: eco_mode

Current economy mode setting, one of 'On', 'Off' or 'Auto'

### List Attr: eco_mode_list

List of all the possible economy mode settings. When setting the economy mode, the name MUST BE in this list.

Economy mode is not available on all devices.

### Dictionary Attr: channels_bias

The bias for all the currently available channels. The key is the channel name, and the
value is the bias as a float. The bias is between -12 dB and +12 dB

### List Attr: channels_bias_list

List of all the possible channels for which a bias can be set. When setting a channel bias the name MUST BE in this list.

Note that this list is dynamic has it depends on the sound mode. Values are like: Front Right, Surrond Left,...

### Method: refresh

No parameter.

Ask the device to query its current status. Returns None but may raise AvrTimeoutError.

### Method: turn_on

No parameter.

Turn on the device. Returns None but may raise AvrTimeoutError.

### Method: turn_off

No parameter.

Turn off the device. Returns None but may raise AvrTimeoutError

Note that the associated value is "Standby". It may be "Off" for some devices.

### Method: mute_volume

One parameter:

    mute: boolean

Returns None but may raise AvrTimeoutError.

### Method: set_volume

One parameter:

    level: float, valuer between 0.0 and 98.0 in 0.5 increments

Set the volume level.

Returns None but may raise AvrTimeoutError.


### Method: volume_up

No parameter.

Raise the volume level by 0.5

Returns None but may raise AvrTimeoutError.

### Method: volume_down

No parameter.

Lower the volume level by 0.5

Returns None but may raise AvrTimeoutError \.

### Method: set_channel_bias

Two parameter:

    chan: The channel name. Must be in channels_bias_list
    level: float, valuer between -12.0 and 12.0 in 0.5 increments

Set the bias level for the specified channel.

Returns None but may raise AvrTimeoutError.

### Method: channel_bias_up

One parameter:

    chan: The channel name. Must be in channels_bias_list

Raises the bias level for the specified channel by 0.5

Returns None but may raise AvrTimeoutError.

### Method: channel_bias_down

One parameter:

    chan: The channel name. Must be in channels_bias_list

Lower the bias level for the specified channel by 0.5

Returns None but may raise AvrTimeoutError.

### Method: channel_bias_reset

No parameter.

Reset all the channels' bias to 0.0

Returns None but may raise AvrTimeoutError.

### Method: select_source

One parameter:

    source: The source name. Must be in source_list

Make the source the current active one for the Main Zone

Returns None but may raise AvrTimeoutError.

### Method: select_sound_mode

One parameter:

    mode: The mode name. Must be in sound_mode_list

Set the sound mode for the active zone. The name of the sound mode
in the status may not be the same as the one set. For instance, setting 'Auto' may lead to a
'Stereo' mode.

Returns None but may raise AvrTimeoutError.

### Method: select_picture_mode

One parameter:

    mode: The mode name. Must be in picture_mode_list

Set the picture mode for the active zone.

Returns None but may raise AvrTimeoutError.

### Method: select_eco_mode

One parameter:

    mode: The mode name. Must be in eco_mode_list

Set the eco mode for the device.

Returns None but may raise AvrTimeoutError.

### Method: notifyme

One parameter:

    func: A callable with 2 parameters:

        lbl: The name of the property, a key in status
        value: The new value

This function register a callable to be called when one
of the status value changes. For 'Channel Bias' it is called
everytime the channel bias info is received.

## Coroutine start_discovery

One parameter:

    addr: The multicast address to use for discovery, by default this is the multicast address for SSDP discovery.
    callb: A callable. It is called when and HEOS service is discoverd. The callablew must accept one parameter, a dictionary with the following keys:

        ip: ip address of the device
        name: friendly name
        model: The device model
        serial: the device serial number


# Caveat

Trying to set the current value will often result in AvrTimeoutError exception. The device will simply not respond to that and will secretly despise you.

The channel bias list may get out of sync when setting the sound mode to 'Auto'. It looks like there is a delay before that information is sent.

# Afterthoughts

The module uses asyncio Streams. I think using protocols may have been a wiser choice.

~~Currently, most of the coroutine of the MDAVR object generate a future and wait for it. Not sure it is a good idea. May be removed in the future. Oh, wait!~~

All that silly use of future has now been cleaned up.





