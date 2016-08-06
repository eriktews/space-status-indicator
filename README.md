# space-status-indicator
Status indicator for Hackerspaces

# Purpose

A hacker- or makerspace is in general a physical place where people hang around to work on interesting and creative projects or just to socialize. Often members of such spaces would like to know how many other members are currently at the space to know whether they are would meet anyone else when they would go there. 

The purpose of this project is a status indicator for hackerspaces or makerspaces websites. Every space can run it on a device in the local network such as a Raspberry Pi. The software counts the number of active hosts in the network which are not permanently online (such as routers, servers...). When every member brings a device that connects to the local network, such as a smartphone via WiFi or a laptop computer with an ethernet jack, this is equal to the number of members who are currently in the space. The number is then shown on the local webserver, which can be made accessable to the outside world using port redirects or similar methods. It can also be embedded into the main website using an iFrame tag.

# Implementation

The implementation consists of several components.

## Main daemon

The main component of the status indicator is a daeon written in python using the gevent framework.

It launches tcpdump to monitor the network for broadcast or multicast frames. For all those frames, the MAC address of the sending device is extracted and saved.

When a MAC address is online for more than 80% of a 24 hour day, it's assumed that this MAC address is permanently online and it is saved in an SQLite database. All other MAC addresses (probably belonging to members of the space) are only kept in RAM and never saved to permanent storage which makes this implementation rather privacy friendly.

The number of MAC addresses active is then exported using two ways:

### Space API

It is exported using the space-API (http://spaceapi.net/) at the "/api/status" path. A template for all the other informations about the location and similar properties of the space can be configured and the status indicator just updates the online true/false property.

### socket.io

The number is also exported using the socket.io protocol. The protocol allows push-notifications about new clients arriving at the space and clients for the protocol can be implemented in many languages. JavaScript is probably the most popular language for implementing socket.io clients.


## Website

The second component is a website (just static HTML) which comes with a client for the socket.io protocol based on jquery and socket.io. I can be customized to any needs and might also be served from a different host or port. It is also suiteable for embedding the website into another website using an iFrame tag.

# Setup

Copy the main daemon 'macs.py' to for example */usr/local/sbin/*

Check that your system provides all the dependencies for the daemon, which is for python *gevent*, *geventwebsocket* and *socketio*. Currently, Debian jessie does not provide a package for *socketio*, so you need to install it with pip.

Create the directory */var/lib/space-status-indicator/*. Alternatively you can specify different paths on the command line for *macs.py*.

Copy the file *hackerspace.json* to */var/lib/space-status-indicator/* and **edit** it to reflect your space.

Copy the *static-html* content to for example */var/www/html/* or where your webserver looks for static ressources.

You can now start editing */var/www/html/index.html*, there are some strings in there realted to fizzPOP, the Birmingham maker space.

Copy the service file for systemd to */etc/systemd/system/* should you be using systemd. Alternatively you might start the daemon with any other kind of init system. Then enable the service with the command *systemctl  daemon-reload; systemctl enable space-status-indicator* 

Add a suiteable virtual host for Apache2. I recommend using lets-encrypt to serv the website using HTTPS. In that virtual host configuration add a reverse proxy configuration like this:

```
RewriteEngine On
RewriteCond %{REQUEST_URI}  ^/socket.io            [NC]
RewriteCond %{QUERY_STRING} transport=websocket    [NC]
RewriteRule /(.*)           ws://localhost:8080/$1 [P,L]

ProxyPass "/socket.io" "http://localhost:8080/socket.io"
ProxyPassReverse "/socket.io" "http://localhost:8080/socket.io"
ProxyPass "/api" "http://localhost:8080/api"
ProxyPassReverse "/api" "http://localhost:8080/api"
```

To make it work, you need to enable the modules *proxy*, *proxy_http*, *proxy_wstunnel* and *rewrite*.

# Running it

In genral, it is expected to work fine, but you might need to update the lets enrypt certificate from time to time. That's not a restriction of the software itself.
