#!/usr/bin/env python3

import base64
import hashlib
import hmac
import json
import time
from collections import OrderedDict
from pprint import pprint

import requests

from config import apikey_public
from config import apikey_secret
from config import domain

# Define Global Vars to use
uri = "/order/trade/history"
url = domain + uri
api_secret_key = apikey_secret.encode("utf-8")
std_secret_key = base64.standard_b64decode(api_secret_key)
pub_key = apikey_public.encode("utf-8")
body = OrderedDict([("currency", "AUD"),
                    ("instrument", "ETH"),
                    ("limit", 3),
                    ("since", 0)])

def build_headers(path, api_pub_key, secret_key):
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

    # Build and sign to construct body
    sbody = path + "\n" + str_ctstamp + "\n" + json.dumps(body, separators=(',', ':'))
    print(repr(sbody))

    # dictionary string
    rbody = sbody.encode("utf-8")
    rsig = hmac.new(secret_key, rbody, hashlib.sha512)
    bsig = base64.standard_b64encode(rsig.digest()).decode("utf-8")

    print(api_pub_key)
    # Construct header list of key value pairs
    headers_list = OrderedDict([("Accept", "application/json"),
                                ("Accept-Charset", "UTF-8"),
                                ("Content-Type", "application/json"),
                                ("apikey", api_pub_key),
                                ("timestamp", str_ctstamp),
                                ("signature", bsig)])

    # http://docs.python-requests.org/en/master/user/advanced/#header-ordering
    # maybe returning the ordered list to requests may provide headers with ordering
    return headers_list


def order_history():
    """ Build the request body by invoking header function with config
    params specified as global variables at top and formatting in json the body as well
    returns a response object from requests
    """
    res = build_headers(uri, pub_key, std_secret_key)
    r = requests.post(url, headers=res, json=body)
    return r


def print_history():
    """
    prints the order history, json loads converts to a dictionary, json dumps converts to text
    """
    response = order_history()
    # print(json.dumps(response.json(), indent=2))
    pprint(json.loads(response.text), indent=1, compact=False)


def main():
    """
    TODO: Add in functionality to pass options for the CLI.
    """
    print_history()


if __name__ == "__main__":
    main()
