import os
from pydantic import BaseModel, field_validator
from fastapi import FastAPI, HTTPException, Body
from typing import List, Optional
from netifaces import interfaces, ifaddresses, AF_INET
from ipaddress import IPv4Network, IPv4Address
from scapy.all import arping

tags = [
    {
        "name": "Interfaces Information",
        "description": "The following item below returns the default interface to where the emulation will be applied "
                       "whenever there is no interface given by the user. It also provides information about what "
                       "the system interfaces are.",
    },
    {
        "name": "Traffic Control status",
        "description": "This actions let the user know what is applied and active now in the traffic control options. "
                       "Only options that are not in the default state will be shown.",
    },
    {
        "name": "Arp scan",
        "description": "This section lets the user get IP addresses that answered during the scanning process. "
                       "Arp scan is performed by using the Scapy python library.",
        "externalDocs": {
            "description": "Scapy documentation",
            "url": "https://scapy.net",
        },
    },
    {
        "name": "Network Emulation",
        "description": "This section gives the user the ability of making changes to the traffic control configuration "
                       "by using the Linux tc queuing discipline and filter options. ",
        "externalDocs": {
            "description": "Linux tc documentation",
            "url": "https://man7.org/linux/man-pages/man8/tc.8.html",
        },
    },
    {
        "name": "Remove Network Emulation",
        "description": "It is crucial to delete the traffic control root after ending its use"
    },
    {
        "name": "Change Network Emulation parameters",
        "description": "This section gives the user the ability of replacing a traffic control root parameters "
                       "that is already active by using the Linux tc queuing discipline and filter options. ",
        "externalDocs": {
            "description": "Linux tc documentation",
            "url": "https://man7.org/linux/man-pages/man8/tc.8.html",
        },
    },
    {
        "name": "Change Network Emulation target IPs",
        "description": "This section gives the user the ability of adding and removing from the traffic control root "
                       "target IPs by using the Linux tc queuing discipline and filter options. ",
        "externalDocs": {
            "description": "Linux tc documentation",
            "url": "https://man7.org/linux/man-pages/man8/tc.8.html",
        },
    },
]

app = FastAPI(title='Network Emulation API', description='The emulation is done by using linux traffic control '
                                                         '(specifically queuing discipline and filter options)',
              version='1.0', openapi_tags=tags)


def sudo():
    if os.getuid() != 0:
        print("Sudo is required for the program to work properly (Usage: 'sudo ./NetJem').")
        exit()


sudo()


def device_interfaces():
    all_interfaces = interfaces()
    system_interfaces = set()
    for interface in all_interfaces:
        if interface == 'lo' or interface == 'loopback':
            pass
        else:
            system_interfaces.add(interface)
    return system_interfaces


def default_interface():
    all_interfaces = interfaces()
    for interface in all_interfaces:
        if interface == 'lo' or interface == 'loopback':
            pass
        else:
            return interface
    raise HTTPException(status_code=400, detail='No system interfaces found (excluding loopback)')


@app.get('/interfaces_info', tags=['Interfaces Information'])
def interfaces_interfaces():
    return {'Default interface': default_interface(), 'All system interfaces': device_interfaces()}


def get_active_ips_from_terminal(interface):
    filter_output = list(map(str, os.popen(f'tc f show dev {interface}').readlines()[:]))
    ips = list()
    for filter_line in filter_output:
        seen_match = False
        filter_words = filter_line.split(' ')
        for filter_word in filter_words:
            if seen_match:
                ip_split = []
                for i in range(4):
                    ip_split.append(str(int(filter_word[2 * i:2 * i + 2], 16)))
                ip = '.'.join(ip_split)
                ips.append(ip)
                seen_match = False

            if filter_word == 'match':
                seen_match = True
    ips = sorted(ips, key=IPv4Address)
    return ips


def get_parameters_from_terminal():
    netem_parameters = {}
    qdisc_output = list(map(str, os.popen('tc q').readlines()[:]))
    first_seen_ips = True
    for line in qdisc_output:
        interface = None
        seen_dev = netem_applied = selected_ips = False
        line = line.replace('\n', '')
        words = line.split(' ')
        for word in words:

            if seen_dev:
                interface = word
                seen_dev = False
            if word == 'dev':
                seen_dev = True

            if word == 'netem':
                netem_applied = True

            if word == 'prio':
                selected_ips = True

        if selected_ips:
            if first_seen_ips:
                netem_parameters['target_ips'] = {interface: list()}
                first_seen_ips = False
            netem_parameters['target_ips'][interface] = get_active_ips_from_terminal(interface)

        if netem_applied:
            netem_parameters[interface] = {}
            seen_limit = seen_loss = seen_duplicate = seen_corrupt = seen_rate = seen_slot = seen_distribution \
                = seen_packets = False

            for word in words:

                if seen_limit:
                    netem_parameters[interface]['limit'] = word
                    seen_limit = False

                elif seen_loss:
                    netem_parameters[interface]['loss'] = word
                    seen_loss = False

                elif seen_duplicate:
                    netem_parameters[interface]['duplicate'] = word
                    seen_duplicate = False

                elif seen_corrupt:
                    netem_parameters[interface]['corrupt'] = word
                    seen_corrupt = False

                elif seen_rate:
                    netem_parameters[interface]['rate'] = word
                    seen_rate = False

                elif seen_slot:
                    if word == 'distribution':
                        netem_parameters[interface]['distribution'] = 'normal'
                        seen_distribution = True
                        continue
                    elif not seen_distribution:
                        netem_parameters[interface]['distribution'] = 'uniform'
                        seen_distribution = True
                        continue
                    netem_parameters[interface]['delay'] = word
                    seen_slot = False

                elif seen_packets:
                    netem_parameters[interface]['packets'] = word
                    seen_packets = False

                if word == 'limit':
                    seen_limit = True
                elif word == 'loss':
                    seen_loss = True
                elif word == 'duplicate':
                    seen_duplicate = True
                elif word == 'corrupt':
                    seen_corrupt = True
                elif word == 'rate':
                    seen_rate = True
                elif word == 'slot' or word == 'delay':
                    seen_slot = True
                elif word == 'packets':
                    seen_packets = True

    return netem_parameters


@app.get('/all_traffic_control', tags=['Traffic Control status'])
def all_tc_status():
    netem_parameters = get_parameters_from_terminal()
    if len(netem_parameters) == 0:
        return 'No active Network Emulation found'
    return netem_parameters


@app.get('/parameters', tags=['Traffic Control status'])
def parameters_tc_status():
    netem_parameters = get_parameters_from_terminal()
    if len(netem_parameters) == 0:
        return 'No active Network Emulation found'
    if 'target_ips' in netem_parameters:
        netem_parameters.pop('target_ips')
    return netem_parameters


@app.get('/ip', tags=['Traffic Control status'])
def ip_tc_status():
    netem_parameters = get_parameters_from_terminal()
    if len(netem_parameters) == 0:
        return 'No active Network Emulation found'
    return netem_parameters.get('target_ips')


def check_interface(interface):
    system_interfaces = device_interfaces()
    if interface not in system_interfaces:
        raise HTTPException(status_code=401, detail=f'Interface not found. System interfaces are: {system_interfaces}')


@app.get('/{interface}', tags=['Traffic Control status'])
def all_selected_interface_tc_status(interface: str):
    check_interface(interface)
    netem_parameters = get_parameters_from_terminal()
    parameters = netem_parameters.get(interface)
    if not parameters:
        return f'No active Network Emulation found for interface {interface}'
    if 'target_ips' in netem_parameters:
        netem_parameters_selected_interface = [netem_parameters['target_ips'].get(interface), parameters]
    else:
        netem_parameters_selected_interface = parameters
    return netem_parameters_selected_interface


@app.get('/parameters/{interface}', tags=['Traffic Control status'])
def parameters_selected_interface_tc_status(interface: str):
    check_interface(interface)
    netem_parameters = get_parameters_from_terminal()
    parameters = netem_parameters.get(interface)
    if not parameters:
        return f'No active Network Emulation found for interface {interface}'
    return netem_parameters.get(interface)


@app.get('/ip/{interface}', tags=['Traffic Control status'])
def ip_tc_status(interface: str):
    check_interface(interface)
    netem_parameters = get_parameters_from_terminal()
    if 'target_ips' in netem_parameters:
        netem_parameters_ips = netem_parameters.get('target_ips')
        return netem_parameters_ips.get(interface)
    else:
        return f'No target IPs found on interface {interface}'


class Parameters(BaseModel):
    """
    This class arranges all network emulation parameters needed for the correct implementation of the emulation,
    including their default values to help understand how they should be used.

    - **"interface"**(default value: 'eth0'): The device interface where changes will be made
    (_has to be one of the system interfaces_)
    - **"limit"**(default value: 0): Maximum number of packets the queueing discipline may hold queued at a time
    (_it's a positive integer_)
    - **"loss"**(default value: 0): The percentage of packets that will be randomly lost(_it's a number between 0-100_)
    - **"duplicate"**(default value: 0): The percentage of packets that will be randomly duplicated
    (_it's a number between 0-100_)
    - **"corrupt"**(default value: 0): The percentage of packets that will be randomly corrupted
    (i.e. changing a few random bytes)(_it's a number between 0-100_)
    - **"rate"**(default value: 0 (if remains as 0, wouldn't be applied)):
    The bandwidth permitted by the traffic control(_it's a positive number_)
    - **"unit_rate"**(default value: 'kbps'): The units for the value specified in "rate".
    (values permitted: _'tbps', 'gbps', 'mbps', 'kbps', 'bps', 'tbit', 'gbit', 'mbit', 'kbit', 'bit'_)
    (_bps_ stands for bytes per second and _bit_ stands for bits per second)
    - **"delay"**(default value: 0 ): adds the chosen delay to the packets outgoing to chosen network interface
    (_it's a positive integer_)
    - **"unit_delay"**(default value: 'ms'): The units for the value specified in "delay".
    (values permitted: _'s', 'ms', 'us', 'ns'_)
    - **"distribution"**(default value: 'uniform'): Modifies the delay value according to the chosen distribution
    (values permitted: _'uniform', 'normal'_)
    - **"packets"**(default value: 1): Limits the number of packets delivered per delay slot
    (i.e. the number of packets that are delivered at the same time)(_it's a positive integer greater than zero_).
    """
    interface: str = default_interface()
    limit: int = 1000
    loss: float = 0
    duplicate: float = 0
    corrupt: float = 0
    rate: float = 0
    unit_rate: str = 'kbps'
    delay: float = 0
    unit_delay: str = 'ms'
    distribution: str = 'uniform'
    packets: int = 1

    @field_validator('interface')
    @classmethod
    def detected_interfaces(cls, interface):
        check_interface(interface)
        return interface

    @field_validator('limit', 'rate', 'delay')
    @classmethod
    def no_negative_numbers(cls, number):
        if number < 0 or number > 2147483647:
            raise ValueError('Limit, rate and delay values must be positive (no greater than 2147483647)')
        return number

    @field_validator('loss', 'duplicate', 'corrupt')
    @classmethod
    def only_percentages(cls, number):
        if number < 0 or number > 100:
            raise ValueError('Loss, duplicate and corrupt values must be percentages in range 0%-100%')
        return number

    @field_validator('unit_rate')
    @classmethod
    def units_rate(cls, word):
        possibilities = {'tbps', 'gbps', 'mbps', 'kbps', 'bps', 'tbit', 'gbit', 'mbit', 'kbit', 'bit'}
        if word not in possibilities:
            raise ValueError('Units permitted for rate (unit_rate) are [tbps, gbps, mbps, kbps, bps, tbit, gbit, mbit, '
                             'kbit, bit]')
        return word

    @field_validator('unit_delay')
    @classmethod
    def units_delay(cls, word):
        possibilities = {'s', 'ms', 'us', 'ns'}
        if word not in possibilities:
            raise ValueError('Units permitted for delay (unit_delay) are [s, ms, us, ns]')
        return word

    @field_validator('distribution')
    @classmethod
    def distributions_delay(cls, word):
        possibilities = {'uniform', 'normal'}
        if word not in possibilities:
            raise ValueError('Distributions permitted for delay ("distribution") are [uniform, normal]')
        return word

    @field_validator('packets')
    @classmethod
    def number_greater_than_one(cls, number):
        if number < 1:
            raise ValueError('Packets value must be greater than one')
        return number


class ParametersWithoutDefault(BaseModel):
    """
    This class has the same purpose as the Parameters class, it arranges all network emulation parameters needed for the
     correct implementation of the emulation; but, in this class, their default values are being removed in order to
     make changes to the active traffic control parameters without overwriting active values with the default ones.

    - **"interface"**(default value: 'eth0'): The device interface where changes will be made
    (_has to be one of the system interfaces_)
    - **"limit"**(default value: 0): Maximum number of packets the queueing discipline may hold queued at a time
    (_it's a positive integer_)
    - **"loss"**(default value: 0): The percentage of packets that will be randomly lost(_it's a number between 0-100_)
    - **"duplicate"**(default value: 0): The percentage of packets that will be randomly duplicated
    (_it's a number between 0-100_)
    - **"corrupt"**(default value: 0): The percentage of packets that will be randomly corrupted
    (i.e. changing a few random bytes)(_it's a number between 0-100_)
    - **"rate"**(default value: 0 (if remains as 0, wouldn't be applied)):
    The bandwidth permitted by the traffic control(_it's a positive number_)
    - **"unit_rate"**(default value: 'kbps'): The units for the value specified in "rate".
    (values permitted: _'tbps', 'gbps', 'mbps', 'kbps', 'bps', 'tbit', 'gbit', 'mbit', 'kbit', 'bit'_)
    (_bps_ stands for bytes per second and _bit_ stands for bits per second)
    - **"delay"**(default value: 0 ): adds the chosen delay to the packets outgoing to chosen network interface
    (_it's a positive integer_)
    - **"unit_delay"**(default value: 'ms'): The units for the value specified in "delay".
    (values permitted: _'s', 'ms', 'us', 'ns'_)
    - **"distribution"**(default value: 'uniform'): Modifies the delay value according to the chosen distribution
    (values permitted: _'uniform', 'normal'_)
    - **"packets"**(default value: 1): Limits the number of packets delivered per delay slot
    (i.e. the number of packets that are delivered at the same time)(_it's a positive integer greater than zero_).
    """
    interface: str = default_interface()
    limit: Optional[int] = None
    loss: Optional[float] = None
    duplicate: Optional[float] = None
    corrupt: Optional[float] = None
    rate: Optional[float] = None
    unit_rate: Optional[str] = None
    delay: Optional[int] = None
    unit_delay: Optional[str] = None
    distribution: Optional[str] = None
    packets: Optional[int] = None

    @field_validator('interface')
    @classmethod
    def detected_interfaces(cls, interface):
        check_interface(interface)
        return interface

    @field_validator('limit', 'rate', 'delay')
    @classmethod
    def no_negative_numbers(cls, number):
        if number < 0 or number > 2147483647:
            raise ValueError('Limit, rate and delay values must be positive (no greater than 2147483647)')
        return number

    @field_validator('loss', 'duplicate', 'corrupt')
    @classmethod
    def only_percentages(cls, number):
        if number < 0 or number > 100:
            raise ValueError('Loss, duplicate and corrupt values must be percentages in range 0%-100%')
        return number

    @field_validator('unit_rate')
    @classmethod
    def units_rate(cls, word):
        possibilities = {'tbps', 'gbps', 'mbps', 'kbps', 'bps', 'tbit', 'gbit', 'mbit', 'kbit', 'bit'}
        if word not in possibilities:
            raise ValueError('Units permitted for rate (unit_rate) are [tbps, gbps, mbps, kbps, bps, tbit, gbit, mbit, '
                             'kbit, bit]')
        return word

    @field_validator('unit_delay')
    @classmethod
    def units_delay(cls, word):
        possibilities = {'s', 'ms', 'us', 'ns'}
        if word not in possibilities:
            raise ValueError('Units permitted for delay (unit_delay) are [s, ms, us, ns]')
        return word

    @field_validator('distribution')
    @classmethod
    def distributions_delay(cls, word):
        possibilities = {'uniform', 'normal'}
        if word not in possibilities:
            raise ValueError('Distributions permitted for delay ("distribution") are [uniform, normal]')
        return word

    @field_validator('packets')
    @classmethod
    def number_greater_than_one(cls, number):
        if number < 1:
            raise ValueError('Packets value must be greater than one')
        return number


def get_all_subnet_ips(ip_range):
    list_ips = []
    if count_points(ip_range) == 4:
        list_ips.append(ip_range)
    else:
        for i in range(256):
            subnet_ip = ip_range + '.' + str(i)
            list_ips.append(subnet_ip)
    return list_ips


def add_ips_to_prio(selected_ips):
    interface = selected_ips.interface
    if len(get_active_ips_from_terminal(interface)) == 0:
        os.system(f'tc q add dev {interface} root handle 1: prio')

    full_ips = []
    ips = selected_ips.ips
    if ips is None:
        os.system(f'tc q del dev {interface} root')
        raise HTTPException(status_code=400, detail='No target IPs selected for emulation. Aborted process')
    elif len(ips) == 0:
        os.system(f'tc q del dev {interface} root')
        raise HTTPException(status_code=400, detail='No target IPs selected for emulation. Aborted process')
    for ip in ips:
        for subnet_ip in get_all_subnet_ips(ip):
            full_ips.append(subnet_ip)
    full_ips = sorted(list(set(full_ips)), key=IPv4Address)

    for ip in full_ips:
        os.system(f'tc filter add dev {interface} parent 1:0 protocol ip prio 1 u32 match ip dst {ip} flowid 2:1')


def pretty_response(interface, user_parameters, modified_interfaces, ips=None):
    modified_interfaces[interface] = {}
    if ips is not None:
        modified_interfaces[interface]['Target IPs'] = sorted(list(set(ips)), key=IPv4Address)
    if user_parameters.delay == 0.0:
        modified_interfaces[interface]['Delay'] = 'No delay applied'
    else:
        modified_interfaces[interface]['Delay'] = f'{user_parameters.delay}{user_parameters.unit_delay} ' \
                                                  f'with {user_parameters.distribution} distribution ' \
                                                  f'applied every {user_parameters.packets} packets'
    modified_interfaces[interface]['Loss'] = str(user_parameters.loss) + '%'
    modified_interfaces[interface]['Corrupt'] = str(user_parameters.corrupt) + '%'
    modified_interfaces[interface]['Duplication'] = str(user_parameters.duplicate) + '%'
    if user_parameters.rate == 0.0:
        modified_interfaces[interface]['Bandwidth'] = 'Not restricted'
    else:
        modified_interfaces[interface]['Bandwidth'] = str(user_parameters.rate) + str(user_parameters.unit_rate)
    modified_interfaces[interface]['Limit'] = str(user_parameters.limit)


def apply_parameters(parameters, list_ips=None):
    modified_interfaces = {}
    for user_parameters in parameters:
        interface = user_parameters.interface
        if user_parameters.delay == 0:
            delay = ''
        elif user_parameters.distribution == 'uniform':
            delay = 'slot ' + str(user_parameters.delay) + str(user_parameters.unit_delay) + ' ' + 'packets ' \
                    + str(user_parameters.packets)
        else:
            delay = 'slot distribution ' + str(user_parameters.distribution) + ' ' + 2 * (
                    str(user_parameters.delay)
                    + str(user_parameters.unit_delay) + ' ') + 'packets ' + str(user_parameters.packets)

        loss = 'loss ' + str(user_parameters.loss) + '%'
        corrupt = 'corrupt ' + str(user_parameters.corrupt) + '%'
        duplicate = 'duplicate ' + str(user_parameters.duplicate) + '%'
        rate = 'rate ' + str(user_parameters.rate) + str(user_parameters.unit_rate)
        limit = 'limit ' + str(user_parameters.limit)

        os.system(f'tc q del dev {interface} root')

        if (int(float(user_parameters.delay)) + int(float(user_parameters.loss)) + int(float(user_parameters.corrupt))
            + int(float(user_parameters.duplicate)) + int(float(user_parameters.rate))) == 0 \
                and str(user_parameters.limit) == '1000':
            return modified_interfaces

        if list_ips is None:
            os.system(f'tc q add dev {interface} root netem {delay} {loss} {corrupt} {duplicate} {rate} {limit}')
            pretty_response(interface, user_parameters, modified_interfaces)

        else:
            ips = []
            for selected_ips in list_ips:
                selected_ips.ips = selected_ips.ips
                if interface == selected_ips.interface:
                    add_ips_to_prio(selected_ips)
                    for ip in selected_ips.ips:
                        for subnet_ip in get_all_subnet_ips(ip):
                            ips.append(subnet_ip)
                    ips = sorted(ips, key=IPv4Address)
            os.system(f'tc q add dev {interface} parent 1:1 handle 2: netem {delay} {loss} {corrupt} {duplicate} '
                      f'{rate} {limit}')
            pretty_response(interface, user_parameters, modified_interfaces, ips)

    return modified_interfaces


@app.post('/', tags=['Network Emulation'])
def enter_parameters_for_network_emulation(parameters: List[Parameters]):
    modified_interfaces = apply_parameters(parameters)
    if len(modified_interfaces) == 0:
        return 'No options selected. Default root applied'
    return 'Process completed. It is recommended to delete the root before closing the program.', \
           'Changes applied to:', f'{modified_interfaces}'


def split_parameters_and_units(value):
    value = value.replace('%', '')
    letters = str()
    if value is int:
        digits = value
        return digits, letters
    else:
        value = value.lower()
        digits = str()
        for character in value:
            if character.isdigit() or character == '.':
                digits += character
            else:
                letters += character
        return digits, letters


def translate_terminal_to_class(interface, values):
    active_parameters = Parameters(interface=interface)
    for parameter, value in values.items():
        digits, letters = split_parameters_and_units(value)
        if len(letters) == 0:
            setattr(active_parameters, parameter, digits)
        elif len(digits) == 0:
            setattr(active_parameters, parameter, letters)
        else:
            setattr(active_parameters, parameter, digits)
            setattr(active_parameters, f'unit_{parameter}', letters)
    return active_parameters


@app.put('/', tags=['Change Network Emulation parameters'])
def make_parameter_changes(parameters: List[ParametersWithoutDefault] = Body(example=[
    {"interface": f"{default_interface()}", "limit": 1000, "loss": 0, "duplicate": 0, "corrupt": 0, "rate": 0,
     "unit_rate": "kbps", "delay": 0, "unit_delay": "ms", "distribution": "uniform", "packets": 1}])):
    seen_parameters = get_parameters_from_terminal()
    final_parameters = []
    ips = []
    for key, values in seen_parameters.items():
        if key == 'target_ips':
            for interface, active_ips in values.items():
                selected_ips = SelectedIPs(interface=interface, ips=active_ips)
                ips.append(selected_ips)
        else:
            final_parameters.append(translate_terminal_to_class(key, values))

    for new_parameters in parameters:
        old_found = False
        for old_parameters in final_parameters:
            if new_parameters.interface != old_parameters.interface:
                continue
            else:
                old_found = True
            for parameter, new_value in new_parameters:
                if new_value is not None:
                    setattr(old_parameters, parameter, new_value)
        if not old_found:
            raise HTTPException(status_code=400, detail='No previous active parameters found on '
                                                        'some of the selected interfaces')
    if len(ips) == 0:
        modified_interfaces = apply_parameters(final_parameters)
    else:
        modified_interfaces = apply_parameters(final_parameters, ips)

    return 'Process completed. It is recommended to delete the root before closing the program.', \
           'New active Network Emulation:', f'{modified_interfaces}'


@app.put('/interface/{interface}', tags=['Change Network Emulation parameters'])
def make_parameter_changes(interface: str, new_parameters: dict = Body(
    example={"limit": 1000, "loss": 0, "duplicate": 0, "corrupt": 0, "rate": 0, "unit_rate": "kbps", "delay": 0,
             "unit_delay": "ms", "distribution": "uniform", "packets": 1}, ), ):
    parameters = ParametersWithoutDefault(interface=interface)
    for key, value in new_parameters.items():
        setattr(parameters, key, value)
    seen_parameters = get_parameters_from_terminal()
    final_parameters = []
    ips = []
    for key, values in seen_parameters.items():
        if key == 'target_ips':
            for interface, active_ips in values.items():
                selected_ips = SelectedIPs(interface=interface, ips=active_ips)
                ips.append(selected_ips)
        else:
            final_parameters.append(translate_terminal_to_class(key, values))

    old_found = False
    for old_parameters in final_parameters:
        if parameters.interface != old_parameters.interface:
            continue
        else:
            old_found = True
        for parameter, new_value in parameters:
            if new_value is not None:
                setattr(old_parameters, parameter, new_value)
    if not old_found:
        raise HTTPException(status_code=400, detail=f'No previous active parameters found interface {interface}')

    if len(ips) == 0:
        modified_interfaces = apply_parameters(final_parameters)
    else:
        modified_interfaces = apply_parameters(final_parameters, ips)

    return 'Process completed. It is recommended to delete the root before closing the program.', \
           'New active Network Emulation:', f'{modified_interfaces}'


@app.delete('/', tags=['Remove Network Emulation'])
def delete_root(list_interfaces: List[str] = Body(example=device_interfaces())):
    no_input = False
    if len(list_interfaces) == 0:
        list_interfaces = device_interfaces()
        no_input = True
    for interface in list_interfaces:
        check_interface(interface)
        os.system(f'tc q del dev {interface} root')
    if no_input:
        return {'No input was given, default traffic control applied to all interfaces': list_interfaces}
    return {'Default traffic control applied to': list_interfaces}


@app.delete('/interface/{interface}', tags=['Remove Network Emulation'])
def delete_interface_root(interface: str):
    check_interface(interface)
    os.system(f'tc q del dev {interface} root')
    return {'Default traffic control applied to': interface}


def count_points(ip):
    x = ip.split(".")
    num = len(x)
    return num


def translate_ip_for_scan(ip_range):
    number_points = count_points(ip_range)
    if number_points == 4:
        ip_range += '/32'
    elif number_points == 3:
        ip_range += '.0/24'
    else:
        raise HTTPException(status_code=400,
                            detail='Invalid ip supplied. Usage: 192.168.3.2 or 192.168.3 for full subnet')

    return ip_range


def local_ips():
    system_interfaces = device_interfaces()
    list_ip_range = []
    for interface in system_interfaces:
        ip_addr = [j['addr'] for j in ifaddresses(interface).setdefault(AF_INET, [{'addr': 'No IP addr'}])]
        list_ip_range.append(ip_addr)
    return list_ip_range


def default_ips():
    ip_ranges = local_ips()
    list_default_ips = []
    for ip_range in ip_ranges:
        ip_range = str(ip_range)
        punctuation = "[']"
        for character in punctuation:
            ip_range = ip_range.replace(character, '')
        ip_range = get_full_subnet(ip_range)
        list_default_ips.append(ip_range)
    return list_default_ips


def get_full_subnet(ip_range):
    split_ip = ip_range.split(".")
    full_subnet_ip_range = '.'.join(split_ip[:len(split_ip) - 1])
    return full_subnet_ip_range


def check_ip(ip):
    try:
        print(f"Valid IP: {IPv4Network(ip)}")
    except Exception:
        print(f"Invalid IP range {ip}.")
        raise HTTPException(status_code=400, detail=f'Error. Invalid IP range supplied ({ip}). Usage: 192.168.3.2 or '
                                                    '192.168.3 for full subnet')


@app.post('/ip_scan', tags=['Arp scan'])
def arp_scan(ip_ranges: List[str] = Body(example=default_ips())):
    list_active_ips = {}
    no_input = False
    if len(ip_ranges) == 0:
        ip_ranges = default_ips()
        no_input = True

    for ip_range in ip_ranges:
        ip_range = translate_ip_for_scan(ip_range)
        check_ip(ip_range)
        print('Scanning...')
        ips_active = arping(ip_range, verbose=0)[0]
        for ip_active in ips_active:
            ip = ip_active[1].psrc
            mac = ip_active[1].hwsrc
            list_active_ips[mac] = ip
    if no_input:
        return {f'No input was given, scan completed on the interfaces IP ranges {ip_ranges}': list_active_ips}
    return {f'Scan completed on {ip_ranges}': list_active_ips}


class SelectedIPs(BaseModel):
    """
    This class lets the user select the target IP addresses that will be following the protocol specified
    with the chosen parameters.

    - **"interface"**(default value: 'eth0'): The device interface where changes will be made
    (_has to be one of the system interfaces_)
    - **"ips"**(default value: ['192.168.3.2', '192.168.1']): A list containing all the IPs that want to be added to the
     traffic control (_it's a list of IP addresses or IP range_)
    """
    interface: str = default_interface()
    ips: List[str] = default_ips()

    @field_validator('interface')
    @classmethod
    def detected_interfaces(cls, interface):
        check_interface(interface)
        return interface

    @field_validator('ips')
    @classmethod
    def real_ips(cls, ips):
        for ip in ips:
            ip = translate_ip_for_scan(ip)
            check_ip(ip)
            return ips


@app.post('/ip', tags=['Network Emulation'])
def enter_parameters_for_ip_network_emulation(ips: List[SelectedIPs], parameters: List[Parameters]):
    interface_matches = []
    for interface_ips in ips:
        for interface_parameters in parameters:
            if interface_ips.interface == interface_parameters.interface:
                interface = interface_parameters.interface
                if interface not in interface_matches:
                    interface_matches.append(interface)
                else:
                    raise HTTPException(status_code=400, detail=f'Interface {interface} has multiple target IPs lists')
    for interface_parameters in parameters:
        interface = interface_parameters.interface
        if interface not in interface_matches:
            raise HTTPException(status_code=400,
                                detail=f'Not found any target IPs for interface {interface}')
    modified_interfaces = apply_parameters(parameters, ips)
    if len(modified_interfaces) == 0:
        return 'No options selected. Default root applied'
    return modified_interfaces


@app.put('/ip', tags=['Change Network Emulation target IPs'])
def add_ips(ips: List[SelectedIPs]):
    seen_parameters = get_parameters_from_terminal()
    selected_interfaces = []
    final_parameters = []
    final_ips = []
    found = 0
    already_active_ips = {}
    for key, values in seen_parameters.items():
        if key == 'target_ips':
            for interface, active_ips in values.items():
                for interface_ips in ips:
                    if interface_ips.interface == interface:
                        added_ips = []
                        if interface_ips.interface not in selected_interfaces:
                            selected_interfaces.append(interface_ips.interface)
                        else:
                            raise HTTPException(status_code=400,
                                                detail=f'Interface {interface_ips.interface} '
                                                       'has multiple added IPs lists')
                        found += 1
                        for ip in interface_ips.ips:
                            for subnet_ip in get_all_subnet_ips(ip):
                                if subnet_ip not in active_ips and ip not in added_ips:
                                    added_ips.append(subnet_ip)
                                elif subnet_ip in active_ips:
                                    already_active_ips.setdefault(interface, []).append(subnet_ip)
                        final_interface_ips = SelectedIPs(interface=interface, ips=(active_ips + added_ips))
                        final_ips.append(final_interface_ips)
                if interface in already_active_ips:
                    already_active_ips[interface] = sorted(list(set(already_active_ips[interface])), key=IPv4Address)

        else:
            if key in selected_interfaces:
                final_parameters.append(translate_terminal_to_class(key, values))

    if found != len(ips):
        raise HTTPException(status_code=406, detail='Not all interfaces selected were found with active ip simulation.'
                                                    ' Aborted Process')

    modified_interfaces = apply_parameters(final_parameters, final_ips)

    if len(already_active_ips) != 0:
        return f'Some selected IPs were already in the active list of target IPs:{already_active_ips}. ' \
               'Process completed. It is recommended to delete the root before closing the program.', \
               'New active Network Emulation:', f'{modified_interfaces}'

    return 'Process completed. It is recommended to delete the root before closing the program.', \
           'New active Network Emulation:', f'{modified_interfaces}'


@app.put('/ip/interface/{interface}', tags=['Change Network Emulation target IPs'])
def add_interface_ips(interface: str, list_ips: List[str] = Body(example=default_ips())):
    ips = SelectedIPs(interface=interface, ips=list_ips)
    seen_parameters = get_parameters_from_terminal()
    selected_interfaces = []
    final_parameters = []
    final_ips = []
    already_active_ips = []
    found_interface = False
    added_ips = []
    for key, values in seen_parameters.items():
        if key == 'target_ips':
            for interface, active_ips in values.items():
                if interface == ips.interface:
                    found_interface = True
                    for ip in ips.ips:
                        for subnet_ip in get_all_subnet_ips(ip):
                            if subnet_ip not in active_ips and subnet_ip not in added_ips:
                                added_ips.append(subnet_ip)
                            elif subnet_ip in active_ips:
                                already_active_ips.append(subnet_ip)
                    selected_interfaces.append(ips.interface)
                    ips.ips = (active_ips + added_ips)
                    final_ips.append(ips)

        else:
            if key in selected_interfaces:
                final_parameters.append(translate_terminal_to_class(key, values))

    if not found_interface:
        raise HTTPException(status_code=400, detail='Interface selected had no previous active IP emulation')

    modified_interfaces = apply_parameters(final_parameters, final_ips)
    already_active_ips = sorted(list(set(already_active_ips)), key=IPv4Address)
    if len(already_active_ips) != 0:
        return f'Some selected IPs were already in the active list of target IPs:{already_active_ips}. ' \
               'Process completed. It is recommended to delete the root before closing the program.', \
               'New active Network Emulation:', f'{modified_interfaces}'

    return 'Process completed. It is recommended to delete the root before closing the program.', \
           'New active Network Emulation:', f'{modified_interfaces}'


@app.delete('/ip', tags=['Change Network Emulation target IPs'])
def remove_ips(ips: List[SelectedIPs]):
    seen_parameters = get_parameters_from_terminal()
    selected_interfaces = []
    final_parameters = []
    final_ips = []
    not_found_ips = {}
    found = 0
    for key, values in seen_parameters.items():
        if key == 'target_ips':
            for interface, active_ips in values.items():
                for interface_ips in ips:
                    selected_interfaces.append(interface_ips.interface)
                    if interface_ips.interface == interface:
                        found += 1
                        for ip in interface_ips.ips:
                            subnet_ips = get_all_subnet_ips(ip)
                            for subnet_ip in subnet_ips:
                                if subnet_ip in active_ips:
                                    active_ips.remove(subnet_ip)
                                else:
                                    not_found_ips.setdefault(interface, []).append(subnet_ip)
                        final_interface_ips = SelectedIPs(interface=interface, ips=active_ips)
                        final_ips.append(final_interface_ips)
                if interface in not_found_ips:
                    not_found_ips[interface] = list(set(not_found_ips[interface]))

        else:
            if key in selected_interfaces:
                final_parameters.append(translate_terminal_to_class(key, values))

    if found != len(ips):
        raise HTTPException(status_code=406, detail='Not all interfaces selected were found with active ip simulation.'
                                                    ' Aborted Process')

    modified_interfaces = apply_parameters(final_parameters, final_ips)
    if len(not_found_ips) != 0:
        return f'Some selected IPs were not in the active list of target IPs:{not_found_ips}. ' \
               'Process completed. It is recommended to delete the root before closing the program.', \
               'New active Network Emulation:', f'{modified_interfaces}'

    return 'Process completed. It is recommended to delete the root before closing the program.', \
           'New active Network Emulation:', f'{modified_interfaces}'


@app.delete('/ip/interface/{interface}', tags=['Change Network Emulation target IPs'])
def remove_interface_ips(interface: str, list_ips: List[str] = Body(example=default_ips())):
    ips = SelectedIPs(interface=interface, ips=list_ips)
    seen_parameters = get_parameters_from_terminal()
    selected_interfaces = []
    final_parameters = []
    final_ips = []
    not_found_ips = []
    found_interface = False
    for key, values in seen_parameters.items():
        if key == 'target_ips':
            for interface, active_ips in values.items():
                selected_interfaces.append(ips.interface)
                if ips.interface == interface:
                    found_interface = True
                    for ip in ips.ips:
                        for subnet_ip in get_all_subnet_ips(ip):
                            if subnet_ip in active_ips:
                                active_ips.remove(subnet_ip)
                            else:
                                not_found_ips.append(subnet_ip)
                    ips.ips = active_ips
                    final_ips.append(ips)
            not_found_ips = list(set(not_found_ips))

        else:
            if key in selected_interfaces:
                final_parameters.append(translate_terminal_to_class(key, values))

    if not found_interface:
        raise HTTPException(status_code=400, detail='Interface selected had no previous active IP emulation')

    modified_interfaces = apply_parameters(final_parameters, final_ips)

    not_found_ips = sorted(list(set(not_found_ips)), key=IPv4Address)
    if len(not_found_ips) != 0:
        return f'Some selected IPs were not in the active list of target IPs:{not_found_ips}. ' \
               'Process completed. It is recommended to delete the root before closing the program.', \
               'New active Network Emulation:', f'{modified_interfaces}'

    return 'Process completed. It is recommended to delete the root before closing the program.', \
           'New active Network Emulation:', f'{modified_interfaces}'
