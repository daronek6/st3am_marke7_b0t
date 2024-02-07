from steam.client import SteamClient
from steam.webauth import WebAuth
from csgo.client import CSGOClient
from json import load, dump
import urllib.parse
import struct
import requests
import re
from queue import Queue 
import threading
import time
from datetime import datetime
import random


def encodeURI(text):
    return urllib.parse.quote(text)

def getLinksAndIds(res_json):
    list = []
    listingid = ''
    assetid = ''
    tempLink = ''
    listinginfo = res_json['listinginfo']
    ids = []
    for elm in listinginfo:
        ids.append(elm)
    
    for id in ids:
        listingid = listinginfo[id]['listingid']
        assetid = listinginfo[id]['asset']['id']
        tempLink = listinginfo[id]['asset']['market_actions'][0]['link']

        tempLink = tempLink.replace("%20M%listingid", f"M{listingid}")
        tempLink = tempLink.replace("%A%assetid%", f"A{assetid}")

        list.append({'listingid': listingid, 'link': tempLink})

    return list     

def getPrices(res_json):
    prices = []
    listinginfo = res_json['listinginfo']
    ids = []
    total = 0
    subtotal = 0
    fee = 0
    for elm in listinginfo:
        ids.append(elm)
    for id in ids:
        if listinginfo[id]['price'] != 0:
            subtotal = listinginfo[id]['converted_price']
            fee = listinginfo[id]['converted_fee']
            total = subtotal +  fee
            prices.append({'total':total, 'subtotal':subtotal, 'fee':fee})
        else:
            print("one of the items had price 0")
            prices = getPricesHtml(res_json)
            break

    return prices

def getPricesHtml(res_json):
    prices = []
    html = res_json['results_html']
    re_list = re.findall(f"([0-9]+,[0-9]+{cur_text})", html)
    total = 0
    subtotal = 0
    fee = 0
    i = 0
    tmpStr = ''
    for elm in re_list:
        tmpStr = elm.replace(cur_text, '')
        tmpStr = tmpStr.replace(',', '.')

        if i == 0:
            total = int(float(tmpStr) * 100)
        elif i == 2:
            subtotal = int(float(tmpStr) * 100)
            fee = total - subtotal
            i = -1

            prices.append({'total':total, 'subtotal':subtotal, 'fee':fee})
        i += 1
    
    return prices

def getItemListings(market_hash_name, start, count):
    url = f"http://steamcommunity.com/market/listings/730/{encodeURI(market_hash_name)}/render/?query=&start={start}&count={count}&country={country}&language={lang}&currency={cur}"
    headers = {
        'Accept': 'text/javascript, text/html, application/xml, text/xml, */*',
        'Accept-Encoding': 'gzip, deflate, br'
    }
    res = requests.get(url=url, headers=headers) 
    body = res.json()
    items = []
    new_items = []
    if body == None:
        print('Probably too many requests :(')
        raise Exception('too many requests')
    elif body['success'] == True:
        prices = getPrices(body)
        links = getLinksAndIds(body)

        for i in range(0, len(prices)):
            prices[i]['listingid'] = links[i]['listingid']
            prices[i]['link'] = links[i]['link']
        items = prices

        for item in items:
            if item['listingid'] not in checked_ids:
                new_items.append(item)
    else:
        print('Empty json')
    
    return new_items

def inspectItem(link = '', m = 0, a = 0, d = 0):
    v_m = 0
    v_a = 0
    v_d = 0
    start_m = 0
    end_m = 0
    start_a = 0
    end_a = 0
    start_d = 0
    if len(link) > 0:
        start_m = link.find('M')
        start_a = link.find('A')
        start_d = link.find('D')

        end_m = start_a
        end_a = start_d

        v_m = int(link[start_m+1:end_m])
        v_a = int(link[start_a+1:end_a])
        v_d = int(link[start_d+1:])

    else:
        v_m = m
        v_a = a
        v_d = d
    
    csgo.request_preview_data_block(s = 0, a = v_a, d = v_d, m = v_m)

def getfloat(paintwear):
    buf = struct.pack('i', paintwear)
    skinFloat = struct.unpack('f', buf)[0]
    return skinFloat

def testItems(items, maxTotal, maxFloat):
    print(f"{len(items)} new item!")
    for item in items:
        checked_ids.append(item['listingid'])
        if testPrice(item, maxTotal) == 1:
            print(f"item {item['listingid']} ready to chceck float")
            if testFloat(item, maxFloat) == 1:
                print(f"item {item['listingid']} ready to buy")
                itemsToBuyQueue.put(item)
        else:
            print(f"item {item['listingid']} too expensive. MaxTotal: {maxTotal}, item total: {item['total']}")

def testPrice(item, maxTotal):
    if(item['total'] <= maxTotal):
        return 1
    else:
        return 0

def testFloat(item, maxFloat):
    global currentItemFloat
    max_retries = int(3.0/0.2)
    retries = 0
    currentItemFloat = 1.0
    lock.acquire()
    inspectItem(link=item['link'])
    while(lock.locked()):
        time.sleep(0.2)
        retries += 1
        if retries >= max_retries:
            lock.release()
    print(f"{threading.current_thread().name} {currentItemFloat}")
    if currentItemFloat <= maxFloat:
        return 1
    else:
        return 0

def bot(market_hash_names, start, count, maxTotals, maxFloat, itemsToBuy):
    i = 0
    while lock.locked():
        time.sleep(0.1)
    print('Bots ready')
    while (itemsToBuy > 0):

        market_hash_name = market_hash_names[i]
        maxTotal = maxTotals[i]
        print(f"item: {market_hash_name}, maxTotal: {maxTotal}")
        try:
            items = getItemListings(market_hash_name, start, count)
        except Exception as ex:
            print(ex)
            return 0
        testItems(items, maxTotal, maxFloat)
        itemsToBuy = tryToBuyItems(itemsToBuy, market_hash_name)
        if i == (len(market_hash_names) - 1):
            i = 0
        else:
            i += 1
        bot_timeout = BOT_MIN_TIMEOUT + random.random() * (BOT_MAX_TIMEOUT - BOT_MIN_TIMEOUT)
        if itemsToBuy > 0:
            print(f"{threading.current_thread().name} TIMEOUT")
            time.sleep(bot_timeout)
    print("Bot stopped!")
    return 1

def tryToBuyItems(itemsToBuy, market_hash_name):
    attempts = itemsToBuyQueue.qsize()
    print(f"Q size: {attempts}")
    while (itemsToBuyQueue.empty() == False) and (attempts > 0) and (itemsToBuy > 0):
        item = itemsToBuyQueue.get()
        res = tryToBuyItem(item, market_hash_name)
        if res == 1:
            print(f"Bought: {market_hash_name}: {item}")
            with open('buy_history.txt', 'a+') as file:
                file.write(f" {market_hash_name};{item['total']};{datetime.now()}\n")
            
            itemsToBuy -= 1
            setup_data['itemstobuy'] = itemsToBuy
            with open('setup.json', 'w') as file:
                dump(setup_data, file)
        elif res == -1:
            print('item already bought')
        elif res == -2:
            print('No balance left')
            itemsToBuy = 0
        else:
            print(f"Error while buying item: {item}")
            itemsToBuyQueue.put(item)
        attempts -= 1
    return itemsToBuy

def tryToBuyItem(item, market_hash_name):
    res = buyItem(item, market_hash_name)
    time.sleep(0.1)
    return res

def buyItem(item, market_hash_name):
    webSession = buyBotClient.session

    url = f"https://steamcommunity.com/market/buylisting/{item['listingid']}"
    headers = {
        'Referer':f"https://steamcommunity.com/market/listings/730/{encodeURI(market_hash_name)}",
        'Origin': 'https://steamcommunity.com',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
    }
    body = {
        'sessionid': buyBotClient.sessionID,
        'currency': 6,
        'subtotal': item['subtotal'],
        'fee': item['fee'],
        'total': item['total'],
        'quantity': 1,
        'billing_state': '',
        'save_my_address': '0'
    }

    if webSession != None:
        try:
            res = webSession.post(url=url, headers=headers, data=body)
        except:
            print('connection error, buybot relogin')
            relogBuyBot(username=setup_data['buybot']['username'], password=setup_data['buybot']['password'])
            webSession = buyBotClient.session
            print(f"retrying to buy: {item}")
            res = webSession.post(url=url, headers=headers, data=body)
        res_data = res.json()

        try:
            balance_left = int(res_data['wallet_info']['wallet_balance'])
            if balance_left > 0:
                print(f"Balance left: {balance_left} ")
                return 1
            else:
                return -2
        except:
            try:
                res_msg = res_data['message']
                print(res_msg)
                return -1
            except:
                return 0
    else:
        print('Cant get webSession')
        return 0

    
def setupFloatBot(username, password):
    floatBotClient.cli_login(username=username, password=password)
    floatBotClient.run_forever()

def setupBuyBot(username, password):
    buyBotClient.cli_login(username=username, password=password)
    setupFloatBot(username=setup_data['floatbot']['username'], password=setup_data['floatbot']['password']) 

def relogBuyBot(username, password):
    buyBotClient.cli_login(username=username, password=password)


setup_data = ''
with open('setup.json', 'r') as file:
    setup_data = load(file)
market_hash_names = []
totals = []
maxFloat = setup_data['maxfloat']
itemsToBuy = setup_data['itemstobuy']
cur_text = setup_data['cur_text']
country = setup_data['country']
lang = setup_data['lang']
cur = setup_data['cur']
for item in setup_data['items']:
    market_hash_names.append(item['name'])
    totals.append(item['maxtotal'])
BOT_MIN_TIMEOUT = setup_data['mintimeout'] # in sec
BOT_MAX_TIMEOUT = setup_data['maxtimeout'] # in sec

currentItemFloat = 1.0
itemsToBuyQueue = Queue()

floatBotClient = SteamClient()
buyBotClient = WebAuth(username=setup_data['buybot']['username'])
csgo = CSGOClient(floatBotClient)
lock = threading.Lock()
checked_ids = []

                                                    # market_hash_name, start, count, maxTotal, maxFloat, itemsToBuy
bot_t = threading.Thread(name='Bot_t', target=bot, args=(market_hash_names, 0, 10, totals, maxFloat, itemsToBuy))

@floatBotClient.on('logged_on')
def start_csgo():
    print('floatBot logged in')
    csgo.launch()

@csgo.on('ready')
def gc_ready():
    print('csgo ready')
    bot_t.start()
    
@csgo.on('item_data_block')
def item_data(data):

    global currentItemFloat
    currentItemFloat = getfloat(data.paintwear) 
    print(f"{threading.current_thread().name} {currentItemFloat}")
    try:
        lock.release()
    except:
        print('already unlocked')


setupBuyBot(username=setup_data['buybot']['username'], password=setup_data['buybot']['password'])