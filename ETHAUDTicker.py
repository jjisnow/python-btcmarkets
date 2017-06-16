#!/usr/bin/env python3

import time

import requests

from config import domain

uri = "/market/ETH/AUD/tick"
url = domain + uri

r = requests.get(url, verify=True)

print("BTC Markets most recent ETH trade data:")
while True:
    ask = str(r.json()["bestAsk"])
    bid = str(r.json()["bestBid"])
    last = str(r.json()["lastPrice"])
    tstamp = r.json()["timestamp"]
    ltime = time.ctime(tstamp)
    utime = time.asctime(time.gmtime(tstamp))

    p = """
        Best bid price (sell at): Best ask price (buy at) : Last trade price
        {0} AUD                 : {1} AUD                 : {2} AUD

        Accurate at:
        {3} (local time)
        {4} UTC

        Source:  {5}

        """.format(bid, ask, last, ltime, utime, r.url)

    print(p)
