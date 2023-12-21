#!/usr/bin/python
#Filename: mkd.py

"""
main part of mkd
import feature(s):
    * support the conception of Channel
    * splited design of display and core loop
    * a watch dog for mplayer and mkd and XServer
    
Change Log:
    2011-03-01 Modified by Tim
        add the the dog for mixer
    2010-12-06 Modified by Tim
        Add the limitation of bandwidth for downloading.
    2010-04-21 Modified by Tim
        For #2071, add a parameter '-ao alsa' for MPlayer command.
        Check if the DSPalyer is running, if do, it will wait.
"""

__VERSION__ = '0.3.1'

try:
    import psyco
    psyco.full()
except:
    print '[SUGGESTION] install psyco for speed up [SUGGESTION]'

import os
import sys
import threading
import xml.dom.minidom as minidom
import md5
import time
from socket import *
setdefaulttimeout(15) # from socket package, for http timeout
import logging
from logging import handlers
import random
import urlparse
import httplib
import fcntl
from config import USER_ROOT

HDMI_FLAG_FILE = os.path.join(USER_ROOT, 'kiosk/tmp/hdmi.connected')
HDMI_FLAG_LOCK = os.path.join(USER_ROOT, 'kiosk/tmp/hdmi.lock')
DS_FLAG_LOCK = os.path.join(USER_ROOT, ".dsplayer", "start.lock")
MIXER_FLAG_LOCK = os.path.join(USER_ROOT, "mixer", "mixer.pid")
HOST_FLAG_FILE = os.path.join(USER_ROOT, "kiosk", "var", "mkd.sys")

MKC2_DIR = os.path.join(USER_ROOT, "kiosk", "mkc2")
#PROXY_DIR = '/home/marco/works/moviemate_internal/kiosk/mkc2/proxy'
sys.path.append(MKC2_DIR)
from proxy.config import *
from proxy.conn_proxy import ConnProxy
from proxy.umg_proxy import UmgProxy

def initlog(logfile):
    log = logging.getLogger('MKD')
    log.setLevel(logging.DEBUG)

    hConsole = logging.StreamHandler()
    hConsole.setLevel(logging.DEBUG)
    hConsole.setFormatter(logging.Formatter('%(asctime)s %(name)s  %(levelname)s \t %(message)s'))
    log.addHandler(hConsole)

    #hFile = handlers.RotatingFileHandler(logfile, 'a', 204800, 7)
    hFile = handlers.TimedRotatingFileHandler(logfile, 'D', 1, 10) # last 10days log
    hFile.setLevel(logging.INFO)
    hFile.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s \t %(message)s'))
    log.addHandler(hFile)

    return log
trace = initlog(os.path.join(USER_ROOT, 'kiosk/var/log/mkd.log'))
trace.info('MKD STARTING')


""" unchanged system var(s) """
DATA_DIR = os.path.join(USER_ROOT, 'kiosk/var/mkd.data/')
CACHED_MEDIA_DIR = DATA_DIR + '/mm_cached/'
SYS_DIR = os.path.join(USER_ROOT, 'kiosk/var/mkd.sys/')

if not os.path.isdir(DATA_DIR):
    print 'create data directory..'
    os.mkdir(DATA_DIR)

if not os.path.isdir(SYS_DIR):
    print 'lack of sys directory! it should not happen, dangerous!'
    os.mkdir(SYS_DIR)

if not os.path.isdir(CACHED_MEDIA_DIR):
    print 'create cached media directory..'
    os.mkdir(CACHED_MEDIA_DIR)

SYS_DEFAULT_TRAILERS = []
def _init_SYS_DEFAULT_TRAILERS():
    for filename in os.listdir(SYS_DIR):
        if filename.split('.')[-1].lower() in ('mpg', 'mpeg', 'avi', 'mov', 'asf', 'wmv', 'ogg', 'flv', 'rmvb', 'rm', 'mp4'):
            SYS_DEFAULT_TRAILERS.append(SYS_DIR+filename)
            print 'append default', filename
_init_SYS_DEFAULT_TRAILERS()
if len(SYS_DEFAULT_TRAILERS) == 0:
    print 'No any default program!\n'*1024
    #sys.exit(-1)

CHANNEL_INTERVAL = 1800 # unit: second



def url2filename(url):
    try:
        name = urlparse.urlparse(url)[2].split('/')[-1]
        if len(name) == 0:
            return 'None'
        else:
            return name
    except Exception, ex:
        trace.error('url2filename failed: %s' %ex)
        return 'None'

class Player( object ):

    def __init__(self):
        self.lockfile = open(HDMI_FLAG_LOCK, 'w')

        self.cmd_base = 'nohup mplayer -display :0 -xineramascreen 1 -fs -zoom -quiet -ao alsa '
        #self.cmd_base = 'nohup mplayer -zoom -quiet '
        #self.cmd_base = 'mplayer -display :0 -really-quiet '

    def _accquire(self):
        rev = False

        for i in xrange(50):
            try:
                fcntl.lockf(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                rev = True
                break
            except Exception, ex:
                trace.info('[Player _accquire] lock failed: %s' %(repr(ex)))
                time.sleep(0.1)
        return rev

    def _release(self):
        fcntl.lockf(self.lockfile, fcntl.LOCK_UN)
        return True

    def play(self, file):
        self.stop()

        cmd = self.cmd_base + file + ' &'
        if self._accquire():
            if os.path.isfile(HDMI_FLAG_FILE):
                os.system(cmd)
            else:
                trace.info('[Player play] hdmi NOT ready to show: %s' %(repr(file)))
            self._release()
        else:
            trace.error('[Player play] cannot get lock')

    def stop(self):
        #os.system('pkill mplayer')
        os.system("kill -9 `ps -eo pid,cmd |grep -w  'mplayer -display' | grep -v 'grep ' | awk '{print $1}'`")


class Channel( object ):
    """
    self.normal_programs format: ((ptype, pmedia, pbegintime, plength), (), ...)
    self.default_programs format:(pmedia1, pmedia2, ...)
    """

    def __init__(self, channel_source):
        self.channel_source = channel_source
        self.default_programs = list()
        self.default_programs_seq = None
        self.normal_programs = list()

        self.parse_channel()

    def add_program(self, ptype=None, pmedia=None, pbegintime=None, plength=None, is_default=None):
        if is_default:
            self.default_programs.append(pmedia)
        else:
            self.normal_programs.append((ptype, pmedia, pbegintime, plength))

    def get_default_programs_list(self):
        return self.default_programs

    def get_default_programs_seq(self):
        return self.default_programs_seq

    def get_normal_programs_list(self):
        self.normal_programs.sort(self._cmp)
        return self.normal_programs

    def _cmp(self, x, y): # compare by pbegintime
        if x[2] < y[2]:
            return -1
        elif x[2] == y[2]:
            return 0
        else: # x[2] > y[2]
            return 1

    def parse_channel(self):
        dom = minidom.parseString(self.channel_source)
        root = dom.documentElement
        self.default_programs_seq = root.getAttribute('default_program_seq')

        nprograms = root.getElementsByTagName('program')
        dprograms = root.getElementsByTagName('default_program')

        for node in nprograms:
            ptype = node.getAttribute('type')
            pbegintime = node.getAttribute('start_time')
            plength = node.getAttribute('play_time')

            if ptype == 'cached':
                pmedia = node.getElementsByTagName('orig_url')[0].firstChild.data
                pmedia = pmedia.strip()
                self.add_program(ptype=ptype, pmedia=pmedia, pbegintime=pbegintime, plength=plength, is_default=False)
            else:
                trace.error('[Channel parse_channel] type: %s is not supported now' %(ptype))

        for node in dprograms:
            pmedia = node.getElementsByTagName('file_name')[0].firstChild.data
            pmedia = pmedia.strip()
            self.add_program(pmedia=pmedia, is_default=True)


class TimerThread( threading.Thread ):

    def __init__(self, interval, timeout_func):
        self._stopEvent = threading.Event()
        self._interval = interval
        threading.Thread.__init__(self, name='TimerThread')
        self.timeout_func = timeout_func

    def run(self):
        """ main control loop """
        while not self._stopEvent.isSet():
            self.timeout_func()
            self._stopEvent.wait(self._interval)

    def join(self, timeout=None):
        """ stop the thread """
        self._stopEvent.set()
        threading.Thread.join(self, timeout)


class Downloader( threading.Thread ):

    def __init__(self, parent=None):
        threading.Thread.__init__(self, name='Downloader')
        self.scheduler = parent

        self.downloader_tasks = set()
        self.downloader_tasks_locker = threading.Lock()
        os.system('pkill wget')

        trace.info('[Downloader __init__] register this threading')

    def add(self, media):

        if urlparse.urlparse(media)[0] == '': # should never run here
            trace.debug('[Downloader add] added a local file, ignor it: %s' %media)
            return

        self.downloader_tasks_locker.acquire() ############### task_lock UP

        random_name = url2filename(media) + '.' + md5.new(media).hexdigest()
        if media in self.downloader_tasks:
            trace.info('[Downloader add] the task already in queue (%s)' %media)
            pass
        elif os.path.isfile(CACHED_MEDIA_DIR+random_name):
            try:
                w, r = os.popen2('pgrep -f %s' %(random_name))
                data = r.read()
                w.close()
                r.close()
                if data == 0:
                    trace.info('[Downloader add] the task is working (%s)' %media)
                    pass
                else:
                    trace.info('[Downloader add] set a new task to queue(-r mode)')
                    self.downloader_tasks.add(media)
            except Exception, ex:
                trace.debug('[Downloader add] pgrep error (%s)' %ex)
                pass
            pass
        elif os.path.isfile(CACHED_MEDIA_DIR+url2filename(media)):
            trace.debug('[Downloader add] file:%s has been downloaded' %media)
            pass
        else:
            trace.info('[Downloader add] set a new task to queue')
            self.downloader_tasks.add(media)

        self.downloader_tasks_locker.release() ############### task_lock DOWN

    def set(self, medias):
        os.system('pkill wget')
        for media in medias:
            self.add(media)
        trace.info('[Downloader set] list: %s' %str(medias))

    def run(self):
        while True:
            time.sleep(1)
            self.downloader_tasks_locker.acquire() ############### task_lock UP

            if len(self.downloader_tasks) == 0:
                self.downloader_tasks_locker.release() ############### task_lock DOWN
                #trace.debug('[Downloader run] no task')

                time.sleep(1)
                continue

            else:
                try:
                    url = self.downloader_tasks.pop()
                    trace.info('[Downloader run] pop a new task: %s' %(url))
                except Exception, ex:
                    trace.info('[Downloader run] pop task exception: %s' %(ex))
                    self.downloader_tasks_locker.release() ############### task_lock DOWN
                    continue

                trace.info('[Downloader run] task(s) still in set: %s' %str(self.downloader_tasks))
                self.downloader_tasks_locker.release() ############### task_lock DOWN

                random_name = url2filename(url) + '.' + md5.new(url).hexdigest()
                band = self._getBandwithLimitation()
                limit = ""
                if band > 0:
                    limit = "--limit-rate=%sk" % band
                cmd = 'wget %s --timeout=64 --tries=3 -c %s -O %s ' \
                      '-o wget.log' %(limit, url, CACHED_MEDIA_DIR+random_name)
                trace.debug('[Downloader run] exec -> %s' %cmd )
                os.system('pkill wget')
                rev = os.system(cmd)
                if rev != 0:
                    trace.error('[Downloader run] wget error (%s)' %(cmd))
                    self.downloader_tasks_locker.acquire() ############### task_lock UP
                    if len(self.downloader_tasks) == 0: # when after a task down, if no task left
                        self.scheduler.program_changed_event.set()
                    self.downloader_tasks_locker.release() ############### task_lock DOWN
                    continue

                self.scheduler.media_dir_locker.acquire()
                try:
                    if os.path.getsize(CACHED_MEDIA_DIR+random_name) <= 10240:
                        os.remove(CACHED_MEDIA_DIR+random_name)
                        trace.info('[Downloader run] get a null file, remove it')
                        #continue
                    else:
                        os.rename(CACHED_MEDIA_DIR+random_name, CACHED_MEDIA_DIR+url2filename(url))
                        trace.info('[Downloader run] get a regular file, rename it')
                except Exception, ex:
                        trace.error('[Downloader run] exception: %s' %(ex))
                self.scheduler.media_dir_locker.release()

                self.downloader_tasks_locker.acquire() ############### task_lock UP
                if len(self.downloader_tasks) == 0: # when after a task down, if no task left
                    self.scheduler.program_changed_event.set()
                self.downloader_tasks_locker.release() ############### task_lock DOWN
                
    def _getBandwithLimitation(self):
        """ Get the bandwith limitation from the config. """
        limit = 0
        try:
            proxy = UmgProxy.getInstance()
            result = proxy._getConfigByKey("bandwidth_limit")
            del proxy
            if result:
                limit = float(result)
        except Exception, ex:
            trace.debug("_getBandwithLimitation: %s" % ex)
        return limit


class Scheduler( object ):

    def __init__(self):
    
        self.lockfile = open(HDMI_FLAG_LOCK, 'w')
      
        self.program_locker = threading.Lock()
        self.media_dir_locker = threading.Lock()
        self.program_changed_event = threading.Event() # set the event will cause re-index program

        self.normal_programs = list()
        self.current_program_index = 0

        self.downloader = Downloader(self)
        self.downloader.start()

        self.channel_timer = TimerThread(CHANNEL_INTERVAL, self._get_channel)
        self.last_channel_md5 = None
        self._get_channel() # first call
        self.channel_timer.start()

        self.player = Player()

       
    def _accquire(self):
        rev = False

        for i in xrange(50):
            try:
                fcntl.lockf(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                rev = True
                break
            except Exception, ex:
                trace.info('[Player _accquire] lock failed: %s' %(repr(ex)))
                time.sleep(0.1)
        return rev

    def _release(self):
        fcntl.lockf(self.lockfile, fcntl.LOCK_UN)
        return True
    
    def _ds_mixer_is_running(self):
        """ Check if the DSPlayer is running.
        """
        is_running = False
        if os.path.exists(DS_FLAG_LOCK) or os.path.exists(MIXER_FLAG_LOCK):
            is_running = True
        return is_running

    def _check_default_trailer(self):
        """ Check and set the default trailer for the kiosk.
        @param None
        @return: None
        """
        try:
            hostId = self._get_host_id_of_kiosk()
            defaultTrailer = os.path.join(HOST_FLAG_FILE, "mmdefault.mepg")
            if hostId.lower() == "dnhost":
                defaultTrailer = os.path.join(HOST_FLAG_FILE, "dndefault.mepg")
                
            defaultMpeg = os.path.join(HOST_FLAG_FILE, "default.mpeg")
            # check if the default.mpeg is the exact default trailer
            if md5.new(defaultMpeg).hexdigest() != md5.new(defaultTrailer).hexdigest():
                os.system("cp -f %s %s" % (defaultTrailer, defaultMpeg))
        except Exception, ex:
            trace.error('[Scheduler _check_default_trailer] failed: %s' % ex)
            
    def _get_host_id_of_kiosk(self):
        """ Get the host ID for the kiosk.
        @param None
        @return: hostId
        @rtype: str
        """
        hostId = ""
        try:
            filePath = os.path.join(HOST_FLAG_FILE, ".ownership")
            # get the ownership from local disk
            if os.path.exists(filePath):
                fdr = None
                try:
                    fdr = open(filePath)
                    hostId = fdr.read()
                except Exception, ex:
                    hostId = ""
                finally:
                    if fdr:
                        fdr.close()

            # can not get the host ID from local disk
            if not hostId:
                # get the ownership from connection proxy
                proxy = ConnProxy.getInstance()
                owner = proxy.getKioskOwnership()
                del proxy
                hostId = owner.get("host_id", "")
                if hostId:
                    # save the ownership to the local disk
                    fdw = None
                    try:
                        fdw = open(filePath, "w")
                        fdw.write(str(hostId))
                    except Exception, ex:
                        pass
                    finally:
                        if fdw:
                            fdw.close()
        except Exception, ex:
            trace.error('[Scheduler _get_host_id_of_kiosk] conn proxy failed: %s' % ex)
        return hostId

    def run(self):
     
        hdmi = True
        while True:
        
            # check and set the default trailer for the kiosk
            # the default trailer is according to the host of the kiosk
            # dnhost is dndefault.mepg and others is mmdefault.mepg
            self._check_default_trailer()

            media, interval = self.get_next() # get next program, if none tell Downloader and show random trailer or default one
            if self._ds_mixer_is_running(): # check if ds or mixer is running 
                if not interval: interval = 60
                time.sleep(interval)
                continue
            
            trace.info('[Scheduler run] program by scheduler: %s, interval: %s' %(str(media), str(interval)))

            self.show(media)

            ################## sleep ##################
            begin_time = int(time.time())
            end_time = begin_time + interval
            while interval > 0:
                time.sleep(1)
                data = True
                try:
                    w, r = os.popen2("ps -eo pid,cmd |grep -w  'mplayer -display' | grep -v 'grep '")
                    data = r.read()
                    w.close()
                    r.close()
                except:
                    data = True
                    pass

               
                if not data: # mplayer crash?
                    self._accquire()
                    if not os.path.exists(os.path.join(USER_ROOT, "kiosk/tmp/hdmi.connected")):
                        hdmi = False

                    if abs( int(time.time()) - end_time ) > 3:
                    #if interval > 3:
                        if hdmi == True:
                            trace.info('[Scheduler run] detect Player crash, play a default trailer')
                            media = random.choice(SYS_DEFAULT_TRAILERS)
                            #interval = self.get_trailer_length(media)
                        else:
                            if os.path.exists(os.path.join(USER_ROOT, "kiosk/tmp/hdmi.connected")):
                                hdmi = True

                        self._release()
                        self.show(media)
                    else:
                        trace.info('[Scheduler run] detect Player crash, but next trailer coming soon')

                interval -= 1
                trace.debug('[Scheduler run] tick %d..' %(interval))
            trace.info('[Scheduler run] begin_time: %d, should interval: %d, real interval: %d' %(begin_time, end_time - begin_time, (int(time.time()) - begin_time)))

    def _downloaded(self, url):
        if urlparse.urlparse(url)[0] == '': # it's a file already in hdd
            trace.debug('[Scheduler _downloaded] ignor file:%s because it\'s a sys media' %url)
            return True

        self.media_dir_locker.acquire()
        media = url2filename(url)
        if os.path.isfile(CACHED_MEDIA_DIR+media):
            trace.debug('[Scheduler _downloaded] %s has been downloaded!' %(url))
            self.media_dir_locker.release()
            return True
        else:
            trace.debug('[Scheduler _downloaded] %s has NOT been downloaded, add it' %(url))
            self.media_dir_locker.release()
            self._do_download(url)
            return False


    def _do_download(self, media):
        self.downloader.add(media)

    def _timestring2int(self, strings): # cover "09:25:12" to (09, 25, 12)
        tmp = list()
        strings = strings.split(':')
        for item in strings:
            try:
                item = int(item)
            except:
                trace.error('[Scheduler _timestring2int] data format error, cover time failed')
                return False
            else:
                tmp.append(item)

        return tmp

    def _compute_time_delta(self, current_time, other_time):
        """ compare two time given in string format like: '03:25:50'
        return the delta in unit: seconds

        NOTICE: other_time thinked later than current_time!
        """

        if current_time < other_time:
            flag = False
        else:
            flag = True

        current_time = self._timestring2int(current_time)
        other_time = self._timestring2int(other_time)

        if current_time is False or other_time is False:
            return 1

        if flag:
            if current_time[0] > other_time[0]:
                other_time[0] += 24

        hour_delta = other_time[0] - current_time[0]
        minute_delta = other_time[1] - current_time[1]
        second_delta = other_time[2] - current_time[2]

        delta = hour_delta * 3600 + minute_delta * 60 + second_delta
        delta = delta.__abs__()
        return delta

    def get_trailer_length(self, media):
        self.media_dir_locker.acquire() ################### LOCK UP
        try:
            w, r = os.popen2('mplayer -quiet -ao null -vo null -identify -frames 0 %s | grep ID_LENGTH' %media)
            interval = r.read()
            r.close()
            w.close()

            if interval.startswith('ID_LENGTH='):
                try:
                    interval = int(float(interval[len('ID_LENGTH='):]))
                except Exception, ex:
                    interval = 8
                    trace.error('[Scheduler get_trailer_length] cannot conver interval: %s' %ex)
            else:
                trace.error('[Scheduler get_trailer_length] cannot parse string: %s' %interval)
                interval = 8

        except Exception, ex:
            trace.error('[Scheduler get_trailer_length] get length for a media: %s' %ex)
            interval = 8
        self.media_dir_locker.release() ################### LOCK DOWN

        return interval

    def get_random_trailer(self):
        self.media_dir_locker.acquire() ################### LOCK UP
        try:
            candidate = list()
            for filename in os.listdir(CACHED_MEDIA_DIR):
                if filename.lower().split('.')[-1] in ('mpg', 'mpeg', 'avi', 'mov', 'asf', 'wmv', 'ogg', 'flv', 'rmvb', 'rm', 'mp4'):
                    candidate.append(CACHED_MEDIA_DIR+'/'+filename)
            if len(candidate) >= 1:
                media = random.choice(candidate)
            else:
                media = random.choice(SYS_DEFAULT_TRAILERS)
        except Exception, ex:
            trace.error('[Scheduler get_random_trailer] cannot get random trailers: %s, use default' %ex)
            media = random.choice(SYS_DEFAULT_TRAILERS)
        self.media_dir_locker.release() ################### LOCK DOWN

        return media

    def get_next(self):
        media = None
        interval = None

        self.program_locker.acquire() ################### LOCK UP

        if len(self.normal_programs) == 0:
            trace.error('[Scheduler get_next] server error, there is no program in data')
            self.program_locker.release() ################### LOCK DOWN
            media = self.get_random_trailer()
            interval = self.get_trailer_length(media)
            return media, interval

        if self.program_changed_event.isSet():
            program_changed = True
            self.program_changed_event.clear()
        else:
            program_changed = False

        if program_changed:
            trace.info('[Scheduler get_next]: program_changed_event set, re-index')
            current_time = time.ctime().split()[3]
            self.current_program_index = 0

            index = 0
            for index in xrange(len(self.normal_programs)):
                """
                self.normal_programs format: ((ptype, pmedia, pbegintime, plength), (), ...)
                """
                if current_time < self.normal_programs[index][2]:
                    self.current_program_index = index
                    break
                else:
                    continue

            try:
                interval = self._compute_time_delta(current_time, self.normal_programs[self.current_program_index][2])
            except Exception, ex:
                trace.info('[Scheduler get_next] _compute_time_delta ERROR: %s' %ex)
                self.program_changed_event.set()
                interval = 8

            if index == 0:
                media = self.normal_programs[-1][1]
            else:
                media = self.normal_programs[index - 1][1]

            self.program_locker.release() ################### LOCK DOWN
            #return media, interval

        else: # program_changed FALSE
            try:
                media = self.normal_programs[self.current_program_index]
                interval = int(media[3])
                media = media[1]
            except Exception, ex:
                trace.info('[Scheduler get_next] internal error: %s' %ex)
                trace.debug('[Scheduler get_next] current_program_index: %d \t length of normal_programs: %d' %(self.current_program_index, len(self.normal_programs)))
                self.program_changed_event.set()
                media = self.get_random_trailer()
                interval = self.get_trailer_length(media)

            self.current_program_index += 1
            if self.current_program_index == len(self.default_programs):
                self.current_program_index = 0
            self.program_locker.release() ################### LOCK DOWN
            #return media, interval

        if self._downloaded(media):
            trace.debug('[Scheduler get_next] return media: %s, interval: %s' %(media, interval))
            return media, interval
        else:
            trace.info('[Scheduler get_next] media: %s has not been downloaded, choose a random one' %(media))
            media = self.get_random_trailer()
            interval = self.get_trailer_length(media)
            trace.debug('[Scheduler get_next] return media: %s, interval: %s' %(media, interval))
            return media, interval

    def show(self, media, interval=10):
        if type(media) is type(tuple()): # upc show, format: (upc, interval)
            pass
        else: # normal file
            if media in SYS_DEFAULT_TRAILERS:
                pass
            else:
                media = CACHED_MEDIA_DIR + url2filename(media)
        trace.info('[Scheduler show] will show media: %s' %str(media))

        self.player.play(media)
        return True

    def _get_channel(self):
        trace.debug('[Scheduler _get_channel] fetching channel......')
        ### connect to CONN proxy
        try:
            proxy = ConnProxy.getInstance()
            data = proxy.getChannelForMachine()
        except Exception, ex:
            trace.error('[Scheduler _get_channel] conn proxy failed: %s' %(ex))
            return

        if type(data) == type({}):
            if data.has_key('channel_id') and data.has_key('password'):
                channel_id = data['channel_id']
                channel_password = data['password']
                pass
            else:
                trace.error('[Scheduler _get_channel] conn proxy return content failed: %s' %(repr(data)))
                return
        else:
            trace.error('[Scheduler _get_channel] conn proxy return type failed: %s' %(repr(data)))
            return

        ### connect to UMG proxy
        try:
            proxy = UmgProxy.getInstance()
            data = proxy.getChannelXmlForKiosk(channel_id, channel_password, self.last_channel_md5)
        except Exception, ex:
            trace.error('[Scheduler _get_channel] umg proxy failed: %s' %(repr(ex)))
            return

        if data == '0':
            if self.last_channel_md5 is None: # this machineId cannot set a channel, server/ network down
                trace.error('[Scheduler _get_channel] cannot get channel! check network and server pls')
                return
            else: # XML not changed
                trace.info('[Scheduler _get_channel] channel server no news')
                return

        else: # new XML coming!
            """
            self.normal_programs format: ((ptype, pmedia, pbegintime, plength), (), ...)
            self.default_programs format:(pmedia1, pmedia2, ...)
            """
            try:
                f = open(os.path.join(USER_ROOT, 'kiosk/var/log/last_channel.xml'), 'w')
                f.write(data)
                f.close()
            except Exception, ex:
                trace.info('[Scheduler _get_channel] trace xml data failed: %s' %(ex))

            try:
                channel = Channel(data)
            except Exception, ex:
                trace.error('[Scheduler _get_channel] parse channel xml error: %s' %(ex))
                return

            self.last_channel_md5 = md5.new(data).hexdigest()

            self.program_locker.acquire()
            self.program_changed_event.set()

            self.normal_programs = channel.get_normal_programs_list()
            self.default_programs = channel.get_default_programs_list()
            self.default_programs_seq = channel.default_programs_seq

            try:
                self._pre_delete()
            except Exception, ex:
                trace.error('[Scheduler _get_channel] _pre_delete error: %s' %ex)

            try:
                self._pre_download()
            except Exception, ex:
                trace.error('[Scheduler _get_channel] _pre_download error: %s' %ex)

            self.program_locker.release()
            trace.info('[Scheduler _get_channel] channel changed')

    def _pre_delete(self):
        """
        after channel changed, delete unused media according to new source
        """
        programs = set()
        for item in self.normal_programs:
            programs.add(url2filename(item[1]))

        trace.info('[Scheduler _pre_delete] new programs will show: %s' %str(programs))

        self.media_dir_locker.acquire() ########################################## Locked
        delete_files = set()
        for dfile in os.listdir(CACHED_MEDIA_DIR):
            if os.path.isfile(CACHED_MEDIA_DIR+'/'+dfile):
                if dfile[:dfile.rfind('.')] in programs: # downloading
                    continue
                if dfile not in programs:
                    delete_files.add(dfile)

        for dfile in delete_files:
            trace.info('[Scheduler _pre_delete] deleting unused trailers: %s' %dfile)
            try:
                os.remove(CACHED_MEDIA_DIR+'/'+dfile)
            except Exception, ex:
                trace.error('[Scheduler _pre_delete] remove unused file error: %s' %ex)
        self.media_dir_locker.release() ########################################## unLock

    def _pre_download(self):
        """
        after channel changed, throw all un-downloaded trailers to Downloader working queue
        """
        tmp = set()
        for item in self.normal_programs:
            tmp.add(item[1])

        #tmp = list(tmp)
        for i in range(len(tmp)):
            item = tmp.pop()
            if url2filename(item) in os.listdir(CACHED_MEDIA_DIR):
                pass
            else:
                tmp.add(item)

        trace.info('[Scheduler _pre_download] list: %s' %(str(tmp)))
        self.downloader.set(tmp)


def main():
    # Wait for the starting of mka2.
    while True:
       if os.path.exists(os.path.join(USER_ROOT, "kiosk/tmp/hdmimonitor.start")): 
           break
       time.sleep(2)

    scheduler = Scheduler()
    scheduler.run()

    sys.exit(0) # should never run here

def unit_test():
    pass

##########################
##########################
#                        #
##########################
if __name__ == '__main__':
    main()
    #unit_test()
