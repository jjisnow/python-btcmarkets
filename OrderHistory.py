#!/usr/bin/env python3

import base64
import hashlib
import hmac
import json
import time
from collections import OrderedDict

import requests

from config import apikey_public
from config import apikey_secret
from config import domain

# Define Global Vars
uri = "/order/trade/history"
url = domain + uri
api_secret_key = apikey_secret.encode("utf-8")
# pub_key = apikey_public.encode("utf-8")
pub_key = apikey_public
std_secret_key = base64.standard_b64decode(api_secret_key)


def build_headers(URL, PUBKEY, PRIVKEY):
    """Build timestamp, format and encode everything,  and construct string to 
    sign with api key. Use HmacSHA512 algorithm in order to sign.
    
    Lastly build the headers to send... In order to ensure the correct order 
    of key value pairs in the JSON payload, build an ordered dictionary out
    of a list of tuples.
    """

    # Build timestamp
    tstamp = time.time()
    ctstamp = int(tstamp * 1000)  # or int(tstamp * 1000) or round(tstamp * 1000)
    str_ctstamp = str(ctstamp)

    # Build Request component
    body = OrderedDict([("currency", "AUD"), ("instrument", "ETH"), ("limit", 10), ("since", 429357237)])

    # Build and sign to construct body
    sbody = uri + "\n" + str_ctstamp + "\n" + json.dumps(body) + "\n"

    # # Fudge an ordered dictionary string
    # for _ in range(len(body)):
    #     s = body.popitem(last=False)
    #     sbody += '\"' + str(s[0]) + '\":'
    #     if type(s[1]) == type(''):
    #         sbody += '\"' + str(s[1]) + '\"'
    #     else:
    #         sbody += str(s[1])
    #     sbody += ","
    # sbody = sbody[:-1] + '}'
    print(repr(sbody))

    # dictionary string
    rbody = sbody.encode("utf-8")
    rsig = hmac.new(std_secret_key, rbody, hashlib.sha512)
    bsig = base64.standard_b64encode(rsig.digest()).decode("utf-8")

    print(pub_key)
    # Construct header list of key value pairs
    headers_list = OrderedDict([("Accept", "application/json"),
                                ("Accept-Charset", "UTF-8"),
                                ("Content-Type", "application/json"),
                                ("apikey", pub_key),
                                ("timestamp", str_ctstamp),
                                ("signature", bsig)])

    # Load list into dictionary
    # headers = dict(headers_list)

    # http://docs.python-requests.org/en/master/user/advanced/#header-ordering
    # maybe returning the ordered list to requests may provide headers with ordering
    return headers_list


def main():
    """ Build the request body by invoking header function with config
    params specified as global variables at top
    
    TODO: Add in functionality to pass options for the CLI.
    """
    res = build_headers(url, pub_key, std_secret_key)
    print(res)
    r = requests.post(url, data=res)

    # try:
    print(r)
    print(r.text)
    print(r.headers)


if __name__ == "__main__":
    main()
