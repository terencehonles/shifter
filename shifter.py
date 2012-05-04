# vim: set fileencoding=utf-8 :

# stolen from README so modeline/file encoding info isn't in help
'''
______________________  _____ _____________                     1  2  3
  ________/ ___/___/ /_  __(_)___/ __/__/ /______ ________   R  │  │  │
    _____/___ \ __/ __ \ ___ ___/ /_ _/  __/_  _ \__/ ___/   └──┼──┼──┤
      ______/ / _/ / / /_/ / _/  __/  / /_  /  __/_/ /          │  │  │
        /____/  /_/ /_/ /_/   /_/     \__/  \___/ /_/           4  5  6


``shifter`` is a library for controlling transmission and uses the version
number of the newest version of transmission that it was written to support
(it will likely work for newer versions, but there is no guarantee).
``shifter`` has been written in 2.x syntax and will work for both Python2.x
and Python3.x starting with Python2.5.
'''

from __future__ import division

import datetime
import logging
import re
import sys
import time
import urllib2

from base64 import b64decode, b64encode

try:
    from urllib import parse as urlparse
except ImportError:
    from urllib2 import urlparse

try:
    import json
except ImportError:
    import simplejson as json


__all__ = ('DAY', 'LIMIT', 'PRIORTIY', 'TORRENT', 'TORRENT_PRE_2_30',
           'TRACKER', 'Client', 'Enum', 'EnumItem', 'TransmissionJSONEncoder',
           'TransmissionRPCError', 'TransmissionSessionHandler')

# enumerate needs "start" for python2.5
if sys.version_info < (2, 6):
    def enumerate(iterable, start=0):
        for item in iterable:
            yield start, item
            start += 1

try:
    basestring
except NameError:
    basestring = str

try:
    long
except NameError:
    long = int


CAP_PATTERN = re.compile('(?<=[^A-Z])[A-Z]')
UNDERSCORE_PATTERN = re.compile('_.')

to_dashed = lambda string: string.replace('_', '-')
from_dashed = lambda string: string.replace('-', '_')

make_mixed = lambda match: match.group()[1].upper()
to_mixed = lambda string: UNDERSCORE_PATTERN.sub(make_mixed, string)

make_underscore = lambda match: '_' + match.group().lower()
from_mixed = lambda string: CAP_PATTERN.sub(make_underscore, string)

class TransmissionRPCError(RuntimeError):
    'Error raised when RPC result != "success"'
    pass

class TransmissionSessionHandler(urllib2.BaseHandler):
    '''
    Handles Transmission CSRF Protection

    https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L48
    '''

    HEADER_NAME = 'X-Transmission-Session-Id'
    HEADER_NAME_LOWER = HEADER_NAME.lower()

    def __init__(self):
        self.__csrf_tokens = {}

    def http_request(self, request):
        'adds the appropriate CSRF token to the headers'

        token = self.__csrf_tokens.get(request.get_full_url())
        if token:
            request.add_header(self.HEADER_NAME, token)

        return request

    def http_error_409(self, request, response, code, message, headers):
        'handles CSRF token expiration and resends the request'

        # cannot handle the request
        if self.HEADER_NAME not in headers: return

        url = request.get_full_url()
        self.__csrf_tokens[url] = headers[self.HEADER_NAME]

        # copy the original headers
        new_headers = dict((k, v) for k, v in request.header_items()
                           if k.lower() not in ('content-length',
                                                'content-type',
                                                self.HEADER_NAME_LOWER))

        new_request = urllib2.Request(
            url = url,
            data = request.get_data(),
            headers = new_headers,
            origin_req_host = request.get_origin_req_host(),
            unverifiable = request.is_unverifiable
        )

        # pass the timeout along only if the timeout was specified
        # (otherwise probably an old version of Python)
        additional = {}
        timeout = getattr(request, 'timeout', None)
        if timeout: additional['timeout'] = timeout

        return self.parent.open(new_request, **additional)


class TransmissionJSONEncoder(json.JSONEncoder):
    def default(self, o):
        # date{,time} is represented as seconds since epoch
        try:
            return int(time.mktime(o.timetuple()))
        except (AttributeError, TypeError): pass

        # time is represented as minutes since midnight
        # (alt_speed_time_begin, alt_speed_time_end)
        try:
            return o.minute + o.hour * 60
        except AttributeError: pass

        # EnumItem or iterable of EnumItem can be collapsed with Enum.to_mask
        try:
            if any(isinstance(i, EnumItem) for i in o):
                return Enum.to_mask(o)
        except TypeError: pass

        # a byte stream is base64 encoded
        try:
            return b64encode(o).decode('utf-8')
        except TypeError: pass

        return super(TransmissionJSONEncoder, self).default(o)


class EnumItem(int):
    '''creates an EnumItem object to hold the enum's name and value'''

    def __new__(cls, *args, **kargs):
        if len(args) != 2 and len(kargs) != 1 or args and kargs:
            raise TypeError('Two arguments or a named argument required')

        if args:
            name, value = args
        else:
            name, value = kargs.popitem()

        return super(EnumItem, cls).__new__(cls, value)

    def __init__(self, *args, **kargs):
        if args:
            self.name, value = args
        else:
            self.name, value = kargs.popitem()

    def __repr__(self):
        return '%s(%s=%d)' % (self.__class__.__name__, self.name, int(self))

class Enum(dict):
    'creates an Enum which has one or more EnumItems'

    def __init__(self, *auto_enum, **explicit_enum):
        super(Enum, self).__init__()
        self.__unique = {}
        self.__reverse = {}
        start = 0

        if auto_enum:
            # the only keyword allowed with auto_enum is "start"
            start = int(explicit_enum.pop('start', 0))

            if explicit_enum:
                raise ValueError('only one of "auto_enum" or "explicit_enum" '
                                 'should be specified')

        if auto_enum:
            iterator = ((k, i) for i, k in enumerate(auto_enum, start))
        else:
            iterator = explicit_enum.items()

        for key, value in iterator:
            enum = EnumItem(key, value)

            self.__reverse[value] = self[key] = enum
            setattr(self, key, enum)

            # auto_enum is sequential so don't build the unique mask
            if auto_enum: continue

            unique = True
            remove = None
            for added in self.__unique.keys():
                # value is or contains added (don't add)
                if added & value == added:
                    unique = False
                    break

                # added contains value (swap)
                elif value & added == value:
                    remove = added
                    break

            if remove: self.__unique.pop(remove, None)
            if unique: self.__unique[value] = enum

    def from_mask(self, mask):
        return set(v for k, v in self.__unique.items() if k & mask == k)

    @staticmethod
    def to_mask(iterable):
        try:
            return reduce((lambda x, y: x | y), iterable, 0)
        except TypeError:
            return iterable | 0

    def __call__(self, value):
        return self.__reverse.get(value)


DAY = Enum(sunday=(1<<0), monday=(1<<1), tuesday=(1<<2), wednesday=(1<<3),
           thursday=(1<<4), friday=(1<<5), saturday=(1<<6),
           # don't use binary literals for python2.5
           weekday=int('0111110', 2), weekend=int('1000001', 2),
           all=int('1111111', 2))

LIMIT = Enum('global', 'single', 'unlimited', start=0)
PRIORTIY = Enum('low', 'normal', 'high', start=-1)

TORRENT = Enum('stopped', 'check pending', 'checking', 'download pending',
               'downloading', 'seed pending', 'seeding', start=0)

TORRENT_PRE_2_30 = Enum(**{
    'check pending': (1<<0),
    'checking': (1<<1),
    'downloading': (1<<2),
    'seeding': (1<<3),
    'stopped': (1<<4)
})

TRACKER = Enum('inactive', 'waiting', 'queued', 'active', start=0)


def check_ids(ids):
    'checks if ids is a number, string or list of numbers or strings'

    valid_types = (int, long, basestring)
    if isinstance(ids, valid_types):
        return ids
    else:
        try:
            ids = list(ids)
            if not all(isinstance(id, valid_types) for id in ids):
                raise TypeError

        # not all valid types or not a sequence
        except TypeError:
            raise TypeError('Number, string or list of numbers or strings '
                            'expected. Found %r' % ids)
        else:
            return ids

def make_ids_method(name):
    def fn(self, ids):
        self._client.invoke(name, dict(ids=check_ids(ids)))

    # remove the prefix and give valid identifiers as the names
    fn.__name__ = name.split('-', 1)[1].replace('-', '_')
    return fn

def denormalize_keys(data, odd_keys, normal_fn, odd_fn):
    result = {}
    for key, value in data.items():
        if key in odd_keys:
            result[odd_fn(key)] = value
        else:
            result[normal_fn(key)] = value

    return result

def denormalize_list(data, odd_values, normal_fn, odd_fn):
    result = []
    for item in data:
        if item in odd_values:
            result.append(odd_fn(item))
        else:
            result.append(normal_fn(item))

    return result

def normalize(data):
    'search for dictionary keys to normalize'

    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            result[from_dashed(from_mixed(key))] = normalize(value)

        return result

    elif isinstance(data, list):
        return [normalize(item) for item in data]

    else:
        return data

def seconds_since_epoch(s, convert=datetime.datetime.fromtimestamp):
    if s <= 0: return
    return convert(s)


class NS(object):
    __slots__ = ('_client')

    def __init__(self, client):
        self._client = client


class QueueMethods(NS):
    move_top = make_ids_method('queue-move-top')
    move_up = make_ids_method('queue-move-up')
    move_down = make_ids_method('queue-move-down')
    move_bottom = make_ids_method('queue-move-bottom')


class SessionMethods(NS):
    _set_mixed = set(['seedRatioLimit', 'seedRatioLimited'])

    _get_map = dict(alt_speed_time_day=DAY.from_mask)
    _get_map['alt_speed_time_begin'] = _get_map['alt_speed_time_end'] = \
            lambda x: datetime.time(hour=x//60, minute=x%60)

    # TODO? handle renames (only affects < 1.60)
    _set_renamed = _get_renamed = {
        'pex-allowed': 'pex-enabled',
        'port': 'peer-port',
        'peer-limit': 'peer-limit-global',
    }

    def close(self):
        '''
        shuts transmission down

        https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L546
        '''

        self._client.invoke('session-close')

    def get(self):
        '''
        gets transmission settings

        https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L413
        '''

        response = self._client.invoke('session-get')
        normalized = normalize(response)

        # convert non standard types to their pythonic representation
        for key, map in self._get_map.items():
            if key in normalized:
                normalized[key] = map(normalized[key])

        # save the rpc_version for the case that it is needed in the future
        self._client._rpc_version = normalized.get('rpc_version')

        return normalized

    def set(self, **kargs):
        '''
        sets transmission settings

        https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L485
        '''

        # mixed case is odd in this case
        translated = denormalize_keys(kargs, odd_keys=self._set_mixed,
                                      normal_fn=to_dashed, odd_fn=to_mixed)

        self._client.invoke('session-set', translated)

    def stats(self):
        '''
        gets transmission statistics

        https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L499
        '''

        response = self._client.invoke('session-stats')

        return normalize(response)


class TorrentMethods(NS):
    start = make_ids_method('torrent-start')
    start_now = make_ids_method('torrent-start-now')
    stop = make_ids_method('torrent-stop')
    verify = make_ids_method('torrent-verify')
    reannounce = make_ids_method('torrent-reannounce')

    files_fields = set(['id', 'name', 'hash_string', 'files', 'priorities',
                        'wanted'])

    # normalization information
    _set_dashed = set(['files_wanted', 'files_unwanted', 'peer_limit',
                       'priority_high', 'priority_low', 'priority_normal'])

    _get_dashed = set(['peer_limit'])
    _add_mixed = set(['bandwidth_priority'])

    # TODO? handle renames (only affects < 1.60)
    _set_renamed = _get_renamed = {
        'speed-limit-down': 'downloadLimit',
        'speed-limit-down-enabled': 'downloadLimited',
        'speed-limit-up': 'uploadLimit',
        'speed-limit-up-enabled': 'uploadLimited',
    }

    # type conversion information
    _get_map = dict(
        bandwidth_priority = PRIORTIY,
        pieces = lambda x: b64decode(x.encode('utf-8')),
        priorities = lambda lst: [PRIORTIY(i) for i in lst],
    )

    _get_map['seed_idle_mode'] = _get_map['seed_ratio_mode'] = LIMIT

    _get_map.update(
        (i, seconds_since_epoch)
        for i in ('activity_date', 'addedDate', 'corrupt_ever',
                  'date_created', 'done_date', 'startDate',
                  'manual_announce_time')
    )

    _get_tracker_stats_map = dict(
        (i, seconds_since_epoch)
        for i in ('last_announce_start_time', 'last_announce_time',
                  'last_scrape_start_time', 'last_scrape_time',
                  'next_announce_time', 'next_scrape_time')
    )

    _get_tracker_stats_map['announce_state'] = \
        _get_tracker_stats_map['scrape_state'] = TRACKER

    def __init__(self, client):
        super(TorrentMethods, self).__init__(client)
        self._get_map = dict(status=self._map_status, **self._get_map)

    def _map_status(self, status):
        'resolve the status enum to use, and patch the map'

        if self._client._get_rpc_version() < 14:
            self.STATE = self._get_map['status'] = TORRENT_PRE_2_30
        else:
            self.STATE = self._get_map['status'] = TORRENT

        return self.STATE(status)

    def add(self, **kargs):
        '''
        adds a torrent to transmission

        ``add(filename=<url to torrent (local or remote)>)``

        or

        ``add(metainfo=<base64 encoded file data>)``

        https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L347
        '''
        if not any(kargs.get(k) for k in ('filename', 'metainfo')):
            raise TypeError('argument filename or metainfo is required')

        # mixed case is odd in this case
        translated = denormalize_keys(kargs, odd_keys=self._add_mixed,
                                      normal_fn=to_dashed, odd_fn=to_mixed)

        cookies = translated.get('cookies')
        if cookies:
            # convert cookie dictionary to list
            try:
                cookies = ['%s=%s' % pair for pair in cookies.items()]
            except (TypeError, AttributeError): pass

            # convert cookie list to string
            try:
                translated['cookies'] = '; '.join(str(c) for c in cookies)
            except TypeError: pass

        response = self._client.invoke('torrent-add', translated)
        return normalize(response.get('torrent-added'))


    def get(self, fields, ids=None, **kargs):
        '''
        gets a torrent(s) properties

        ``get(fields, ids=<all>, key=None) -> [<fields>, ...]``

        returns a list of one or more dictionaries describing the torrent(s)
        requested (all if ids=None or []). If ids is "recently-active" the
        format will be the same, but instead of one list there will be a pair
        of lists (torrents-requested, recently-removed).

        ``get(fields, ids=<all>, key='id') -> {key:<fields>, ...}``

        if the keyword only argument "key" is given then the original list
        will be mapped into a dictionary with the specified key.

        https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L119
        '''

        ids = check_ids(ids or [])
        if isinstance(fields, basestring): fields = [fields]

        # force key to be a named argument (2.x)
        key = kargs.get('key')
        if key: fields = set(fields) | set([key])

        # dashed is odd in this case
        translated = denormalize_list(fields, odd_values=self._get_dashed,
                                      normal_fn=to_mixed, odd_fn=to_dashed)

        args = dict(fields=translated)
        if ids: args['ids'] = ids

        # TODO: ensure renames are consistent
        response = self._client.invoke('torrent-get', args)

        result = [response.get('torrents')]
        if 'removed' in response: result.append(response.get('removed'))

        # normalize keys
        result = [[normalize(t) for t in l] for l in result]

        # assuming all torrents have the same keys
        # (allows hoisting the if statement)
        first_obj = result[0][0]
        for name in first_obj:
            map = self._get_map.get(name)
            if not map: continue

            for lst in result:
                for obj in lst:
                    obj[name] = map(obj[name])

        # tracker_stats mapping
        if 'tracker_stats' in first_obj:
            stats = 'tracker_stats'

            for name in first_obj[stats][0]:
                map = self._get_tracker_stats_map.get(name)
                if not map: continue

                for lst in result:
                    for obj in lst:
                        for inner in obj[stats]:
                            inner[name] = map(inner[name])

        # file_stats mapping
        if 'file_stats' in first_obj:
            stats = 'file_stats'
            if 'priority' in first_obj[stats][0]:
                for lst in result:
                    for obj in lst:
                        for inner in obj[stats]:
                            inner['priority'] = PRIORTIY(inner['priority'])

        # if a "key" was given return a keyed dictionary rather than a list
        if key:
            result = [dict((t[key], t) for t in l) for l in result]

        # removed is present
        if len(result) == 2:
            return tuple(result)
        else:
            return result[0]

    def files(self, ids=None, **kargs):
        '''
        ``files(ids=<all>, key='id') -> {key: <fields>, ...}``

        helper "torrent-get" method to return the files in a torrent(s)
        '''

        # force key to be a named argument (2.x)
        key = kargs.get('key') or 'id'
        return self.get(self.files_fields, ids=ids, key=key)

    def percent_done(self, ids=None, **kargs):
        '''
        ``percent_done(ids=<all>, key='id') -> {key: <percent_done>, ...}``

        helper "torrent-get" method to return the torrent(s) (percent done)
        '''

        # force key to be a named argument (2.x)
        key = kargs.get('key') or 'id'

        to_dict = lambda lst: dict((i[key], i['percent_done']) for i in lst)
        response = self.get(set([key, 'percent_done']), ids=ids)

        # removed is present
        if isinstance(response, tuple):
            return tuple(to_dict(lst) for lst in response)
        else:
            return to_dict(response)

    def remove(self, ids, **kargs):
        '''
        removes a torrent(s) from transmission

        https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L380
        '''

        translated = dict((to_dashed(k), v) for k, v in kargs.items())
        translated['ids'] = check_ids(ids)

        self._client.invoke('torrent-remove', translated)

    def set(self, ids, **kargs):
        '''
        sets a torrent(s) properties

        https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L82
        '''

        # dashed is odd in this case
        translated = denormalize_keys(kargs, odd_keys=self._set_dashed,
                                      normal_fn=to_mixed, odd_fn=to_dashed)

        translated['ids'] = check_ids(ids)

        self._client.invoke('torrent-set', translated)

    def set_location(self, ids, location, **kargs):
        '''
        moves a torrent(s)

        https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L394
        '''

        kargs['ids'] = check_ids(ids)
        kargs['location'] = location
        self._client.invoke('torrent-set-location', kargs)


class Client(object):
    '''
    creates a transmission rpc client which communicates over JSON/HTTP
    '''

    json_encoder = TransmissionJSONEncoder(ensure_ascii=False)
    json_decoder = json.JSONDecoder()

    list_fields = set(['id', 'hash_string', 'name', 'size_when_done',
                       'left_until_done' , 'eta', 'status', 'rate_upload',
                       'rate_download', 'uploaded_ever' , 'downloaded_ever',
                       'upload_ratio', 'queue_position'])

    log = logging.getLogger('shifter.client')

    def __init__(self, address='http://localhost:9091/transmission/rpc',
                 scheme=None, host=None, port=None, path=None, query=None,
                 timeout=None, urlopener=None):

        self.session = SessionMethods(self)
        self.torrent = TorrentMethods(self)
        self.queue = QueueMethods(self)

        self._rpc_version = None
        self.timeout = timeout

        # any explicit keyword arguments override the default address
        url_info = urlparse.urlsplit(address)
        if scheme is None: scheme = url_info.scheme
        if host is None: host = url_info.hostname
        if port is None: port = url_info.port
        if path is None: path = url_info.path
        if query is None: query = url_info.query

        self.endpoint = urlparse.urlunsplit((scheme, '%s:%d' % (host, port),
                                             path, query, ''))

        if urlopener:
            self.connection = urlopener
            self.connection.add_handler(TransmissionSessionHandler())
        else:
            self.connection = urllib2.build_opener(TransmissionSessionHandler)

    def _get_rpc_version(self):
        if self._rpc_version: return self._rpc_version

        self.session.get()
        return self._rpc_version

    def blocklist_update(self):
        'updates the block list and returns its size'

        return self.invoke('blocklist-update').get('blocklist-size')

    def invoke(self, method, args=None):
        '''invokes a method via transmission's rpc protocol'''

        data = dict(method=method)

        if args: data['arguments'] = args

        additional = {}
        if sys.version_info > (2, 5) and self.timeout:
            additional['timeout'] = self.timeout

        # encoding should be UTF-8
        # https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L19
        encoded_data = self.json_encoder.encode(data).encode('utf-8')
        self.log.debug('message to %r POST %r', self.endpoint, encoded_data)

        response = self.connection.open(self.endpoint, encoded_data,
                                      **additional)

        decoded_data = response.read().decode('utf-8')
        self.log.debug('message from %r: %r', self.endpoint, decoded_data)

        info = self.json_decoder.decode(decoded_data)
        if info['result'] != 'success':
            raise TransmissionRPCError(info['result'])

        return info['arguments']

    def list(self, **kargs):
        '''
        ``list(key='id') -> {key: <fields>, ...}``

        helper "torrent-get" method to return all the torrents
        '''

        # force key to be a named argument (2.x)
        key = kargs.get('key') or 'id'
        return self.torrent.get(self.list_fields, key=key)

    def port_test(self):
        'returns whether the listening port is open'

        return self.invoke('port-test').get('port-is-open')
