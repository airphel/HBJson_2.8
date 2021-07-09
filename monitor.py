#!/usr/bin/env python3
#
###############################################################################
#   Copyright (C) 2016-2019  Cortney T. Buffington, N0MJS <n0mjs@me.com>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software Foundation,
#   Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
###############################################################################
#
#   Python 3 port by Steve Miller, KC1AWV <smiller@kc1awv.net>
#
###############################################################################
###############################################################################
#
#   Version by Waldek SP2ONG
#
###############################################################################
###############################################################################
#
#   JSON service by Avrahqedivra F-16987
#
###############################################################################

# Standard modules
import json
import logging
import datetime

import os
import csv
from itertools import islice
from subprocess import check_call, CalledProcessError

# Twisted modules
from twisted.internet.protocol import ReconnectingClientFactory, Protocol
from twisted.protocols.basic import NetstringReceiver, FileSender
from twisted.internet import reactor, endpoints, task, defer
from twisted.web.server import Site
from twisted.web import http
from twisted.web.client import URI
from twisted.web.resource import Resource, NoResource
from twisted.web.static import File
from twisted.web import server
import base64

# Autobahn provides websocket service under Twisted
from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory
from autobahn.websocket.compress import *

# Specific functions to import from standard modules
from time import time, strftime, localtime
from pickle import loads
from binascii import b2a_hex as h
from os.path import getmtime
from collections import deque
from time import time

# Utilities from K0USY Group sister project
from dmr_utils3.utils import int_id, get_alias, try_download, mk_full_id_dict, bytes_4

# Configuration variables and constants
from config import *

# SP2ONG - Increase the value if HBlink link break occurs
NetstringReceiver.MAX_LENGTH = 500000000

# Opcodes for reporting protocol to HBlink
OPCODE = {
    'CONFIG_REQ': '\x00',
    'CONFIG_SND': '\x01',
    'BRIDGE_REQ': '\x02',
    'BRIDGE_SND': '\x03',
    'CONFIG_UPD': '\x04',
    'BRIDGE_UPD': '\x05',
    'LINK_EVENT': '\x06',
    'BRDG_EVENT': '\x07',
    }

# Global Variables:
CONFIG      = {}
CTABLE      = {'MASTERS': {}, 'PEERS': {}, 'OPENBRIDGES': {}, 'SETUP': {}}
BRIDGES     = {}
BTABLE      = {}
BTABLE['BRIDGES'] = {}
BRIDGES_RX  = ''
CONFIG_RX   = ''

LASTHEARDSIZE       = 100
TRAFFICSIZE         = 50
CTABLEJ             = ""
BTABLEJ             = ""
MESSAGEJ            = []
SILENTJ             = True
VOICEJ              = False

# Define setup setings
CTABLE['SETUP']['LASTHEARD'] = LASTHEARD_INC

# OPB Filter for lastheard
def get_opbf():
   if len(OPB_FILTER) !=0:
       mylist = OPB_FILTER.replace(' ','').split(',')
   else:
       mylist = []
   return mylist

# For importing HTML templates
def get_template(_file):
    with open(_file, 'r') as html:
        return html.read()

# Alias string processor
def alias_string(_id, _dict):
    alias = get_alias(_id, _dict, 'CALLSIGN', 'CITY', 'STATE')
    if type(alias) == list:
        for x,item in enumerate(alias):
            if item == None:
                alias.pop(x)
        return ', '.join(alias)
    else:
        return alias

def alias_only(_id, _dict):
    alias = get_alias(_id, _dict, 'CALLSIGN', 'NAME')
    if type(alias) == list:
        for x,item in enumerate(alias):
            if item == None:
                alias.pop(x)

        return alias
    else:
        return ["", str(alias)]

def alias_short(_id, _dict):
    alias = get_alias(_id, _dict, 'CALLSIGN', 'NAME')
    if type(alias) == list:
        for x,item in enumerate(alias):
            if item == None:
                alias.pop(x)
        return ', '.join(alias)
    else:
        return str(alias)

def alias_call(_id, _dict):
    alias = get_alias(_id, _dict, 'CALLSIGN')
    if type(alias) == list:
        for x,item in enumerate(alias):
            if item == None:
                alias.pop(x)
        return ', '.join(alias)
    else:
        return str(alias)

def alias_tgid(_id, _dict):
    alias = get_alias(_id, _dict, 'NAME')
    if type(alias) == list:
        return str(alias[0])
    else:
        return str(alias)

# Return friendly elapsed time from time in seconds.
def since(_time):
    now = int(time())
    _time = now - int(_time)
    seconds = _time % 60
    minutes = int(_time/60) % 60
    hours = int(_time/60/60) % 24
    days = int(_time/60/60/24)
    if days:
        return '{}d {}h'.format(days, hours)
    elif hours:
        return '{}h {}m'.format(hours, minutes)
    elif minutes:
        return '{}m {}s'.format(minutes, seconds)
    else:
        return '{}s'.format(seconds)

##################################################
# Cleaning entries in tables - Timeout (5 min)
#
def cleanTE():
    timeout = datetime.datetime.now().timestamp()

    for system in CTABLE['MASTERS']:
        for peer in CTABLE['MASTERS'][system]['PEERS']:
            for timeS in range(1,3):
              if CTABLE['MASTERS'][system]['PEERS'][peer][timeS]['TS']:
                ts = CTABLE['MASTERS'][system]['PEERS'][peer][timeS]['TIMEOUT']
                td = ts - timeout if ts > timeout else timeout - ts
                td = int(round(abs((td)) / 60))
                if td > 3:
                    CTABLE['MASTERS'][system]['PEERS'][peer][timeS]['TS'] = False
                    CTABLE['MASTERS'][system]['PEERS'][peer][timeS]['TXRX'] = ''
                    CTABLE['MASTERS'][system]['PEERS'][peer][timeS]['TYPE'] = ''
                    CTABLE['MASTERS'][system]['PEERS'][peer][timeS]['SUB'] = ''
                    CTABLE['MASTERS'][system]['PEERS'][peer][timeS]['SRC'] = ''
                    CTABLE['MASTERS'][system]['PEERS'][peer][timeS]['DEST'] = ''

    for system in CTABLE['PEERS']:
        for timeS in range(1,3):
            if CTABLE['PEERS'][system][timeS]['TS']:
                ts = CTABLE['PEERS'][system][timeS]['TIMEOUT']
                td = ts - timeout if ts > timeout else timeout - ts
                td = int(round(abs((td)) / 60))
                if td > 3:
                    CTABLE['PEERS'][system][timeS]['TS'] = False
                    CTABLE['PEERS'][system][timeS]['TXRX'] = ''
                    CTABLE['PEERS'][system][timeS]['TYPE'] = ''
                    CTABLE['PEERS'][system][timeS]['SUB'] = ''
                    CTABLE['PEERS'][system][timeS]['SRC'] = ''
                    CTABLE['PEERS'][system][timeS]['DEST'] = ''

    for system in CTABLE['OPENBRIDGES']:
        for streamId in list(CTABLE['OPENBRIDGES'][system]['STREAMS']):
            ts = CTABLE['OPENBRIDGES'][system]['STREAMS'][streamId][3]
            td = ts - timeout if ts > timeout else timeout - ts
            td = int(round(abs((td)) / 60))
            if td > 3:
                 del CTABLE['OPENBRIDGES'][system]['STREAMS'][streamId]


def add_hb_peer(_peer_conf, _ctable_loc, _peer):
    _ctable_loc[int_id(_peer)] = {}
    _ctable_peer = _ctable_loc[int_id(_peer)]

    # if the Frequency is 000.xxx assume it's not an RF peer, otherwise format the text fields
    # (9 char, but we are just software)  see https://wiki.brandmeister.network/index.php/Homebrew/example/php2

    if _peer_conf['TX_FREQ'].strip().isdigit() and _peer_conf['RX_FREQ'].strip().isdigit() and str(type(_peer_conf['TX_FREQ'])).find("bytes") != -1 and str(type(_peer_conf['RX_FREQ'])).find("bytes") != -1:
        if _peer_conf['TX_FREQ'][:3] == b'000' or _peer_conf['RX_FREQ'][:3] == b'000':
            _ctable_peer['TX_FREQ'] = 'N/A'
            _ctable_peer['RX_FREQ'] = 'N/A'
        else:
            _ctable_peer['TX_FREQ'] = _peer_conf['TX_FREQ'][:3].decode('utf-8') + '.' + _peer_conf['TX_FREQ'][3:7].decode('utf-8') + ' MHz'
            _ctable_peer['RX_FREQ'] = _peer_conf['RX_FREQ'][:3].decode('utf-8') + '.' + _peer_conf['RX_FREQ'][3:7].decode('utf-8') + ' MHz'
    else:
        _ctable_peer['TX_FREQ'] = 'N/A'
        _ctable_peer['RX_FREQ'] = 'N/A'

    # timeslots are kinda complicated too. 0 = none, 1 or 2 mean that one slot, 3 is both, and anything else it considered DMO
    # Slots (0, 1=1, 2=2, 1&2=3 Duplex, 4=Simplex) see https://wiki.brandmeister.network/index.php/Homebrew/example/php2

    if (_peer_conf['SLOTS'] == b'0'):
        _ctable_peer['SLOTS'] = 'NONE'
    elif (_peer_conf['SLOTS'] == b'1' or _peer_conf['SLOTS'] == b'2'):
        _ctable_peer['SLOTS'] = _peer_conf['SLOTS'].decode('utf-8')
    elif (_peer_conf['SLOTS'] == b'3'):
        _ctable_peer['SLOTS'] = 'Duplex'
    else:
        _ctable_peer['SLOTS'] = 'Simplex'

    # Simple translation items
    if str(type(_peer_conf['PACKAGE_ID'])).find("bytes") != -1:
       _ctable_peer['PACKAGE_ID'] = _peer_conf['PACKAGE_ID'].decode('utf-8').strip()
    else:
       _ctable_peer['PACKAGE_ID'] = _peer_conf['PACKAGE_ID']

    if str(type(_peer_conf['SOFTWARE_ID'])).find("bytes") != -1:
       _ctable_peer['SOFTWARE_ID'] = _peer_conf['SOFTWARE_ID'].decode('utf-8').strip()
    else:
       _ctable_peer['SOFTWARE_ID'] = _peer_conf['SOFTWARE_ID']

    if str(type(_peer_conf['LOCATION'])).find("bytes") != -1:
       _ctable_peer['LOCATION'] = _peer_conf['LOCATION'].decode('utf-8').strip()
    else:
       _ctable_peer['LOCATION'] = _peer_conf['LOCATION']

    if str(type(_peer_conf['CALLSIGN'])).find("bytes") != -1:
       _ctable_peer['CALLSIGN'] = _peer_conf['CALLSIGN'].decode('utf-8').strip()
    else:
       _ctable_peer['CALLSIGN'] = _peer_conf['CALLSIGN']

    _ctable_peer['COLORCODE'] = _peer_conf['COLORCODE'].decode('utf-8')
    _ctable_peer['CALLSIGN'] = _peer_conf['CALLSIGN'].decode('utf-8')

    _ctable_peer['CONNECTION'] = _peer_conf['CONNECTION']
    _ctable_peer['CONNECTED'] = since(_peer_conf['CONNECTED'])
    #_ctable_peer['ONLINE'] = str(_peer_conf['CONNECTED'])
    _ctable_peer['IP'] = _peer_conf['IP']
    _ctable_peer['PORT'] = _peer_conf['PORT']
    #_ctable_peer['LAST_PING'] = _peer_conf['LAST_PING']

    # SLOT 1&2 - for real-time montior: make the structure for later use
    for ts in range(1,3):
        _ctable_peer[ts]= {}
        _ctable_peer[ts]['TS'] = ''
        _ctable_peer[ts]['TYPE'] = ''
        _ctable_peer[ts]['SUB'] = ''
        _ctable_peer[ts]['SRC'] = ''
        _ctable_peer[ts]['DEST'] = ''
        _ctable_peer[ts]['TXRX'] = ''

######################################################################
#
# Build the HBlink connections table
#

def build_hblink_table(_config, _stats_table):
    for _hbp, _hbp_data in list(_config.items()):
        if _hbp_data['ENABLED'] == True:

            # Process Master Systems
            if _hbp_data['MODE'] == 'MASTER':
                _stats_table['MASTERS'][_hbp] = {}
                if _hbp_data['REPEAT']:
                    _stats_table['MASTERS'][_hbp]['REPEAT'] = "repeat"
                else:
                    _stats_table['MASTERS'][_hbp]['REPEAT'] = "isolate"
                _stats_table['MASTERS'][_hbp]['PEERS'] = {}
                for _peer in _hbp_data['PEERS']:
                    add_hb_peer(_hbp_data['PEERS'][_peer], _stats_table['MASTERS'][_hbp]['PEERS'], _peer)

            # Proccess Peer Systems
            elif (_hbp_data['MODE'] == 'XLXPEER' or _hbp_data['MODE'] == 'PEER') and HOMEBREW_INC:
                _stats_table['PEERS'][_hbp] = {}
                _stats_table['PEERS'][_hbp]['MODE'] = _hbp_data['MODE']

                if str(type(_hbp_data['LOCATION'])).find("bytes") != -1:
                     _stats_table['PEERS'][_hbp]['LOCATION'] = _hbp_data['LOCATION'].decode('utf-8').strip()
                else:
                     _stats_table['PEERS'][_hbp]['LOCATION'] = _hbp_data['LOCATION']

                if str(type(_hbp_data['CALLSIGN'])).find("bytes") != -1:
                     _stats_table['PEERS'][_hbp]['CALLSIGN'] = _hbp_data['CALLSIGN'].decode('utf-8').strip()
                else:
                     _stats_table['PEERS'][_hbp]['CALLSIGN'] = _hbp_data['CALLSIGN']

                _stats_table['PEERS'][_hbp]['RADIO_ID'] = int_id(_hbp_data['RADIO_ID'])
                _stats_table['PEERS'][_hbp]['MASTER_IP'] = _hbp_data['MASTER_IP']
                _stats_table['PEERS'][_hbp]['MASTER_PORT'] = _hbp_data['MASTER_PORT']
                _stats_table['PEERS'][_hbp]['STATS'] = {}

                if _stats_table['PEERS'][_hbp]['MODE'] == 'XLXPEER':
                    _stats_table['PEERS'][_hbp]['STATS']['CONNECTION'] = _hbp_data['XLXSTATS']['CONNECTION']

                    if _hbp_data['XLXSTATS']['CONNECTION'] == "YES":
                        _stats_table['PEERS'][_hbp]['STATS']['CONNECTED'] = since(_hbp_data['XLXSTATS']['CONNECTED'])
                        #_stats_table['PEERS'][_hbp]['STATS']['ONLINE'] = str(_hbp_data['XLXSTATS']['CONNECTED'])
                        _stats_table['PEERS'][_hbp]['STATS']['PINGS_SENT'] = _hbp_data['XLXSTATS']['PINGS_SENT']
                        _stats_table['PEERS'][_hbp]['STATS']['PINGS_ACKD'] = _hbp_data['XLXSTATS']['PINGS_ACKD']
                    else:
                        _stats_table['PEERS'][_hbp]['STATS']['CONNECTED'] = "--   --"
                        #_stats_table['PEERS'][_hbp]['STATS']['ONLINE'] = "0"
                        _stats_table['PEERS'][_hbp]['STATS']['PINGS_SENT'] = 0
                        _stats_table['PEERS'][_hbp]['STATS']['PINGS_ACKD'] = 0
                else:
                    _stats_table['PEERS'][_hbp]['STATS']['CONNECTION'] = _hbp_data['STATS']['CONNECTION']

                    if _hbp_data['STATS']['CONNECTION'] == "YES":
                        _stats_table['PEERS'][_hbp]['STATS']['CONNECTED'] = since(_hbp_data['STATS']['CONNECTED'])
                        #_stats_table['PEERS'][_hbp]['STATS']['ONLINE'] = str(_hbp_data['STATS']['CONNECTED'])
                        _stats_table['PEERS'][_hbp]['STATS']['PINGS_SENT'] = _hbp_data['STATS']['PINGS_SENT']
                        _stats_table['PEERS'][_hbp]['STATS']['PINGS_ACKD'] = _hbp_data['STATS']['PINGS_ACKD']
                    else:
                        _stats_table['PEERS'][_hbp]['STATS']['CONNECTED'] = "--   --"
                        #_stats_table['PEERS'][_hbp]['STATS']['ONLINE'] = "0"
                        _stats_table['PEERS'][_hbp]['STATS']['PINGS_SENT'] = 0
                        _stats_table['PEERS'][_hbp]['STATS']['PINGS_ACKD'] = 0

                if _hbp_data['SLOTS'] == b'0':
                    _stats_table['PEERS'][_hbp]['SLOTS'] = 'NONE'
                elif _hbp_data['SLOTS'] == b'1' or _hbp_data['SLOTS'] == b'2':
                    _stats_table['PEERS'][_hbp]['SLOTS'] = _hbp_data['SLOTS'].decode('utf-8')
                elif _hbp_data['SLOTS'] == b'3':
                    _stats_table['PEERS'][_hbp]['SLOTS'] = '1&2'
                else:
                    _stats_table['PEERS'][_hbp]['SLOTS'] = 'DMO'

                # SLOT 1&2 - for real-time montior: make the structure for later use
                for ts in range(1,3):
                    _stats_table['PEERS'][_hbp][ts]= {}
                    _stats_table['PEERS'][_hbp][ts]['TXRX'] = ''
                    _stats_table['PEERS'][_hbp][ts]['TS'] = ''
                    _stats_table['PEERS'][_hbp][ts]['TYPE'] = ''
                    _stats_table['PEERS'][_hbp][ts]['SUB'] = ''
                    _stats_table['PEERS'][_hbp][ts]['SRC'] = ''
                    _stats_table['PEERS'][_hbp][ts]['DEST'] = ''

            # Process OpenBridge systems
            elif _hbp_data['MODE'] == 'OPENBRIDGE':
                _stats_table['OPENBRIDGES'][_hbp] = {}
                _stats_table['OPENBRIDGES'][_hbp]['NETWORK_ID'] = int_id(_hbp_data['NETWORK_ID'])
                _stats_table['OPENBRIDGES'][_hbp]['TARGET_IP'] = _hbp_data['TARGET_IP']
                _stats_table['OPENBRIDGES'][_hbp]['TARGET_PORT'] = _hbp_data['TARGET_PORT']
                _stats_table['OPENBRIDGES'][_hbp]['STREAMS'] = {}

    #return(_stats_table)

def update_hblink_table(_config, _stats_table):
    # Is there a system in HBlink's config monitor doesn't know about?
    for _hbp in _config:
        if _config[_hbp]['MODE'] == 'MASTER':
            for _peer in _config[_hbp]['PEERS']:
                if int_id(_peer) not in _stats_table['MASTERS'][_hbp]['PEERS'] and _config[_hbp]['PEERS'][_peer]['CONNECTION'] == 'YES':
                    logger.info('Adding peer to CTABLE that has registerred: %s', int_id(_peer))
                    add_hb_peer(_config[_hbp]['PEERS'][_peer], _stats_table['MASTERS'][_hbp]['PEERS'], _peer)

    # Is there a system in monitor that's been removed from HBlink's config?
    for _hbp in _stats_table['MASTERS']:
        remove_list = []
        if _config[_hbp]['MODE'] == 'MASTER':
            for _peer in _stats_table['MASTERS'][_hbp]['PEERS']:
                if bytes_4(_peer) not in _config[_hbp]['PEERS']:
                    remove_list.append(_peer)

            for _peer in remove_list:
                logger.info('Deleting stats peer not in hblink config: %s', _peer)
                del (_stats_table['MASTERS'][_hbp]['PEERS'][_peer])

    # Update connection time
    for _hbp in _stats_table['MASTERS']:
        for _peer in _stats_table['MASTERS'][_hbp]['PEERS']:
            if bytes_4(_peer) in _config[_hbp]['PEERS']:
                _stats_table['MASTERS'][_hbp]['PEERS'][_peer]['CONNECTED'] = since(_config[_hbp]['PEERS'][bytes_4(_peer)]['CONNECTED'])

    for _hbp in _stats_table['PEERS']:
        if _stats_table['PEERS'][_hbp]['MODE'] == 'XLXPEER':
            if _config[_hbp]['XLXSTATS']['CONNECTION'] == "YES":
                _stats_table['PEERS'][_hbp]['STATS']['CONNECTED'] = since(_config[_hbp]['XLXSTATS']['CONNECTED'])
                #_stats_table['PEERS'][_hbp]['STATS']['ONLINE'] = str(_config[_hbp]['XLXSTATS']['ONLINE'])
                _stats_table['PEERS'][_hbp]['STATS']['CONNECTION'] = _config[_hbp]['XLXSTATS']['CONNECTION']
                _stats_table['PEERS'][_hbp]['STATS']['PINGS_SENT'] = _config[_hbp]['XLXSTATS']['PINGS_SENT']
                _stats_table['PEERS'][_hbp]['STATS']['PINGS_ACKD'] = _config[_hbp]['XLXSTATS']['PINGS_ACKD']
            else:
                _stats_table['PEERS'][_hbp]['STATS']['CONNECTED'] = "--   --"
                #_stats_table['PEERS'][_hbp]['STATS']['ONLINE'] = "0"
                _stats_table['PEERS'][_hbp]['STATS']['CONNECTION'] = _config[_hbp]['XLXSTATS']['CONNECTION']
                _stats_table['PEERS'][_hbp]['STATS']['PINGS_SENT'] = 0
                _stats_table['PEERS'][_hbp]['STATS']['PINGS_ACKD'] = 0
        else:
            if _config[_hbp]['STATS']['CONNECTION'] == "YES":
                _stats_table['PEERS'][_hbp]['STATS']['CONNECTED'] = since(_config[_hbp]['STATS']['CONNECTED'])
                #_stats_table['PEERS'][_hbp]['STATS']['ONLINE'] = str(_config[_hbp]['STATS']['ONLINE'])
                _stats_table['PEERS'][_hbp]['STATS']['CONNECTION'] = _config[_hbp]['STATS']['CONNECTION']
                _stats_table['PEERS'][_hbp]['STATS']['PINGS_SENT'] = _config[_hbp]['STATS']['PINGS_SENT']
                _stats_table['PEERS'][_hbp]['STATS']['PINGS_ACKD'] = _config[_hbp]['STATS']['PINGS_ACKD']
            else:
                _stats_table['PEERS'][_hbp]['STATS']['CONNECTED'] = "--   --"
                #_stats_table['PEERS'][_hbp]['STATS']['ONLINE'] = "0"
                _stats_table['PEERS'][_hbp]['STATS']['CONNECTION'] = _config[_hbp]['STATS']['CONNECTION']
                _stats_table['PEERS'][_hbp]['STATS']['PINGS_SENT'] = 0
                _stats_table['PEERS'][_hbp]['STATS']['PINGS_ACKD'] = 0

    cleanTE()
    build_stats()

######################################################################
#
# CONFBRIDGE TABLE FUNCTIONS
#

def build_bridge_table(_bridges):
    _stats_table = {}
    _now = time()
    _cnow = strftime('%Y-%m-%d %H:%M:%S', localtime(_now))

    for _bridge, _bridge_data in list(_bridges.items()):
        _stats_table[_bridge] = {}

        for system in _bridges[_bridge]:
            _stats_table[_bridge][system['SYSTEM']] = {}
            _stats_table[_bridge][system['SYSTEM']]['TS'] = system['TS']
            _stats_table[_bridge][system['SYSTEM']]['TGID'] = int_id(system['TGID'])

            #_stats_table[_bridge][system['SYSTEM']]['TS']['TXRX'] = ''

            if system['TO_TYPE'] == 'ON' or system['TO_TYPE'] == 'OFF':
                if system['TIMER'] - _now > 0:
                    _stats_table[_bridge][system['SYSTEM']]['EXP_TIME'] = int(system['TIMER'] - _now)
                else:
                    _stats_table[_bridge][system['SYSTEM']]['EXP_TIME'] = 'Expired'
                if system['TO_TYPE'] == 'ON':
                    _stats_table[_bridge][system['SYSTEM']]['TO_ACTION'] = 'Disconnect'
                else:
                    _stats_table[_bridge][system['SYSTEM']]['TO_ACTION'] = 'Connect'
            else:
                _stats_table[_bridge][system['SYSTEM']]['EXP_TIME'] = 'N/A'
                _stats_table[_bridge][system['SYSTEM']]['TO_ACTION'] = 'None'

            if system['ACTIVE'] == True:
                _stats_table[_bridge][system['SYSTEM']]['ACTIVE'] = 'Connected'
            elif system['ACTIVE'] == False:
                _stats_table[_bridge][system['SYSTEM']]['ACTIVE'] = 'Disconnected'

            for i in range(len(system['ON'])):
                system['ON'][i] = str(int_id(system['ON'][i]))

            _stats_table[_bridge][system['SYSTEM']]['TRIG_ON'] = ', '.join(system['ON'])

            for i in range(len(system['OFF'])):
                system['OFF'][i] = str(int_id(system['OFF'][i]))

            _stats_table[_bridge][system['SYSTEM']]['TRIG_OFF'] = ', '.join(system['OFF'])
    return _stats_table

######################################################################
#
# BUILD HBlink AND CONFBRIDGE TABLES FROM CONFIG/BRIDGES DICTS
#          THIS CURRENTLY IS A TIMED CALL
#
build_time = time()
def build_stats():
    global build_time
    now = time()
    if True: #now > build_time + 1:
        if CONFIG:
            CTABLEJ = { 'CTABLE' : CTABLE, 'EMPTY_MASTERS' : EMPTY_MASTERS }
            dashboard_server.broadcast(CTABLEJ)
        if BRIDGES and BRIDGES_INC:
            BTABLEJ = { 'BRIDGES': BTABLE['BRIDGES'] }
            # dashboard_server.broadcast(BTABLEJ)
        build_time = now


def timeout_clients():
    now = time()
    try:
        for client in dashboard_server.clients:
            if dashboard_server.clients[client] + CLIENT_TIMEOUT < now:
                logger.info('TIMEOUT: disconnecting client %s', dashboard_server.clients[client])
                try:
                    dashboard.sendClose(client)
                except Exception as e:
                    logger.error('Exception caught parsing client timeout %s', e)
    except:
        logger.info('CLIENT TIMEOUT: List does not exist, skipping. If this message persists, contact the developer')


def rts_update(p):
    callType = p[0]
    action = p[1]
    trx = p[2]
    system = p[3]
    streamId = p[4]
    sourcePeer = int(p[5])
    sourceSub = int(p[6])
    timeSlot = int(p[7])
    destination = int(p[8])
    timeout = datetime.datetime.now().timestamp()

    if system in CTABLE['MASTERS']:
        for peer in CTABLE['MASTERS'][system]['PEERS']:
            if action == 'START':
                CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['TIMEOUT'] = timeout
                CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['TS'] = True

                if sourcePeer in (None, '') or peer in (None, ''):
                    CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['TXRX'] = ''
                else:
                    CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['TXRX'] = "TX" if (sourcePeer == peer) else "RX"

                CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['TYPE'] = callType
                CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['SRC'] = peer
				CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['SUB'] = '{} ({})'.format(alias_short(sourceSub, subscriber_ids), sourceSub)
				CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['DEST'] = '{} ({})'.format(alias_tgid(destination,talkgroup_ids),destination)

            if action == 'END':
                CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['TS'] = False
                CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['TXRX'] = ''
                CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['TYPE'] = ''
                CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['SUB'] = ''
                CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['SRC'] = ''
                CTABLE['MASTERS'][system]['PEERS'][peer][timeSlot]['DEST'] = ''

    if system in CTABLE['OPENBRIDGES']:
        if action == 'START':
            CTABLE['OPENBRIDGES'][system]['STREAMS'][streamId] = (trx, alias_call(sourceSub, subscriber_ids),'TG{}'.format(destination),timeout)
        if action == 'END':
            if streamId in CTABLE['OPENBRIDGES'][system]['STREAMS']:
                del CTABLE['OPENBRIDGES'][system]['STREAMS'][streamId]

    if system in CTABLE['PEERS']:
        if action == 'START':
            CTABLE['PEERS'][system][timeSlot]['TIMEOUT'] = timeout
            CTABLE['PEERS'][system][timeSlot]['TS'] = True
            CTABLE['PEERS'][system][timeSlot]['SUB'] = '{} ({})'.format(alias_short(sourceSub,subscriber_ids),sourceSub)
            CTABLE['PEERS'][system][timeSlot]['SRC'] = sourcePeer
            CTABLE['PEERS'][system][timeSlot]['DEST'] = '{} ({})'.format(alias_tgid(destination,talkgroup_ids),destination)

            if not sourcePeer or not sourceSub or not destination:
                CTABLE['PEERS'][system][timeSlot]['TXRX'] = ''
            else:
                CTABLE['PEERS'][system][timeSlot]['TXRX'] = trx

        if action == 'END':
            CTABLE['PEERS'][system][timeSlot]['TS'] = False
            CTABLE['PEERS'][system][timeSlot]['TYPE'] = ''
            CTABLE['PEERS'][system][timeSlot]['SUB'] = ''
            CTABLE['PEERS'][system][timeSlot]['SRC'] = ''
            CTABLE['PEERS'][system][timeSlot]['DEST'] = ''
            CTABLE['PEERS'][system][timeSlot]['TXRX'] = ''

    build_stats()

######################################################################
#
# LOG+
#
def createLogTable():
    logTable = '<table id="loglast" class="tables lastheard tablefixed">\n<thead><tr class="headerRow"><th class="thledate">Date</th><th class="thletime">Heure</th><th class="thleslot">Slot</th><th class="thletx" colspan=2>TX Connectés</th><th class="thlename">Name</th><th class="thletg">TG#</th><th class="thlelog">Conf. Infra</th><th class="thledelay">Durée TX</th><th class="thlenetid">NetID</th><th class="thlemaster">Master Infra</th></tr></thead><tbody>\n'

    with open(LOG_PATH + "lastheard.log", "r") as lastheard:
        for row in islice(reversed(list(csv.reader(lastheard))), 2000):

            REPORT_DATE     = row[0]
            REPORT_DELAY    = row[1]
            REPORT_INFRA    = row[4]

            REPORT_SRC_ID   = row[5]
            REPORT_DMRID    = row[10]

            REPORT_TS       = row[7]
            REPORT_TGID     = row[8]
            REPORT_LOGP     = row[9]

            REPORT_NETID    = row[6]

            REPORT_CALLSIGN = row[11]

            if len(row) < 13:
                row.append("---")

            REPORT_NAME     = row[12]

            if REPORT_LOGP =='ECHO/PARROT':
                BGCLASS = "tgPurple"
            else:
                BGCLASS = "tgWhite"

            logTable = logTable + "<tr class='" + BGCLASS + "'><td>" + REPORT_DATE[:10] + "</td><td>" + REPORT_DATE[11:16] + "</td><td>" + REPORT_TS[2:] + "</td><td class='callsign'><a target='_blank' href=https://qrz.com/db/" + REPORT_CALLSIGN + ">" + REPORT_CALLSIGN + "</a></td><td class='dmrid'>(" + REPORT_DMRID + ")</td><td class='firstname'>" + REPORT_NAME + "</td><td class='talkgroup'>"+REPORT_TGID[2:]+"</td><td class='alias' style='color:'" + BGCLASS + ">" + REPORT_LOGP+"</td><td class='delay'>"+REPORT_DELAY+"</td><td class='netid'>"+REPORT_NETID+"</td><td class='infra'>"+REPORT_INFRA+"</td></tr>\n"

        logTable = logTable + "</tbody></table>"
        return logTable

######################################################################
#
# PROCESS INCOMING MESSAGES AND TAKE thE CORRECT ACTION DEPENING ON
#    THE OPCODE
#
def process_message(_bmessage):
    global CTABLE, CONFIG, BRIDGES, CONFIG_RX, BRIDGES_RX, MESSAGEJ
    _message = _bmessage.decode('utf-8', 'ignore')
    opcode = _message[:1]
    _now = strftime('%Y-%m-%d %H:%M:%S %Z', localtime(time()))

    if opcode == OPCODE['CONFIG_SND']:
        logging.debug('got CONFIG_SND opcode')
        CONFIG = load_dictionary(_bmessage)
        CONFIG_RX = strftime('%Y-%m-%d %H:%M:%S', localtime(time()))

        if CTABLE['MASTERS']:
            update_hblink_table(CONFIG, CTABLE)
        else:
            build_hblink_table(CONFIG, CTABLE)

    elif opcode == OPCODE['BRIDGE_SND']:
        logging.debug('got BRIDGE_SND opcode')
        BRIDGES = load_dictionary(_bmessage)
        BRIDGES_RX = strftime('%Y-%m-%d %H:%M:%S', localtime(time()))
        if BRIDGES_INC:
           BTABLE['BRIDGES'] = build_bridge_table(BRIDGES)

    elif opcode == OPCODE['LINK_EVENT']:
        logging.info('LINK_EVENT Received: {}'.format(repr(_message[1:])))

    elif opcode == OPCODE['BRDG_EVENT']:
        logging.info('BRIDGE EVENT: {}'.format(repr(_message[1:])))

        p = _message[1:].split(",")
        rts_update(p)
        opbfilter = get_opbf()

        REPORT_TYPE     = p[0]
        REPORT_RXTX     = p[2]
        REPORT_SRC_ID   = p[5]

        if REPORT_TYPE == 'GROUP VOICE' and REPORT_RXTX != 'TX' and REPORT_SRC_ID not in opbfilter:
            REPORT_DATE     = _now[0:10]
            REPORT_TIME     = _now[11:16]
            REPORT_PACKET   = p[1]
            REPORT_SYS      = p[3]
            REPORT_DMRID    = p[6]
            REPORT_TS       = p[7]
            REPORT_TGID     = p[8]
            REPORT_ALIAS    = alias_tgid(int(p[8]), talkgroup_ids)
            REPORT_CALLSIGN = alias_only(int(p[6]), subscriber_ids)[0].strip()
            REPORT_NAME     = alias_only(int(p[6]), subscriber_ids)[1].strip()
            REPORT_BOTH     = alias_short(int(p[6]), subscriber_ids)
            jsonStr = {}

            if REPORT_PACKET == 'END':
                REPORT_DELAY    = int(float(p[9]))

                # read saved history
                with open(LOG_PATH + "lastheard.json", 'r') as infile:
                    traffic = json.load(infile)
                    MESSAGEJ = traffic["TRAFFIC"]

                # append new entry
                jsonStr = { 'DATE': REPORT_DATE, 'TIME': REPORT_TIME, 'TYPE': REPORT_TYPE[6:], 'PACKET': REPORT_PACKET, 'SYS': REPORT_SYS, 'SRC_ID': REPORT_SRC_ID, 'TS': REPORT_TS, 'TGID': REPORT_TGID, 'ALIAS': REPORT_ALIAS, 'DMRID': REPORT_DMRID, 'CALLSIGN': REPORT_CALLSIGN, 'NAME': REPORT_NAME, 'DELAY': REPORT_DELAY }
                MESSAGEJ.append(jsonStr)

                # keep only the N last
                MESSAGEJ = MESSAGEJ[-LASTHEARDSIZE:]

                # write back to disk new history
                with open(LOG_PATH + "lastheard.json", 'w') as outfile:
                    json.dump({ "TRAFFIC" : MESSAGEJ }, outfile, indent=4)

                # log only to file if system is NOT OpenBridge event (not logging open bridge system, name depends on your OB definitions)
                # and transmit time is LONGER as N sec (make sense for very short transmits)
                if LASTHEARD_INC and int(float(p[9])) > 0:
                    log_lh_message = '{},{},{},{},{},{},{},TS{},TG{},{},{},{}'.format(_now, REPORT_DELAY, REPORT_TYPE, REPORT_PACKET, REPORT_SYS, REPORT_SRC_ID, alias_call(int(REPORT_SRC_ID), subscriber_ids), REPORT_TS, REPORT_TGID,alias_tgid(int(REPORT_TGID),talkgroup_ids),REPORT_DMRID, alias_short(int(REPORT_DMRID), subscriber_ids))
                    # append to file
                    lh_logfile = open(LOG_PATH + "lastheard.log", "a")
                    lh_logfile.write(log_lh_message + '\n')
                    lh_logfile.close()

            elif REPORT_PACKET == 'START':
                jsonStr = { 'DATE': REPORT_DATE, 'TIME': REPORT_TIME, 'TYPE': REPORT_TYPE[6:], 'PACKET': REPORT_PACKET, 'SYS': REPORT_SYS, 'SRC_ID': REPORT_SRC_ID, 'TS': REPORT_TS, 'TGID': REPORT_TGID, 'ALIAS': REPORT_ALIAS, 'DMRID': REPORT_DMRID, 'CALLSIGN': REPORT_CALLSIGN, 'NAME': REPORT_NAME, 'DELAY': 0 }

            elif REPORT_PACKET == 'END WITHOUT MATCHING START':
                jsonStr = { 'DATE': REPORT_DATE, 'TIME': REPORT_TIME, 'TYPE': REPORT_TYPE[6:], 'PACKET': REPORT_PACKET, 'SYS': REPORT_SYS, 'SRC_ID': REPORT_SRC_ID, 'TS': REPORT_TS, 'TGID': REPORT_TGID, 'ALIAS': REPORT_ALIAS, 'DMRID': REPORT_DMRID, 'CALLSIGN': REPORT_CALLSIGN, 'NAME': REPORT_NAME, 'DELAY': 0 }
            else:
                jsonStr = { 'DATE': _now[0:10], 'TIME': _now[11:16], 'PACKET' : 'UNKNOWN GROUP VOICE LOG MESSAGE' }

            dashboard_server.broadcast( {"TRAFFIC": jsonStr  } )
        else:
            logging.debug('{} UNKNOWN LOG MESSAGE'.format(_now[10:19]))

    else:
        logging.debug('got unknown opcode: {}, message: {}'.format(repr(opcode), repr(_message[1:])))

def load_dictionary(_message):
    data = _message[1:]
    return loads(data)
    logging.debug('Successfully decoded dictionary')

######################################################################
#
# COMMUNICATION WITH THE HBlink INSTANCE
#
class report(NetstringReceiver):
    def __init__(self):
        pass

    def connectionMade(self):
        pass

    def connectionLost(self, reason):
        pass

    def stringReceived(self, data):
        process_message(data)


class reportClientFactory(ReconnectingClientFactory):
    def __init__(self):
        logging.info('reportClient object for connecting to HBlink.py created at: %s', self)

    def startedConnecting(self, connector):
        logging.info('Initiating Connection to Server.')
        if 'dashboard_server' in locals() or 'dashboard_server' in globals():
            dashboard_server.broadcast({ "STATUS": "Connection to HBlink Established" } )

    def buildProtocol(self, addr):
        logging.info('Connected.')
        logging.info('Resetting reconnection delay')
        self.resetDelay()
        return report()

    def clientConnectionLost(self, connector, reason):
        CTABLE['MASTERS'].clear()
        CTABLE['PEERS'].clear()
        CTABLE['OPENBRIDGES'].clear()
        BTABLE['BRIDGES'].clear()
        logging.info('Lost connection.  Reason: %s', reason)
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)
        dashboard_server.broadcast({ "STATUS": "Connection to HBlink Lost" })

    def clientConnectionFailed(self, connector, reason):
        logging.info('Connection failed. Reason: %s', reason)
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

######################################################################
#
# WEBSOCKET COMMUNICATION WITH THE DASHBOARD CLIENT
#
class dashboard(WebSocketServerProtocol):
    def onConnect(self, request):
        logging.info('Client connecting: %s', request.peer)

    def onOpen(self):
        logging.info('WebSocket connection open.')
        self.factory.register(self)

        _message = {}
        _message["CTABLE"] = CTABLE
        _message["EMPTY_MASTERS"] = EMPTY_MASTERS
        with open(PATH + LOCAL_SUB_FILE, 'r') as infile:
            _message["USERS"] = json.load(infile)
        self.sendMessage(json.dumps({ "CONFIG": _message }, ensure_ascii = False).encode('utf-8'))

        # _message = {}
        # _message["BTABLE"] = BTABLE
        # self.sendMessage(json.dumps({ "BTABLE": _message }, ensure_ascii = False).encode('utf-8'))

        # read saved history or create traffic file for later
        if os.path.exists(LOG_PATH + "lastheard.json"):
            with open(LOG_PATH + "lastheard.json", 'r') as infile:
                _message = json.load(infile)
                if _message and _message["TRAFFIC"]:
                    _message = _message["TRAFFIC"][-TRAFFICSIZE:]
                    self.sendMessage(json.dumps({ "TRAFFIC": _message }, ensure_ascii = False).encode('utf-8'))
                else:
                    logging.info("Creating empty " + LOG_PATH + "lastheard.json")
                    with open(LOG_PATH + "lastheard.json", 'w') as outfile:
                        json.dump({ "TRAFFIC" : [] }, outfile)
        else:
            logging.info("Creating empty " + LOG_PATH + "lastheard.json")
            with open(LOG_PATH + "lastheard.json", 'w') as outfile:
                json.dump({ "TRAFFIC" : [] }, outfile)

    def connectionLost(self, reason):
        WebSocketServerProtocol.connectionLost(self, reason)
        self.factory.unregister(self)

    def onClose(self, wasClean, code, reason):
        logging.info('WebSocket connection closed: %s', reason)


class dashboardFactory(WebSocketServerFactory):

    def __init__(self, url):
        WebSocketServerFactory.__init__(self, url)
        self.clients = {}

    def register(self, client):
        if client not in self.clients:
            logging.info('registered client %s', client.peer)
            self.clients[client] = time()

    def unregister(self, client):
        if client in self.clients:
            logging.info('unregistered client %s', client.peer)
            del self.clients[client]

    def broadcast(self, msg):
        logging.debug('broadcasting message to: %s', self.clients)
        for c in self.clients:
            c.sendMessage(json.dumps(msg, ensure_ascii = False).encode('UTF-8'))
            logging.debug('message sent to %s', c.peer)

######################################################################
#
# STATIC WEBSERVER
#
class staticFile(Resource):
    def __init__(self, file_Name, file_Folder, file_contentType):
        self.file_Name = file_Name
        self.file_Folder = file_Folder
        self.file_contentType = file_contentType
        Resource.__init__(self)

    def render_GET(self, request):
        @defer.inlineCallbacks
        def _feedfile():
            filepath = "{}/{}".format(PATH + self.file_Folder, self.file_Name.decode("UTF-8"))

            @defer.inlineCallbacks
            def _setContentDispositionAndSend(file_path, file_name, content_type):
                request.setHeader('content-disposition', 'filename=' + file_name.decode("UTF-8"))
                request.setHeader('content-type', content_type)

                with open(file_path, 'rb') as f:
                    yield FileSender().beginFileTransfer(f, request)
                    f.close()

                defer.returnValue(0)

            if os.path.exists(filepath):
                yield _setContentDispositionAndSend(filepath, self.file_Name, self.file_contentType)
            else:
                request.setResponseCode(http.NOT_FOUND)

            request.finish()

            defer.returnValue(0)

        _feedfile()
        return server.NOT_DONE_YET

class loglast(Resource):
    def __init__(self):
        Resource.__init__(self)

    def render_GET(self, request):
        loglast_html = get_template(PATH + "templates/loglast_template.html")
        loglast_html = loglast_html.replace("<<<system_name>>>", REPORT_NAME)
        return str.encode(loglast_html.replace("<<<logtable_html>>>", createLogTable()))

class web_server(Resource):
    def __init__(self):
        Resource.__init__(self)

    def getChild(self, name, request):
        page = name.decode("utf-8")

        logging.info("requested page \"" + page + "\"")

        if page == '':
            return self

        if page == 'loglast.html':
            return loglast()

        #
        # deal with static files (images, css etc...)
        # call static file with file name, location folder, controlType
        #
        if page.endswith(".html") or page.endswith(".htm"):
            return staticFile(name, "html", "text/html; charset=utf-8")
        if page.endswith(".css"):
            return staticFile(name, "css", "text/css; charset=utf-8")
        elif page.endswith(".js"):
            return staticFile(name, "scripts", "text/html; charset=utf-8")
        elif page.endswith(".jpg") or page.endswith(".jpeg"):
            return staticFile(name, "images", "image/jpeg")
        elif page.endswith(".gif"):
            return staticFile(name, "images", "image/gif")
        elif page.endswith(".png"):
            return staticFile(name, "images", "image/png")
        elif page.endswith(".svg"):
            return staticFile(name, "images", "image/svg+xml")
        elif page.endswith(".ico"):
            return staticFile(name, "images", "image/x-icon")
        elif page.endswith(".json"):
            return staticFile(name, "assets", "application/json")

        return NoResource()

    def render_GET(self, request):
        logging.info('static website requested: %s', request)

        if WEB_AUTH:
          user = WEB_USER.encode('utf-8')
          password = WEB_PASS.encode('utf-8')
          auth = request.getHeader('Authorization')
          if auth and auth.split(' ')[0] == 'Basic':
             decodeddata = base64.b64decode(auth.split(' ')[1])
             if decodeddata.split(b':') == [user, password]:
                 logging.info('Authorization OK')
                 return index_html.encode('utf-8')

          request.setResponseCode(http.UNAUTHORIZED)
          request.setHeader('www-authenticate', 'Basic realm="realmname"')
          logging.info('Someone wanted to get access without authorization')

          return "<html<head></hread><body style=\"background-color: #EEEEEE;\"><br><br><br><center> \
                    <fieldset style=\"width:600px;background-color:#e0e0e0e0;text-algin: center; margin-left:15px;margin-right:15px; \
                     font-size:14px;border-top-left-radius: 10px; border-top-right-radius: 10px; \
                     border-bottom-left-radius: 10px; border-bottom-right-radius: 10px;\"> \
                  <p><font size=5><b>Authorization Required</font></p></filed></center></body></html>".encode('utf-8')
        else:
            return index_html.encode('utf-8')

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        filename = (LOG_PATH + LOG_NAME),
        filemode='a',
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)
    logger = logging.getLogger(__name__)

    logging.info('monitor.py starting up')
    logger.info('\n\n\tCopyright (c) 2016, 2017, 2018, 2019\n\tThe Regents of the K0USY Group. All rights reserved.' \
                '\n\n\tPython 3 port:\n\t2019 Steve Miller, KC1AWV <smiller@kc1awv.net>' \
                '\n\n\tHBMonitor v1 SP2ONG 2019-2021' \
                '\n\n\tHBJSON v2.0.0:\n\t2021 Jean-Michel Cohen, F-16987\n\n')

    # Check lastheard.log file
    if os.path.isfile(LOG_PATH+"lastheard.log"):
      try:
         check_call("sed -i -e 's|\\x0||g' {}".format(LOG_PATH+"lastheard.log"), shell=True)
         logging.info('Check lastheard.log file')
      except CalledProcessError as err:
         print(err)
    # Download alias files
    result = try_download(PATH, PEER_FILE, PEER_URL, (FILE_RELOAD * 86400))
    logging.info(result)

    result = try_download(PATH, SUBSCRIBER_FILE, SUBSCRIBER_URL, (FILE_RELOAD * 86400))
    logging.info(result)

    result = try_download(PATH, LOCAL_SUB_FILE, LOCAL_SUBSCRIBER_URL, (FILE_RELOAD * 3600))
    logging.info(result)
    # Make Alias Dictionaries
    peer_ids = mk_full_id_dict(PATH, PEER_FILE, 'peer')
    if peer_ids:
        logging.info('ID ALIAS MAPPER: peer_ids dictionary is available')

    subscriber_ids = mk_full_id_dict(PATH, SUBSCRIBER_FILE, 'subscriber')
    if subscriber_ids:
        logging.info('ID ALIAS MAPPER: subscriber_ids dictionary is available')

    local_subscriber_ids = mk_full_id_dict(PATH, LOCAL_SUB_FILE, 'local_subscriber')
    if subscriber_ids:
        logging.info('ID ALIAS MAPPER: local_subscriber_ids dictionary is available')

    talkgroup_ids = mk_full_id_dict(PATH, TGID_FILE, 'tgid')
    if talkgroup_ids:
        logging.info('ID ALIAS MAPPER: talkgroup_ids dictionary is available')

    local_subscriber_ids = mk_full_id_dict(PATH, LOCAL_SUB_FILE, 'subscriber')
    if local_subscriber_ids:
        logging.info('ID ALIAS MAPPER: local_subscriber_ids added to subscriber_ids dictionary')
        subscriber_ids.update(local_subscriber_ids)

    local_peer_ids = mk_full_id_dict(PATH, LOCAL_PEER_FILE, 'peer')
    if local_peer_ids:
        logging.info('ID ALIAS MAPPER: local_peer_ids added peer_ids dictionary')
        peer_ids.update(local_peer_ids)

    # Create Static Website index file
    index_html = get_template(PATH + "templates/index_template.html")
    index_html = index_html.replace("<<<system_name>>>", REPORT_NAME)
    index_html = index_html.replace("<<<TGID_FILTER>>>", str(TGID_FILTER))
    index_html = index_html.replace("<<<SOCKER_SERVER_PORT>>>", str(SOCKET_SERVER_PORT))
    index_html = index_html.replace("<<<DISPLAY_LINES>>>", str(DISPLAY_LINES))

    # Start update loop
    update_stats = task.LoopingCall(build_stats)
    update_stats.start(FREQUENCY)

    # Start a timout loop
    if CLIENT_TIMEOUT > 0:
        timeout = task.LoopingCall(timeout_clients)
        timeout.start(10)

    # Connect to HBlink
    reactor.connectTCP(HBLINK_IP, HBLINK_PORT, reportClientFactory())

    # Create websocket server to push content to clients
    dashboard_server = dashboardFactory('ws://*:{}'.format(SOCKET_SERVER_PORT))
    dashboard_server.protocol = dashboard

    # Function to accept offers from the client ..
    def accept(offers):
        for offer in offers:
            if isinstance(offer, PerMessageDeflateOffer):
                return PerMessageDeflateOfferAccept(offer)

    dashboard_server.setProtocolOptions(perMessageCompressionAccept=accept)

    reactor.listenTCP(SOCKET_SERVER_PORT, dashboard_server)

    # Create static web server to push initial index.html
    root = web_server()
    factory = Site(root)
    endpoint = endpoints.TCP4ServerEndpoint(reactor, JSON_SERVER_PORT)
    endpoint.listen(factory)

    # reactor.listenTCP(JSON_SERVER_PORT, factory)

    reactor.run()

