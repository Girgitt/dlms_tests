#!/usr/bin/python3
import logging
from pathlib import Path
from types import SimpleNamespace

from gurux_serial import GXSerial
from GXDLMSReader import GXDLMSReader          # Gurux wrapper taken from https://raw.githubusercontent.com/Gurux/Gurux.DLMS.Python/refs/heads/master/Gurux.DLMS.Client.Example.python/GXDLMSReader.py
from gurux_dlms.enums import Security
from gurux_dlms import GXDLMSException
from gurux_common.enums import TraceLevel
from gurux_common.io import Parity, StopBits
from gurux_dlms.GXDLMSClient import GXDLMSClient
from gurux_dlms.enums import InterfaceType, Authentication

from utils import save_object_list, load_object_list, class_name

log = logging.getLogger("main")
logging.basicConfig(level=logging.DEBUG)

CACHE_PATH = Path("./object_cache.json")

# ---------- serial adapter ----------
sp = GXSerial("/dev/ttyUSB0")
sp.baudRate  = 9600             # works both for rs485 and IR probe
sp.dataBits  = 8
#sp.parity    = Parity.EVEN     # optical probe shuld require Even parity but works with None
sp.parity    = Parity.NONE
sp.stopBits  = StopBits.ONE
sp.open()

# ---------- DLMS addressing ----------
CLIENT_ADDR  = 4   #  1 - mng; 4 - reader
SERVER_ADDR  = 1
USE_LN       = True # Metcom uses logical-name referencing

authenticate = True

obis_list = [
    '0.0.1.0.0.255',  # clock
    '0.0.96.1.0.255',  # serial
    '0.0.96.1.1.255',  # manufacturer
    '0.0.22.0.0.255',  # COM settings (?)
    '1.0.99.2.0.255',  # profile (?)
    '0.0.96.6.0.255',  # register
    '1.0.10.8.0.255',  # active energy
]


def main():
    cli = GXDLMSClient()
    cli.clientAddress = CLIENT_ADDR
    cli.serverAddress = SERVER_ADDR

    # cli.interfaceType = InterfaceType.HDLC_WITH_MODE_E  #  supposedly the IR probe should require starting at bitrate 300 but it doesn't
    cli.interfaceType = InterfaceType.HDLC
    cli.useLogicalNameReferencing = True

    if not authenticate:
        cli.authentication = Authentication.NONE
    else:
        # LOW auth is not supported by metcom for public client
        cli.authentication = Authentication.LOW
        #cli.password = bytes.fromhex("12345678")  # leftover from tests when serial number was used instead of 12345678 and proper format was unknown
        cli.password = b"12345678"

    # Only needed for gurux_dlms installed from wheel which is missing ciphering attribute
    cli.ciphering = SimpleNamespace(security=Security.NONE)

    #reader = GXDLMSReader(cli, sp, TraceLevel.VERBOSE, None)
    reader = GXDLMSReader(cli, sp, TraceLevel.ERROR, None)

    reader.initializeConnection()

    try:
        # if obis_sample:
        #     log.info("READING SAMPLE OBIS list. ")
        #     import json
        #     with open('obis_list.json', 'wb') as of:
        #         of.write(json.dumps(obis_sample, indent=1).encode('utf8'))
        if not load_object_list(cli, path=CACHE_PATH, obis_filter=obis_list):
            log.info("creating objects cache")
            log.info(">>> getAssociationView; be patient - this may take a minute or two")
            reader.getAssociationView()              # pull available objects from meter
            log.info("<<< getAssociationView")
            log.info(">>> save_object_list")
            save_object_list(cli, path=CACHE_PATH)   # write cache for next run
            log.info("<<< save_object_list")

        log.info(f"USING CACHED OBJECTS. Delete cache file: {CACHE_PATH} to pull objects from your meter")

        # read every cached readable attribute again
        # for o in cli.objects:
        #     attrs = o.__dict__.get("_cached_readable", [2])  # default to 2
        #     for idx in attrs:
        #         try:
        #             val = reader.read(o, idx)
        #             print(o.logicalName, idx, val, o.className)
        #         except Exception as e:
        #             print(o.logicalName, idx, e)

        for obj in cli.objects:
            print(f"{obj.logicalName}  class={class_name(obj.objectType)}")
            for attr in obj.getAttributeIndexToRead(True):
                if not obj.canRead(attr):
                    continue
                if attr == 1:
                    continue
                try:
                    val = reader.read(obj, attr)
                    print(f"  · attr {attr}: {val}")
                except (GXDLMSException) as err:
                    print(f"  · attr {attr} ERR: {err}")
                except Exception as err:
                    print(f"  · attr {attr} EXC: {err}")

    except Exception as e:
        log.exception(e)
        log.info("If meter stopped responding suddenly this could be related to improperly terminated read attempt.")
        log.info("Quick workaround is to change client address from 1 to 4 or 4 to 1 or wait some time until")
        log.info("last session times out on the meter or power cycle the meter if it is just local testing.")
    finally:
        reader.close()


if __name__ == "__main__":
    main()
