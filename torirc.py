#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2012-2013, Alfredo Ortega <alfred@groundworkstech.com>
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#

import curses,traceback
from threading import Thread
from optparse import OptionParser
import time,os,subprocess
import socket,select,random,sys

try:
	import socks
except:
	print "Can't load socksiphy module."
	print "Try installing python-socksipy in debian-like distros"
	exit(0)

__author__="alfred"
__date__ ="$Jan 06, 2013$"

## ---------- Start of user-configurable variables ----------------

# Directories
configdir='Torirc-config'
hostnamefile='%s/hidden_service/hostname' % configdir

# Network-related variables
hidden_service_interface='127.0.0.1'
hidden_service_port=11009
tor_server='127.0.0.1'
tor_server_socks_port=11109
minimum_message_len=256

## Time "noise". Increase this value in dire situations

clientRandomWait=5 # Random wait before sending messages
clientRandomNoise=10 # Random wait before sending the "noise message" to the server
serverRandomWait=5 # Random wait before sending messages 

## Gui
buddywidth=20

## ---------- End of user-configurable variables -----------------

# lists for the gui
chantext=[]
roster=[]

## Tor glue files

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

## Log Mode (Server logs to stdout, client do not)
STDoutLog=False

## Variable signalling TOR client functionality available
TORclientFunctionality=0

# Initialize TOR config directory
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
	
# Add padding to a message up to minimum_message_len
def addpadding(message):
	if len(message)<minimum_message_len:
		message+=chr(0)
		for i in range(minimum_message_len-len(message)):
			message+=chr(random.randint(ord('a'),ord('z')))
	return message
		

## Return sanitized version of input string
def sanitize(string):
	out=""
	for c in string:
		if (ord(c)==0): break # char(0) marks start of padding
		if (ord(c)>=0x20) and (ord(c)<0x80):
			out+=c
	return out


## Load hidden hostname from Tor config directory
def loadhostname():
	global hostname
	a=open(hostnamefile,"rb")
	hostname=a.read().strip()
	a.close()
	return hostname


## detects TOR by binding to the socks port
def detectTOR():
	try:
		s=socks.socksocket(socket.AF_INET,socket.SOCK_STREAM)
		s.settimeout(1)
		s.connect((tor_server,tor_server_socks_port))
		s.close()
		return True
	except:	return False

## Starts portable TOR process, torchat-style
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


### Server class
# Contains the server socket listener/writer

class Server():
	# Server roster dictionary: nick->timestamp
	serverRoster={}

	## List of message queues to send to clients
	servermsgs=[]

	## channel name
	channelname=""

	## Eliminate all nicks more than a day old
	def serverRosterCleanThread(self):
		while True:
			time.sleep(10)
			current=time.time()
			waittime = random.randint(60*60*10,60*60*36) # 10 hours to 1.5 days
			for b in self.serverRoster:
				if current-self.serverRoster[b]>waittime: # Idle for more than the time limit
					self.serverRoster.pop(b) #eliminate nick
					waittime = random.randint(60*60*10,60*60*36)
			
	## Thread attending a single client
	def serverThread(self,conn,addr,msg,nick):
		log("(ServerThread): Received connection")
		conn.setblocking(0)
		randomwait=random.randint(1,serverRandomWait)
		while (True):
			try:
				time.sleep(1)
				ready = select.select([conn], [], [], 1.0)
				if ready[0]:
					data=sanitize(conn.recv(minimum_message_len))
					if len(data)==0: continue
					message="%s: %s" % (nick,data)
					# Received PING, send PONG
					if data.startswith("/PING"):
						message=""
						msg.append(data)
						continue
					# Change nick. Note that we do not add to roster before this operation
					if data.startswith("/nick "): 
						newnick=data[6:].strip()
						if newnick.startswith("--"):continue
						log("Nick change: %s->%s" % (nick,newnick))
						nick=newnick
						self.serverRoster[newnick]=time.time() # save/refresh timestamp
						message="Nick changed to %s" % newnick
						msg.append(message)
						continue
					# Return roster
					if data.startswith("/roster"):
						message = "--roster"
						message+=" %s" % self.channelname
						totalbuddies=len(self.servermsgs)
						for r in self.serverRoster:
							message+=" %s" % r
							totalbuddies-=1
						message+=" --anonymous:%d" % totalbuddies
						msg.append(message)
						continue
					if data.startswith("/serverhelp"):
						msg.append("These are the commands I support:")
						msg.append("     /serverhelp  : Send this help")
						msg.append("     /roster      : Send the buddy list")
						msg.append("     /nick <nick> : Changes the nick")
						continue
					# refresh timestamp
					self.serverRoster[nick]=time.time() 
					# Send 'message' to all queues
					for m in self.servermsgs:
						m.append(message)
				# We need to send a message
				if len(msg)>0:
					randomwait-=1 # Wait some random time to add noise
					if randomwait==0:
						m = addpadding(msg.pop(0))
						conn.sendall(m)
						randomwait=random.randint(1,serverRandomWait)
				# Random wait before sending noise to the client
				if random.randint(0,clientRandomNoise)==0: 
					ping="/PING "
					for i in range(120):
						ping+="%02X" % random.randint(ord('a'),ord('z'))
					msg.append(ping)
			except:
				self.servermsgs.remove(msg)
				conn.close()
				print "exiting: msgs %d" % len(self.servermsgs)
				raise

	## Server main thread
	def serverMain(self,channel_name):
		global STDOutLog
		global TORclientFunctionality
		STDOutLog=True
		self.channelname=channel_name
		log("(Main Server Thread) Trying to connect to existing tor...")
		# Starts tor if not active
		if detectTOR():
			loadhostname()
			TORclientFunctionality=1
		else:
			initTor()
			while(TORclientFunctionality==0):
				time.sleep(1)
		# Start server socket
		s=socks.socksocket(socket.AF_INET,socket.SOCK_STREAM)
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
		s.bind((hidden_service_interface,hidden_service_port))		
		log("(Main Server Thread) Tor looks active, listening on %s" % hostname)
		s.listen(5)
		# Create server roster cleanup thread
		t = Thread(target=self.serverRosterCleanThread, args=())
		t.daemon = True
		t.start()
		while True:
			try:
				conn,addr = s.accept()
				cmsg=[]
				nick="anon_%d" % random.randint(0,10000)
				cmsg.append("Welcome %s, this is %s" % (nick,self.channelname))
				self.servermsgs.append(cmsg)
				t = Thread(target=self.serverThread, args=(conn,addr,cmsg,nick))
				t.daemon = True
				t.start()
			except KeyboardInterrupt:
				log("(Main Server Thread): Exiting")
			        exit(0)
			except:
				pass

## Client commands
commands =[]

def chat_help():
	pass

# Client Help
def chat_help(args): 
	chantext.append("\ttor-irc, %s %s" % (__author__,__date__))
	chantext.append("\tAvailable commands:")
	for c in commands:
		chantext.append("\t\t/%s: %s" % (c[0],c[2]))
	return ""
commands.append(("help",chat_help,"Local help"))


# Server help
def chat_server_help(args): 
	return "/serverhelp"
commands.append(("serverhelp",chat_server_help,"Request sever commands help"))

# Quit
def chat_quit(args): 
	exit(0)
commands.append(("quit",chat_quit,"Exit the application"))

## --- end client commands

## Client GUI functions

count=0
cmdline=""
inspoint=0
pagepoint=0

def changeSize(stdscr):
	global width,height
	size = stdscr.getmaxyx()
	width=size[1]
	height=size[0]

def redraw(stdscr):
	global textpad
	global roster
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
	# draw roster
	for i in range(len(roster)):
		buddy=roster[i]
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
			loadhostname()
			TORclientFunctionality=1
		time.sleep(0.2)


# Client connection thread
def clientConnectionThread(stdscr,ServerOnionURL,msgs):
	global TORclientFunctionality
	global roster
	while(TORclientFunctionality==0):
		time.sleep(1)
	log("clientConnection: TOR looks alive")		
	while(True):
		try: 
			log("Trying to connect to %s:%d" % (ServerOnionURL,hidden_service_port))
			## Connects to TOR via Socks
			s=socks.socksocket(socket.AF_INET,socket.SOCK_STREAM)
			s.setproxy(socks.PROXY_TYPE_SOCKS5,tor_server,tor_server_socks_port)
			s.settimeout(100)
			s.connect((ServerOnionURL,hidden_service_port))
			s.setblocking(0)
			log("clientConnection: Connected to %s" % ServerOnionURL)
			log("clientConnection: Autorequesting roster...")
			msgs.append("/roster")
			randomwait=random.randint(1,clientRandomWait)
		except:
			log("clientConnection: Can't connect! retrying...")
			time.sleep(1)
			while(TORclientFunctionality==0):
				time.sleep(1)
			continue
		try:
			while(True):
				time.sleep(1)
				ready = select.select([s], [], [], 1.0)
				# received data from server
				if ready[0]:
					data=sanitize(s.recv(minimum_message_len))
					# received pong (ignore)
					if data.find("/PING ")>-1:
						continue 
					# received roster list
					if data.startswith("--roster"):
						roster=[]
						for i in data.split(' ')[1:]:
							roster.append(i)
					# Write received data to channel
					log(data)
				# We need to send a message
				if len(msgs)>0:  
					randomwait-=1 # Wait some random time to add noise
					if randomwait==0:
						m = addpadding(msgs.pop(0))
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


## Client main procedure
def clientMain(stdscr,ServerOnionURL):
	global cmdline
	global inspoint
	global pagepoint
	global width,height
	changeSize(stdscr)
	redraw(stdscr)
	
	global TORclientFunctionality
	global hostname
	
	# Starts TOR if not active
	if detectTOR():
		loadhostname()
		TORclientFunctionality=1
	else:
		initTor()
		while(TORclientFunctionality==0):
			time.sleep(1)

	## Message queue to send to server
	msgs=[]
	t = Thread(target=clientConnectionThread, args=(stdscr,ServerOnionURL,msgs))
	t.daemon = True
	t.start()

	# Main Loop
	while True:
		input=stdscr.getch()

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
			if len(cmdline)<(width-5):
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
  parser.add_option("-s", "--server", action="store", type="string",dest="channel_name", help="Acts as server")
  	# no arguments->bail
  if len(sys.argv)==1:
  	parser.print_help()
	exit(0)
  (options, args) = parser.parse_args()
  if options.channel_name:
  	s=Server()
	s.serverMain(options.channel_name)
  else:
  	if len(options.connect)>0:
	   	Client(options.connect)
	else: parser.print_help()
