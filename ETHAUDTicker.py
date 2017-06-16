#!/usr/bin/env python3

import time

import requests

from config import domain

uri = "/market/ETH/AUD/tick"
url = domain + uri
poll_seconds = 5

r = requests.get(url, verify=True)
print("BTC Markets most recent ETH trade data:")
print("{0}\n".format(r.url))
print("bid price   : ask price   : Last trade \n")
while True:
    r = requests.get(url, verify=True)
    ask = str(r.json()["bestAsk"])
    bid = str(r.json()["bestBid"])
    last = str(r.json()["lastPrice"])
    tstamp = r.json()["timestamp"]

    local_time=time.localtime(tstamp)
    local=time.strftime("%Y-%m-%d %H:%M:%S",local_time)
    utc_time=time.gmtime(tstamp)
    utc=time.strftime("%H:%M:%S",utc_time)

    p = "{0} AUD  : {1} AUD  : {2} AUD : {3} local : {4} UTC ".format(bid, ask, last, local, utc )

    print(p)
    time.sleep(poll_seconds)
