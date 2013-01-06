Torirc
======

Anonymous IRC-like multiuser chat using TOR hidden services, with emphasis in network-analysis protection.

This is a simple client/server chat using TOR hidden services, implemented in a single python file. License is GNU-GPL

Usage
-----
	torirc.py [options]

	Options:
	  -h, --help            show this help message and exit
	  -c CONNECT, --connect=CONNECT
	                        Acts as client, connect to server
	  -s, --server          Acts as server

Example use:
------------

In the Server:
	~$ ./torirc.py --server=#TESTSRV
	(Main Server Thread) Trying to connect to existing tor...
	(Main Server Thread) Tor looks active, listening on k52whdwcd2zxjtcq.onion


In the Client:

	~$./torirc.py  -c k52whdwcd2zxjtcq.onion
	clientConnection: TOR looks alive
	Trying to connect to k52whdwcd2zxjtcq.onion:11009
	clientConnection: Connected to k52whdwcd2zxjtcq.onion


You will be assigned a randomly generated nick. You need to set your nick with '/nick' and you are good to go. If you want multiple chatrooms, start multiple servers, each one will auto-generate their own hidden-service url.

Objectives
----------

Anonymous/Encrypted chat resistant to:
		+  Network analysis techniques
		+  Exploits
		+  Crypto attacks
		+ Trust minimization

To reach those objectives the design of torirc follows:
	+  Simplicity: Small means less bugs and easier to audit
	+  Interpreted language: Avoid most memory corruption bugs
	+  Minimize library use: Again, less code susceptible to bugs
	+  Entropy maximization: When possible, random delays and useless data is transmitted.


Discussion of choices
---------------------

 *  Python: I choosed python because it's what I know, and the interpreter is relatively small. Second choice would have been Java, but the JRE is too big and cumbersome. Also Python usually comes installed in most Linux distros.

 *  TOR: TOR is a big ugly chunk of C code that I do not trust, but at this time is the only software that provides the functionality that I need, that is, hidden services and onion routing. Also, the current version of torirc doesn't have his own cryptography routines and uses TOR for it, but this may change in the future.

Alternatives
------------

Here are alternative software and why I do not like it:

 *  IRC over tor:
	This is the best alternative, but only if you don't use any public server. Anyway this is vulnerable to exploits as IRC servers and clients tend to be huge pieces of C code. Also Network analysis is trivial with this protocol.

 *  MSN/Gtalk/Pidgin: Horrible choices, huge codebases, hundreds of libraries riddled with bugs, vulnerable to exploits, central server sees all your (often plaintext) messages, etc. Some plugins like OTR fix some shortcomings, but network analysis is also trivial.

 *  Silc: They wrote their own crypto, that's a big mistake. Also, it's written in C. I do believe they also don't protect against network analysis.

 *  torchat: Nice alternative but only P2P, latest versions started to creep with unsafe functionality like emoticons, etc.

Network analysis protections
----------------------------

This still is experimental software so no strong network-analysis-proof must be assumed. At this moment:

 * Thanks to TOR, nobody, the server or the clients, known the IP address of nobody else.
 * However, the server knows when a client is connected.
 * The client periodically sends random data at random intervals.
 * The server doesn't accurately report the number of clients in the chatroom, it only erases a nick approximately a day after it disconnects (this delay is also random)

Network analysis is a hard problem and there are hundreds of side-channels that can be used to determine if a user is connected or not. This information can be the difference between life and death for some people, so it's a useful problem to tackle IMHO.
