#!/usr/bin/env python
# -*- coding: utf-8 -*-

import curses,traceback
from threading import Thread
from optparse import OptionParser
import time,os,subprocess
import socket,socks,select,random,sys

__author__="alfred"
__date__ ="$Jan 03, 2013 2:12 PM$"

### Config
hidden_service_interface='127.0.0.1'
hidden_service_port=11009
configdir='Torirc-config'
hostnamefile='%s/hidden_service/hostname' % configdir

tor_server='127.0.0.1'
tor_server_socks_port=11109

clientRandomWait=5 # Random wait before sending messages
clientRandomNoise=10 # Random wait before sending the "noise message" to the server
serverRandomWait=5 # Random wait before sending messages 

buddywidth=20

# lists for the gui
chantext=[]
rooster=[]


## Tor glue-logic files

#tor.sh
torsh="""#!/bin/sh

trap 'kill -15 `cat tor.pid`' 15

export PATH=$PATH:/usr/sbin
tor -f torrc.txt --PidFile tor.pid &
wait
"""
#torrc.txt
torrc="""## Socks port
SocksPort %d

## INCOMING connections for the hidden service arrive at 11009 
HiddenServiceDir hidden_service
HiddenServicePort %d %s:%d

## where should tor store it's cache files
DataDirectory tor_data

## some tuning
AvoidDiskWrites 1
LongLivedPorts %d
FetchDirInfoEarly 1
CircuitBuildTimeout 30
NumEntryGuards 6
""" % (tor_server_socks_port,hidden_service_port,hidden_service_interface,hidden_service_port,hidden_service_port)

# Initialize stand-alone TOR process
def initTorDirs():
    	log ("(1) initializing directories")
	#Create dir
	TorDir=os.path.join(os.getcwd(),configdir)
	if not os.path.isdir(TorDir):
		os.mkdir(TorDir)
	#Create torrc.txt
	torrcDir=os.path.join(TorDir,"torrc.txt")
	if not os.path.exists(torrcDir):
		a=open(torrcDir,"wb")
		a.write(torrc)
		a.close()
	torshDir=os.path.join(TorDir,"tor.sh")
	if not os.path.exists(torshDir):
		#Create tor.sh
		a=open(torshDir,"wb")
		a.write(torsh)
		a.close()
                os.system("chmod +x %s" % torshDir)
	
## Log Mode
STDoutLog=False

## Return sanitized version of input string
def sanitize(string):
	out=""
	for c in string:
		if (ord(c)>=0x20) and (ord(c)<0x80):
			out+=c
	return out

### Server class
# Contains the server socket listener/writer

class Server():
	# Server rooster dictionary: nick->timestamp
	serverRooster={}
	## List of message queues to send to clients
	servermsgs=[]
	## Eliminate all nicks more than a day old
	def serverRoosterCleanThread(self):
		while True:
			time.sleep(10)
			current=time.time()
			for b in self.serverRooster:
				if current-self.serverRooster[b]>60*60*24: # More than a day old
					self.serverRooster.pop(b) #eliminate nick
			

	## Thread attending a single client
	def serverThread(self,conn,addr,msg):
		log("(ServerThread): Received connection")
		conn.setblocking(0)
		randomwait=random.randint(1,serverRandomWait)
		while (True):
			try:
				time.sleep(1)
				ready = select.select([conn], [], [], 1.0)
				if ready[0]:
					data=sanitize(conn.recv(256))
					if len(data)==0: continue
					message="%s: %s" % (self.nick,data)
					# Received PING, send PONG
					if data.startswith("/PING"):
						message=""
						msg.append(data)
						continue
					# Change nick. Note that we do not add to rooster before this operation
					if data.startswith("/nick "): 
						newnick=data[6:].strip()
						log("Nick change: %s->%s" % (self.nick,newnick))
						self.nick=newnick
						self.serverRooster[newnick]=time.time() # save/refresh timestamp
						message="Nick changed to %s" % newnick
						msg.append(message)
						continue
					# Return rooster
					if data.startswith("/rooster"):
						message = "--rooster"
						totalbuddies=len(self.servermsgs)
						for r in self.serverRooster:
							message+=" %s" % r
							totalbuddies-=1
						message+=" --anonymous:%d" % totalbuddies
						msg.append(message)
						continue
					# Send 'message' to all queues
					for m in self.servermsgs:
						m.append(message)
				# We need to send a message
				if len(msg)>0:
					randomwait-=1 # Wait some random time to add noise
					if randomwait==0:
						m=msg.pop(0)
						conn.sendall(m)
						randomwait=random.randint(1,serverRandomWait)
				# Random wait before sending noise to the client
				if random.randint(0,clientRandomNoise)==0: 
					ping="/PING "
					for i in range(120):
						ping+="%02X" % random.randint(0,255)
					msg.append(ping)
			except:
				self.servermsgs.remove(msg)
				conn.close()
				print "exiting: msgs %d" % len(self.servermsgs)
				raise
	def serverMain(self):
		global STDOutLog
		global TORclientFunctionality
		STDOutLog=True
		initTor()
		# Create server rooster cleanup thread
		t = Thread(target=self.serverRoosterCleanThread, args=())
		t.daemon = True
		t.start()
		while(TORclientFunctionality==0):
			time.sleep(1)
		log("(Main Server Thread) Tor looks active, listening on %s:%d" % (hostname,hidden_service_port))
		s=socks.socksocket(socket.AF_INET,socket.SOCK_STREAM)
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
		s.bind((hidden_service_interface,hidden_service_port))
		s.listen(5)
		while True:
			try:
				conn,addr = s.accept()
				cmsg=[]
				cmsg.append("Welcome to irc-tor, this is Server")
				self.servermsgs.append(cmsg)
				self.nick="anon_%d" % random.randint(0,10000)
				t = Thread(target=self.serverThread, args=(conn,addr,cmsg))
				t.daemon = True
				t.start()
			except KeyboardInterrupt:
				log("(Main Server Thread): Exiting")
			        exit(0)
			except:
				pass


		

def chat_help():
	pass

### commands
commands =[]

def chat_help(args): # Help
	chantext.append("\ttor-irc, %s %s" % (__author__,__date__))
	chantext.append("\tAvailable commands:")
	for c in commands:
		chantext.append("\t\t/%s: %s" % (c[0],c[2]))
	return ""
commands.append(("help",chat_help,"Local help"))


def chat_server_help(args): # Server help
	return "/serverhelp"
commands.append(("serverhelp",chat_server_help,"Request sever commands help"))

def chat_quit(args): # Quit
	exit(0)
commands.append(("quit",chat_quit,"Exit the application"))


## GUI
def changeSize(stdscr):
	global width,height
	size = stdscr.getmaxyx()
	width=size[1]
	height=size[0]

count=0
cmdline=""
inspoint=0
pagepoint=0
def redraw(stdscr):
	global textpad
	global rooster
	stdscr.clear()
	# draw Text
	line=height-3
	for i in reversed(range(len(chantext)-pagepoint)):
		try:
			stdscr.addstr(line,0,chantext[i],0)
			if line==0: break
			else: line-=1
		except:
			pass
	# draw rooster
	for i in range(len(rooster)):
		buddy=rooster[i]
		stdscr.addstr(i,width-buddywidth+1,str(buddy),0)
	# draw lines
	stdscr.hline(height-2,0,curses.ACS_HLINE,width)
	stdscr.vline(0,width-buddywidth,curses.ACS_VLINE,height-2)
	# prompt
	prompt="~ "
	stdscr.addstr(height-1,0,"%s%s" % (prompt,cmdline),0)
	stdscr.move(height-1,len(prompt)+inspoint)

# Process command line
# Returns string to send to server
def processLine(command):
	if command.startswith("/"):
		comm=command[1:].split(' ')
		for t in commands:
			if comm[0].startswith(t[0]):
				func=t[1]
				return func(comm)
	return command

## Log function
## Logs to STDOut or to the chantext channel list
def log(text):
	if (STDOutLog):
		print text
	else:
		maxlen=width-buddywidth-1
		while (True):
			if (len(text[:maxlen])>0):
				chantext.append(text[:maxlen])
			text=text[maxlen:]
			if text=='':
				break
		redraw(stdscr)
		stdscr.refresh()


## Variable signalling TOR client functionality available
TORclientFunctionality=0

# Listen to TOR STDOut and print to LOG
# Additionaly look for client functionality working
def torStdoutThread(torproc):
	global TORclientFunctionality
	global hostname
	while(True):
		line=torproc.stdout.readline()
		if line != '':
			log("(TOR):%s" % line)
		if line.find("Looks like client functionality is working")>-1:
			# Load hostname
			a=open(hostnamefile,"rb")
			hostname=a.read().strip()
			a.close()
			TORclientFunctionality=1
		time.sleep(0.2)

## Connects to TOR via Socks
def openTORSocket():
	s=socks.socksocket(socket.AF_INET,socket.SOCK_STREAM)
	s.setproxy(socks.PROXY_TYPE_SOCKS5,tor_server,tor_server_socks_port)
	s.settimeout(100)
	return s

# Client connection thread
def clientConnectionThread(stdscr,ServerOnionURL,msgs):
	global TORclientFunctionality
	global rooster
	while(TORclientFunctionality==0):
		time.sleep(1)
	log("clientConnection: TOR looks alive")		
	while(True):
		try: 
			log("Trying to connect to %s:%d" % (ServerOnionURL,hidden_service_port))
			s = openTORSocket()
			s.connect((ServerOnionURL,hidden_service_port))
			log("%s %d" % (ServerOnionURL,hidden_service_port))
			s.setblocking(0)
			log("clientConnection: Connected to %s" % ServerOnionURL)
			log("clientConnection: Autorequesting rooster...")
			msgs.append("/rooster")
			randomwait=random.randint(1,clientRandomWait)
		except:
			log("clientConnection: Can't connect!")
			log(traceback.format_exc())
			initTor()
			while(TORclientFunctionality==0):
				time.sleep(1)
			continue
		try:
			while(True):
				time.sleep(1)
				ready = select.select([s], [], [], 1.0)
				# received data from server
				if ready[0]:
					data=sanitize(s.recv(256))
					# received pong (ignore)
					if data.find("/PING ")>-1:
						continue 
					# received rooster list
					if data.startswith("--rooster"):
						rooster=[]
						for i in data.split(' '):
							rooster.append(i)
					# Write received data to channel
					log(data)
				# We need to send a message
				if len(msgs)>0:  
					randomwait-=1 # Wait some random time to add noise
					if randomwait==0:
						m = msgs.pop(0)
						s.sendall(m)
						randomwait=random.randint(1,clientRandomWait)
				# send noise in form of PINGs
				if random.randint(0,clientRandomNoise)==0:
					ping="/PING "
					for i in range(120):
						ping+="%02X" % random.randint(0,255)
					#log("Sending %s" % ping)
					msgs.append(ping)
		except:
			s.close()
			pass



def initTor():
    global tor_in, tor_out
    global TOR_CONFIG
    global tor_pid
    global tor_proc
    log ("(1) entering function initTor()")
    initTorDirs()
    old_dir = os.getcwd()
    log("(1) current working directory is %s" % os.getcwd())
    try:
        log("(1) changing working directory")
        os.chdir(configdir)
        log("(1) current working directory is %s" % os.getcwd())

        # now start tor with the supplied config file
        log("(1) trying to start Tor")

        if os.path.exists("tor.sh"):
		#os.system("killall -9 tor") # a little violent
                #let our shell script start a tor instance
                tor_proc = subprocess.Popen("./tor.sh".split(),stdout=subprocess.PIPE)
                tor_pid = tor_proc.pid
                log("(1) tor pid is %i" % tor_pid)
        else:
                log("(1) there is no Tor starter script (tor.sh)")
                tor_pid = False

        if tor_pid:
            log("(1) successfully started Tor (pid=%i)" % tor_pid)

            # we now assume the existence of our hostname file
            # it WILL be created after the first start
            # if not, something must be totally wrong.
            cnt = 0
            found = False
            while cnt <= 20:
                try:
                    log("(1) trying to read hostname file (try %i of 20)" % (cnt + 1))
                    f = open(os.path.join("hidden_service", "hostname"), "r")
                    hostname = f.read().strip()
                    log("(1) found hostname: %s" % hostname)
                    found = True
                    f.close()
                    break
                except:
                    # we wait 20 seconds for the file to appear
                    time.sleep(1)
                    cnt += 1

            if not found:
                log("(0) very strange: portable tor started but hostname could not be read")
                log("(0) will use section [tor] and not [tor_portable]")
            else:
                #in portable mode we run Tor on some non-standard ports:
                #so we switch to the other set of config-options
                log("(1) switching active config section from [tor] to [tor_portable]")
                TOR_CONFIG = "tor_portable"
                #start the timer that will log Tor Stdout to console
		t = Thread(target=torStdoutThread, args=(tor_proc,))
		t.daemon = True
		t.start()

        else:
            log("(1) no own Tor instance. Settings in [tor] will be used")

    except:
        log("(1) an error occured while starting tor, see traceback:")
        log(traceback.format_exc())           # Print the exception

    log("(1) changing working directory back to %s" % old_dir)
    os.chdir(old_dir)
    log("(1) current working directory is %s" % os.getcwd())

## Client main procedure
def clientMain(stdscr,ServerOnionURL):
	global cmdline
	global inspoint
	global pagepoint
	changeSize(stdscr)
	redraw(stdscr)
	
	global TORclientFunctionality
	global hostname
	a=open(hostnamefile,"rb")
	hostname=a.read().strip()
	a.close()
	TORclientFunctionality=1

	## Message queue to send to server
	msgs=[]
	t = Thread(target=clientConnectionThread, args=(stdscr,ServerOnionURL,msgs))
	t.daemon = True
	t.start()
	

	# Main Loop
	while 1:
		input=stdscr.getch()
		stdscr.addstr(10,10,"Char: %d " % input,0)

		# event processing
		if (input == curses.KEY_RESIZE):
			changeSize(stdscr)
		# Basic line editor
		if (input == curses.KEY_LEFT) and (inspoint>0):
				inspoint-=1
		if (input == curses.KEY_RIGHT) and (inspoint<len(cmdline)):
				inspoint+=1
		if (input == curses.KEY_BACKSPACE) and (inspoint>0):
			cmdline=cmdline[:inspoint-1]+cmdline[inspoint:]
			inspoint-=1
		if (input == curses.KEY_DC) and (inspoint<len(cmdline)):
			cmdline=cmdline[:inspoint]+cmdline[inspoint+1:]
		if (input == curses.KEY_HOME):
			inspoint=0
		if (input == curses.KEY_END):
			inspoint=len(cmdline)
		#PgUp/PgDown
		if (input == curses.KEY_PPAGE):
			pagepoint+=height-2
			if len(chantext)-pagepoint<0:
				pagepoint=len(chantext)
		if (input == curses.KEY_NPAGE):
			pagepoint-=height-2
			if pagepoint<0: pagepoint=0
		#History
		"""
		if (input == curses.KEY_UP):
		if (input == curses.KEY_DOWN):
		"""

		if (input == 10):
			tosend=processLine(cmdline)
			if len(tosend)>0:
				msgs.append(tosend)
			cmdline=""
			inspoint=0

		# Ascii key
		if input>31 and input<128:
			cmdline=cmdline[:inspoint]+chr(input)+cmdline[inspoint:]
			inspoint+=1
		redraw(stdscr)

# Client
# Init/deinit curses 
def Client(ServerOnionURL):
  global stdscr
  global STDOutLog 
  STDOutLog=False
  try:
      # Initialize curses
      stdscr=curses.initscr()
      curses.noecho()
      curses.cbreak()
      #curses.start_color()
      stdscr.keypad(1)
      clientMain(stdscr,ServerOnionURL)                    # Enter the main loop
      # Set everything back to normal
      stdscr.keypad(0)
      curses.echo()
      curses.nocbreak()
      curses.endwin()                 # Terminate curses
      exit(0)
  except:
      # In event of error, restore terminal to sane state.
      stdscr.keypad(0)
      curses.echo()
      curses.nocbreak()
      curses.endwin()
	

# Main proc:
# Parse options, invoke Server or Client
if __name__=='__main__':
  parser = OptionParser()
  parser.add_option("-c", "--connect", action="store", type="string", dest="connect", help="Acts as client, connect to server")
  parser.add_option("-s", "--server", action="store_true", dest="Server", help="Acts as server")
  (options, args) = parser.parse_args()
  if options.Server:
  	s=Server()
	s.serverMain()
  else:
   	Client(options.connect)
