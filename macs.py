#!/usr/bin/env python

from gevent import monkey; monkey.patch_all()
from geventwebsocket.handler import WebSocketHandler
import gevent
import argparse
import re
import datetime
import time
import logging
from gevent import subprocess
from gevent import Greenlet

import socketio
import sqlite3

import json

class storage:
	def __init__(self, server, file):
		self.iLen = 180
		self.intervals = (24*60*60)//self.iLen
		self.alwaysOn = set()
		self.seen = set()
		self.intervalData = []
		self.current = None
		self.clients = 0
		self.server = server
		self.conn = sqlite3.connect(file)
		self.conn.isolation_level = None
		self.cur = self.conn.cursor()
		self.init_db()
		server.on('connect', namespace='/online', handler=self.connect)

	def connect(self, sid, environ):
		self.server.emit("log", room=sid, data=self.clients, namespace="/online")


	def init_db(self):
		try:
			self.cur.execute("CREATE TABLE alwaysOn (mac text primary key)")
		except:
			pass
		self.cur.execute("SELECT mac from alwaysOn")
		for i in self.cur.fetchall():
			self.alwaysOn.add(i[0])
		

	def clearLast(self):
		if len(self.intervalData) > self.intervals:
			self.intervalData.pop(0)

	def addCurrentToLast(self):
		self.intervalData.append([self.current, self.seen])

	def addNewSet(self, targetInterval):
		logging.info("current number online " + str(self.clients))
		self.updateAlwaysOn()
		while (targetInterval > self.current):
			self.clearLast()
			self.addCurrentToLast()
			self.current = self.current + 1
			self.seen = set()


	def addMac(self, x):
		[time, mac] = x
		targetInterval = time // self.iLen
		if (self.current == None):
			self.current = targetInterval
		if targetInterval > self.current:
			self.addNewSet(targetInterval)
		if not mac in self.seen:
			logging.debug("adding mac " + mac + " to set " + str(self.current))
			self.seen.add(mac)
			self.countClients()

	def countClients(self):
		allMacs = self.seen
		if len(self.intervalData) > 0:
			allMacs = allMacs | self.intervalData[-1][1]
		clients = allMacs - self.alwaysOn
		numClients = len(clients)
		if numClients != self.clients:
			self.updateClients(numClients)
		self.clients = numClients

	def updateAlwaysOn(self):
		if len(self.intervalData) < self.intervals:
			return
		s = self.stats()
		for i in s:
			if (s[i] > 80) and (i not in self.alwaysOn):
				self.alwaysOn.add(i)
				self.cur.execute("INSERT INTO alwaysOn(mac) values (?)", (i,))
		

	def stats(self):
		s = {}
		for i in self.intervalData:
			[d, macs] = i
			for m in macs:
				if m in s:
					s[m] = s[m]+1
				else:
					s[m] = 1
		for i in s:
			s[i] = (s[i]*100)//len(self.intervalData)
		return s

	def printStats(self):
		s = self.stats()
		for i in s:
			print(str(i) + " " + str(s[i]) + "%")

	def updateClients(self, c):
		self.server.emit("log", data=c, namespace="/online")



class commandProcessor:
	remac = re.compile('^(\d+)\.\d+ ([0-9a-f\:]+) ', re.M)

	def __init__(self, cmd, storage):
		self.cmd = cmd
		self.storage = storage

	def process(self, line):
		result = self.remac.search(line)
		if result:
			return [int(result.group(1)), result.group(2)]
		else:
			return None

	def run(self):
		#args = shlex.split(self.cmd)
		p = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, shell=True, universal_newlines=True)
		for line in p.stdout:
			logging.debug("read line " + line)
			[time, mac] = self.process(line)
			if mac: 
				logging.debug(mac)
				self.storage.addMac([time, mac])
		p.poll()


class spaceAPI:
	def __init__(self, template, s):
		self.template = template
		self.s = s

	def application(self, environ, start_response):
		path = environ.get('PATH_INFO', '').lstrip('/')
		if path == 'api/status':
			f = open(self.template)
			j = json.load(f)
			f.close()
			if (self.s.clients == 0):
				online = False
			else:
				online = True
			j['state']['open'] = online
			start_response('200 OK', [('Content-Type', 'application/json'), ('Access-Control-Allow-Origin', '*'), ('Cache-Control', 'no-cache')])
			return [json.dumps(j).encode("utf-8")]
		else:
			start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
			return ['Not Found']

			
		

def main(args):
	sio = socketio.Server(async_mode='gevent')
	from gevent import pywsgi
	s = storage(sio, args.database)
	sAPI = spaceAPI(args.apifile, s)
	app = socketio.Middleware(sio, sAPI.application)
	server = pywsgi.WSGIServer(('', 8080), app, handler_class=WebSocketHandler)

	cP = commandProcessor(args.cmd, s)
	g = Greenlet(cP.run)
	g.start()
	server.start()
	
	logging.info("server started")
	g.join()
	#s.printStats()

if __name__ == "__main__":
	# execute only if run as a script
	#logging.basicConfig(level=logging.INFO)
	logging.basicConfig(level=logging.WARNING)
	parser = argparse.ArgumentParser(description="Monitor the status of a hackerspace")
	parser.add_argument("--database", help="File used to store the MACs that are almost permanently online", default="/var/lib/space-status-indicator/alwaysOn.db")
	parser.add_argument("--cmd", help="The command that is executed to monitor the traffic on the netwrok", default="tcpdump -tt -e -n -i eth0 broadcast or multicast")
	parser.add_argument("--apifile", help="The JSON file that is used as a template for the hackerspace API", default="/var/lib/space-status-indicator/hackerspace.json")
	args = parser.parse_args()
	
	main(args)
