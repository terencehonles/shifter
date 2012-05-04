Shifter
=======

::

    ______________________  _____ _____________                     1  2  3
      ________/ ___/___/ /_  __(_)___/ __/__/ /______ ________   R  │  │  │
        _____/___ \ __/ __ \ ___ ___/ /_ _/  __/_  _ \__/ ___/   └──┼──┼──┤
          ______/ / _/ / / /_/ / _/  __/  / /_  /  __/_/ /          │  │  │
            /____/  /_/ /_/ /_/   /_/     \__/  \___/ /_/           4  5  6


``shifter`` is a Python_ library for controlling transmission_ and uses the
version number of the newest version of transmission that it was written to
support *(it will likely work for newer versions, but there is no guarantee)*.
``shifter`` has been written in 2.x syntax and will work for both Python2.x and Python3.x starting with Python2.5.

To install::

    $ pip install shifter

or ::

    $ easy_install shifter

For versions of Python3.x ``shifter`` is converted using ``2to3``. When
installing with ``pip`` or using ``distribute``, ``shifter`` will automatically
be converted to 3.x syntax. Otherwise you can run the ``2to3`` tool manually
with the following command::

    $ 2to3 -f future -f reduce -f urllib -w shifter.py

``shifter`` was designed to be a more lightweight and consistent transmission_
RPC library than what was currently available for Python_. Instead of simply
using the keys/fields that transmission-rpc_ specifies which have a mix of
dashed separated words and mixed case words, ``shifter`` tries to convert all
keys to a more python oriented: underscore separated words. This conversion is
done so that it is still possible to specify the fields/argument specified in
`transmission-rpc`_, but if you do so your mileage may vary *(probably want to
avoid it)*.

``shifter`` is designed to work with all versions of transmission_, but for
renamed fields before and after the transmission version 1.60 (`RPC v5`_) you
must specify the correct argument names (no automatic renames)

To use ``shifter`` to control a default ``transmission-daemon`` on
``localhost``:

>>> client = shifter.Client()
>>> client.list()

which produces a list of dictionaries with the torrent information (keys are
the fields: client.list_fields), and is synonymous to calling

>>> client.torrent.get(client.list_fields)

To use different connection information:

- complete path

  >>> client = shifter.Client(address="https://host:port/path")

- default URL, but port change to 8080

  >>> client = shifter.Client(port=8080)

- default URL, but different host

  >>> client = shifter.Client(host="github.com")

``shifter``'s RPC methods are namespaced into four sections:

:Client_:

    - port_test -- return if transmission port is open.
    - blocklist_update -- update block list and return block list size.
    - *list* (`torrent.get`_ helper) -- list basic torrent info for all torrents

:Client.queue_:

    - move_bottom -- move torrent to bottom of the queue
    - move_down -- move torrent down in the queue
    - move_top -- move torrent to the top of the queue
    - move_up -- move torrent up in the queue

:Client.session_:

    - close -- shutdown the transmission daemon
    - get -- get session properties
    - set -- set session properties
    - stats -- get session statistics

:Client.torrent_:

    - add -- add a new torrent

    .. _`torrent.get`:

    - get -- get torrent properties
    - *files* (`torrent.get`_ helper) -- get file information for one or more
      torrents

    - *percent_done* (`torrent.get`_ helper) -- get torrent percent done for
      one or more torrents

    - remove -- remove a torrent from transmission and optionally delete the
      data

    - set -- set torrent properties
    - set_location -- set/move torrent location


.. source references

.. _Client:
    https://github.com/terencehonles/shifter/blob/master/shifter.py#L667

.. _Client.queue:
    https://github.com/terencehonles/shifter/blob/master/shifter.py#L338

.. _Client.session:
    https://github.com/terencehonles/shifter/blob/master/shifter.py#L345

.. _Client.torrent:
    https://github.com/terencehonles/shifter/blob/master/shifter.py#L413

.. external references

.. _Python: http://python.org/
.. _transmission: http://www.transmissionbt.com/

.. _transmission-rpc:
    https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt

.. _RPC v5:
    https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt#L593
