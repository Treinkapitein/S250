"""
Config.py
"""
import os

USER_ROOT = "/home/mm/"
try:
    f = open("/etc/kioskhome")
    USER_ROOT = f.read().strip()
    f.close()
except:
    pass

PROXY_DATA = {
                "MOVIE_PROXY":{
                            "SOCK_LOG_HOST":"127.0.0.1",
                            "SOCK_LOG_PORT":12345,
                            "LOG_FILE_PATH":os.path.join(USER_ROOT, "kiosk/var/log/movie_proxy.log"),
                            "LOG_FORMAT":'%(asctime)s %(name)s %(levelname)s \t %(message)s',
                            "SYNC_HOST":"127.0.0.1",
                            "SYNC_PORT":20380
                              },
                "CONN_PROXY":{
                            "SOCK_LOG_HOST":"127.0.0.1",
                            "SOCK_LOG_PORT":12345,
                            "LOG_FILE_PATH":os.path.join(USER_ROOT, "kiosk/var/log/conn_proxy.log"),
                            "LOG_FORMAT":'%(asctime)s %(name)s %(levelname)s \t %(message)s',
                            "SYNC_HOST":"127.0.0.1",
                            "SYNC_PORT":20080
                              },
                "UPG_PROXY":{
                            "SOCK_LOG_HOST":"127.0.0.1",
                            "SOCK_LOG_PORT":12345,
                            "LOG_FILE_PATH":os.path.join(USER_ROOT, "kiosk/var/log/upg_proxy.log"),
                            "LOG_FORMAT":'%(asctime)s %(name)s %(levelname)s \t %(message)s',
                            "SYNC_HOST":"127.0.0.1",
                            "SYNC_PORT":20280
                              },
                "UMG_PROXY":{
                            "SOCK_LOG_HOST":"127.0.0.1",
                            "SOCK_LOG_PORT":12345,
                            "LOG_FILE_PATH":os.path.join(USER_ROOT, "kiosk/var/log/umg_proxy.log"),
                            "LOG_FORMAT":'%(asctime)s %(name)s %(levelname)s \t %(message)s',
                            "SYNC_HOST":"127.0.0.1",
                            "SYNC_PORT":20580
                              },
                "UMS_PROXY":{
                            "SOCK_LOG_HOST":"127.0.0.1",
                            "SOCK_LOG_PORT":12345,
                            "LOG_FILE_PATH":os.path.join(USER_ROOT, "kiosk/var/log/ums_proxy.log"),
                            "LOG_FORMAT":'%(asctime)s %(name)s %(levelname)s \t %(message)s',
                            "SYNC_HOST":"127.0.0.1",
                            "SYNC_PORT":20180
                              },
             }

LOCK_FILE_PATH = os.path.join(USER_ROOT, "kiosk/tmp/thread-lock")
MKC_PATH = os.path.join(USER_ROOT, "kiosk/mkc2/")
UI_PATH = os.path.join(USER_ROOT, "kiosk/mkc2/gui/image/")
MKC_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/mkc.db")
NEW_UPC_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/new_upc.db")
UPC_DB_PATH = NEW_UPC_DB_PATH #os.path.join(USER_ROOT, "kiosk/var/db/upc.db")
SYNC_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/sync.db")
MEDIA_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/media.db")
MOVIE_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/movie.db")
MOVIE_PICTURE_PATH = os.path.join(USER_ROOT, "kiosk/var/gui/newpic/")
MOVIE_DEFAULT_PIC_NAME = "default.jpg"
DEFAULT_SOCKET_TIMEOUT = 300
MEDIA_PATH = os.path.join(USER_ROOT, "kiosk/var/gui/trailer/")
MEDIA_DEFAULT_FILE_NAME = "default.flv"
VIDEO_PATH = os.path.join(USER_ROOT, "kiosk/var/video/")
VIDEO_SERVER_HOST = "s250video.cereson.com"
VIDEO_SERVER_USER = "s250"
VIDEO_SERVER_PASSWORD = "s250_video"
VIDEO_SERVER_PATH = "videos"

# Upg proxy.
UPG_AGENT_URL = "http://192.168.1.52:9090/upg/agent/upgAgent"
POSTAUTH_SLEEP_PERIOD = 600 # Seconds.
POSTAUTH_DELAY_HOURS = 1 # Hours.
GENRE_LIMIT_COUNT = 12 

# Common
COMMON_SOCK_LOG_HOST = "127.0.0.1"
COMMON_SOCK_LOG_PORT = 12345
COMMON_LOG_FORMAT = '%(asctime)s %(name)s %(levelname)s \t %(message)s'
COMMON_LOG_FILE_SIZE = 10 * 1024 * 1024
#COMMON_LOG_FILE_SIZE = 10 * 1024
COMMON_LOG_FILE_COUNT = 5
COMMON_LOG_FILE_PATH = os.path.join(USER_ROOT, "kiosk/var/log/")

# show mode, 1: show mode; 0: real mode
SHOW_MODE = 0

# upg test, 1: test mode; 0: live mode
UPG_TEST_MODE = 1

# kiosk version
KIOSKSOFT = "V1.0.018"
FIRMWARE = "V0.3.9.6"

# check reserved
CHECK_RESERVED_SLEEP_PERIOD = 300

UPG_NEED_APIS = ("getCcInfoByCcNumber", "check_black_list_for_chip_n_pin",
                 "getCerePayCfgByAcctId", "getCerePayUserInfo",
                 "checkCerePayEmail", "registerCerePay", "topup_cerepay",
                 "getCcInfoByCcId")
LITE_UPG_HOST = "upgs.cereson.com"