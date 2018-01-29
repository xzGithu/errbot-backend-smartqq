import collections
import copyreg
import json
import logging
import re
import time
import sys
import threading
import pprint
from smartQQ import Login
from calculation import getGName


from errbot.backends.base import Message, Presence, ONLINE, AWAY, Room, RoomError, RoomDoesNotExistError, \
    UserDoesNotExistError, RoomOccupant, Person, Card, Stream
from errbot.core import ErrBot
from errbot.utils import split_string_after
from errbot.rendering.ansiext import AnsiExtension, enable_format, IMTEXT_CHRS

# Can't use __name__ because of Yapsy
log = logging.getLogger('errbot.backends.Qqslack')

pat='\*'
class QqSlackPerson(Person):
    """
    This class describes a person on Qq's network.
    """

    def __init__(self, sc, userid=None, roomid=None):
        self._userid = userid
        self._roomid = roomid
        self._sc = sc

    @property
    def userid(self):
#        return self._userid
        userids = self._sc.friend_info(self._userid)
        return userids

    @property
    def username(self):
        #user = self._sc.name
#        user = self._userid
        if self._userid!=self._sc.uin:
            user = self._sc.friend_info(self._userid)
        else:
            user = self._userid
        return user

    @property
    def roomid(self):
        return self._roomid

    client = roomid
    nick = username

    # Override for ACLs
    @property
    def aclattr(self):
        # Note: Don't use str(self) here because that will return
        # an incorrect format from SlackMUCOccupant.
        return "@%s" % self.username

    @property
    def fullname(self):
#        user = self._userid
        user = self._sc.friend_info(self._userid)
        return user

    def __unicode__(self):
        return "@%s" % self.username

    def __str__(self):
        return self.__unicode__()


    def __hash__(self):
        return self.userid.__hash__()

    @property
    def person(self):
        return "@%s" % self.username


class QqSlackRoomOccupant(RoomOccupant, QqSlackPerson):
    """
    This class represents a person inside a MUC.
    """
    def __init__(self, sc, userid, roomid, bot):
        super().__init__(sc, userid, roomid)
        self._room = QqSlackRoom(roomid=roomid, bot=bot)

    @property
    def room(self):
        return self._room

    def __unicode__(self):
        return "#%s/%s" % (self._room.name, self.username)

    def __str__(self):
        return self.__unicode__()



class QqBackend(ErrBot):
    def __init__(self, config):
        super().__init__(config)
        identity = config.BOT_IDENTITY
        self.token = identity.get('grouptoken', None)
        if not self.token:
            log.fatal(
                'You need to set your token for you room name '
                'the BOT_IDENTITY setting in your configuration. Without this token I '
                'cannot connect to qq.'
            )
            sys.exit(1)
        self.sc = None  # Will be initialized in serve_once
        #compact = config.COMPACT_OUTPUT if hasattr(config, 'COMPACT_OUTPUT') else False
        self.timerForLoginReset=None
        self.timerForLogin=None
        self.timerGetMessage=None
        self.bot_identifier=None
        self.uin=None
        self.msgtype=None
        

    def loginSuccessCb(self):
        self.sc.state = 1
        self.sc.login()
        self.sc.getVfWebQQ()
        self.sc.getPsessionAndUin()
        self.sc.getFriends()
        self.sc.getGroup()
        self.sc.item = getGName(self.sc.gnamelist, self.sc.groupname)
        #timerForLoginReset.start()
        log.info('Message: login successfully')
        log.info('Message: name -> ' + self.sc.name)
        log.info('Message: uin  -> ' + str(self.sc.uin))
        #self.timerGetMessage.start()
    def timerLogin(self):
        if self.sc.state == 0:
            self.sc.isLogin(self.loginSuccessCb)
            self.timerForLogin = threading.Timer(1, self.timerLogin)
            self.timerForLogin.start()
    def getsMessage(self):
        #self.timerGetMessage = threading.Timer(1, self.getMessage)
        #self.timerGetMessage.start()
        msg = self.sc.getMessage()
        log.info(msg)
        if msg:
            mess=self.build_msg(msg)
            self.msg_event_handler(mess)

    def msg_event_handler(self,msg):
        global text,mentioned
        #try:
        if msg['group']:
            text=msg['content'][0]
            user=msg['send_uid']
            touser=msg['to_uid']
            group=msg['group']
        else:
            text=msg['content'][0]
            user=msg['send_uid']
            touser=msg['to_uid']
            group=None
        #except:
        #    log.info('-------')
        text, mentioned = self.process_mentions(text)
        msg=Message(text)
        msg.frm=QqSlackPerson(self.sc,user,group)
        msg.to=QqSlackPerson(self.sc,touser,group)
        self.callback_message(msg)
        if mentioned:
            self.callback_mention(msg, mentioned)
        
    def process_mentions(self,text):
        mentioned=[]
        ms=[]
        for i in text:
            m=re.findall('(@.*).',i)
            if m:
                ms.append(m)
        for word in ms:
            try:
                identifier=self.build_identifier(word)
            except Exception as e:
                log.debug("Tried to build an identifier from '%s' but got exception: %s", word, e)
                continue
            if isinstance(identifier, QqSlackPerson):
                log.debug('Someone mentioned')
                mentioned.append(identifier)
                text = text.replace(word, str(identifier))
        return text,mentioned
    def build_msg(self,msg):
        mess={}
        if msg['result'][0]['poll_type']=='message':
            mess['send_uid']=msg['result'][0]['value']['from_uin']
            mess['to_uid']=msg['result'][0]['value']['to_uin']
            mess['content']=msg['result'][0]['value']['content'][1:]
            mess['time']=msg['result'][0]['value']['time']
            mess['group']=None
            self.uin=msg['result'][0]['value']['from_uin']
            self.msgtype='to'
        elif msg['result'][0]['poll_type']=='group_message':
            mess['send_uid']=msg['result'][0]['value']['send_uin']
            mess['to_uid']=msg['result'][0]['value']['to_uin']
            mess['content']=msg['result'][0]['value']['content'][1:]
            mess['time']=msg['result'][0]['value']['time']
            mess['group']=msg['result'][0]['value']['group_code']
            self.uin=msg['result'][0]['value']['group_code']
            self.msgtype='group_uin'
        elif msg['result'][0]['poll_type']=='discu_message':
            mess['send_uid']=msg['result'][0]['value']['send_uin']
            mess['to_uid']=msg['result'][0]['value']['to_uin']
            mess['content']=msg['result'][0]['value']['content'][1:]
            mess['group']=None
            self.uin=msg['result'][0]['value']['did']
            self.msgtype='did'
        else:
            mess={'send_uid':'','to_uid':'','content':[],'time':'','group':''}
        log.debug("Processing qq event: %s" % msg)
        return mess
    def serve_once(self):
        self.sc=Login(self.token)
        log.info("Verifying authentication token")
        self.sc.downloadPtqr()
        self.sc.writePtqr()
        self.sc.getToken()
        self.timerForLogin=threading.Timer(1,self.timerLogin)
        self.timerForLogin.start()
        #self.timerGetMessage=threading.Timer(1,self.getMessage)
        
        log.info("Verifying authentication token")
        self.bot_identifier = QqSlackPerson(self.sc, self.sc.name)
        time.sleep(20)
        if self.sc.state:
            log.info("connected")
            self.connect_callback()
            self.reset_reconnection_count()
            try:
                while True:
                    self.getsMessage() 
            except KeyboardInterrupt:
                log.info("Interrupt received, shutting down..")
                return True
            except Exception:
                log.exception("Error reading from RTM stream:")
            finally:
                log.debug("Triggering disconnect callback")
                self.disconnect_callback()
        else:
            raise Exception('Connection failed, invalid nm?')
            self.disconnect_callback()
    def send_message(self, msg):
        log.debug('wwwwww111111 %s' %msg)
        super().send_message(msg)
        body=msg.body
        print (len(body))
        msglist = self.message_cut(body)
        for msg in msglist:
            self.sc.sendMessage(msg,self.uin,self.msgtype)

    def message_cut(self,msg):
        c=300
        msgs = [msg[i:i+c] for i in range(0,len(msg),c)]
        return msgs


    def change_presence(self, status: str = ONLINE, message: str = '') -> None:
        self.api_call('users.setPresence', data={'presence': 'auto' if status == ONLINE else 'away'})


    def build_identifier(self, txtrep:str):
        log.debug("building an identifier from %s" % txtrep)
        if txtrep.startswith('!'):
            userid=self.sc.name
            roomid=2167480848
        return QqSlackPerson(self.sc,userid,roomid)


    def build_reply(self, msg, text=None, private=False, threaded=False):
        #log.debug('Threading is %s' % threaded)
        #log.debug('msgs is %s' % msg)
        #log.debug('text is  %s ' %text)
        response = self.build_message(text)
        #log.debug('------resp %s' %response)
        response.frm = self.bot_identifier
        response.to = msg.frm
        if private:
            response.type="qq"
        log.debug('wwww---resps %s' %response)
        return response



    def shutdown(self):
        super().shutdown()

    @property
    def mode(self):
        return 'qqslack'

    def query_room(self, room):
        return QqRoom(name=room, bot=self)

    def rooms(self):
        """
        Return a list of rooms the bot is currently in.
        """
        return [QqRoom(name=roomid['name'], bot=self) for roomid in self.sc.getGroup]



class QqRoom(Room):
    def invite(self, *args) -> None:
        log.error('Not implemented')
    @property
    def joined(self) -> bool:
        log.error('Not implemented')
        return True

    def leave(self, reason: str = None) -> None:
        log.error('Not implemented')

    def create(self) -> None:
        log.error('Not implemented')

    def destroy(self) -> None:
        log.error('Not implemented')

    def join(self, username: str = None, password: str = None) -> None:
        log.error('Not implemented')

    @property
    def topic(self) -> str:
        log.error('Not implemented')
        return ''

    @property
    def occupants(self):
        log.error('Not implemented')
        return []
    @property
    def exists(self) -> bool:
        log.error('Not implemented')
        return True

    def __init__(self, name ):
        self.name = name


    def __str__(self):
        return self.name
    def __eq__(self, other):
        return other.name == self.name
