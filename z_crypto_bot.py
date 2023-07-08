# -*- coding: utf-8 -*-
"""
Created on Thu Apr 29 21:06:57 2021
@author: rafiq
"""

import hmac
import hashlib
import json
import time
import datetime
import requests

order_threshold = 25
key = None  # Secret Key
secret = None  # Secret Key
# python3
secret_bytes = bytes(secret, encoding='utf-8')

time_sleep = 20


def print_log(log: str):
    now = datetime.datetime.now()
    with open("bot.log", "a") as text_file:
        text_file.write(f"{str(now.strftime('%Y-%m-%d %H:%M:%S'))} :: {log}\n")


def cancel_order(order_id: str) -> bool:
    print_log(f'Entered cancel_order for {order_id}')
    try:
        # Generating a timestamp.
        timeStamp = int(round(time.time() * 1000))

        body = {
            "id": order_id,  # Enter your Order ID here.
            "timestamp": timeStamp
        }

        json_body = json.dumps(body, separators=(',', ':'))

        signature = hmac.new(secret_bytes, json_body.encode(), hashlib.sha256).hexdigest()

        url = "https://api.coindcx.com/exchange/v1/orders/cancel"

        headers = {
            'Content-Type': 'application/json',
            'X-AUTH-APIKEY': key,
            'X-AUTH-SIGNATURE': signature
        }

        response = requests.post(url, data=json_body, headers=headers)
        print_log(f'cancel_order : {order_id} , Response -> {response}')
        if response.status_code == 200:
            return True
        return False
    except Exception as e:
        print_log(f'Exception cancel_order -> {e}')
        return False


def is_order_filled(buy_or_sell: str, order_id: str, do_retry: bool) -> bool:
    try:
        # Generating a timestamp.
        timeStamp = int(round(time.time() * 1000))
        buy_retry_threshold = 15  # 5 minutes wait if time_sleep is 10
        sell_retry_threshold = 180  # 25 minutes wait if time_sleep is 10
        count = 0
        body = {
            "id": order_id,  # Enter your Order ID here.
            "timestamp": timeStamp
        }

        json_body = json.dumps(body, separators=(',', ':'))

        signature = hmac.new(secret_bytes, json_body.encode(), hashlib.sha256).hexdigest()

        url = "https://api.coindcx.com/exchange/v1/orders/status"

        headers = {
            'Content-Type': 'application/json',
            'X-AUTH-APIKEY': key,
            'X-AUTH-SIGNATURE': signature
        }

        while True:
            time.sleep(time_sleep)
            response = requests.post(url, data=json_body, headers=headers)
            status = response.json()['status']
            print_log(f'{buy_or_sell} order status is {status} for order {order_id}')
            if status == 'filled':
                return True
            elif status == 'partially_filled':
                continue
            elif status == 'open' and do_retry:
                count = count + 1
            elif status == 'open' and not do_retry:
                continue
            else:
                return False  # something went wrong, maybe order got cancelled manually?
            if buy_or_sell == 'buy' and count > buy_retry_threshold and do_retry:
                print_log('Retry threshold reached for Buy order, Cancel and try again')
                return False  # Cancel existing order and buying again
            elif buy_or_sell == 'sell' and count > sell_retry_threshold and do_retry:
                print_log('Retry threshold reached for Sell order, Cancel and try again')
                return False  # Cancel existing order and selling again
            else:
                pass
    except Exception as e:
        print_log(str(e))
        return False


def create_order(buy_or_sell: str, price: float, quantity: int) -> str:
    print_log(f'In create_order for {buy_or_sell} at {price} for quantity {quantity}')
    timeStamp = int(round(time.time() * 1000))
    body = {
        "side": buy_or_sell,  # Toggle between 'buy' or 'sell'.
        "order_type": "limit_order",  # Toggle between a 'market_order' or 'limit_order'.
        "market": "ADAINR",  # Replace 'SNTBTC' with your desired market pair.
        "price_per_unit": price,  # This parameter is only required for a 'limit_order'
        "total_quantity": quantity,  # Replace this with the quantity you want
        "timestamp": timeStamp
    }

    json_body = json.dumps(body, separators=(',', ':'))

    signature = hmac.new(secret_bytes, json_body.encode(), hashlib.sha256).hexdigest()

    url = "https://api.coindcx.com/exchange/v1/orders/create"

    headers = {
        'Content-Type': 'application/json',
        'X-AUTH-APIKEY': key,
        'X-AUTH-SIGNATURE': signature
    }

    response = requests.post(url, data=json_body, headers=headers)
    data = response.json()
    print_log(data)
    order_id = data['orders'][0]['id']
    print_log(f"create_order returned order id {order_id}")
    return str(order_id)


def get_buy_price(bids_order_book: dict, low: float, last_price: float, my_quantity: int) -> float:
    bid_list = []
    try:
        for bp, quantity in bids_order_book.items():
            bid_price = float(bp)
            if float(quantity) > my_quantity and bid_price >= low and bid_price < last_price:
                print_log(f'Order Books Bids {bid_price} {quantity}')
                bid_list.append(bid_price)
        if bid_list:
            return sum(bid_list) / len(bid_list)
        return -1
    except Exception as e:
        print_log(f'Exception in get_buy_price {str(e)}')
        return 0


def get_sell_price(asks_order_book: dict, high: float, last_price: float) -> float:
    ask_list = []
    try:
        for ap, quantity in asks_order_book.items():
            ask_price = float(ap)
            if ask_price > last_price and ask_price <= high:
                print_log(f'Order Books Asks {ask_price} {quantity}')
                ask_list.append(ask_price)
        if ask_list:
            return sum(ask_list) / len(ask_list)
        return -1
    except Exception as e:
        print_log(f'Exception in get_sell_price {str(e)}')
        return 0


def profitable(profit: float, buy_price: float, sell_price: float) -> bool:
    if profit < 0 or not buy_price or not sell_price:
        print_log(f'Stop Loss, profit = {profit}, buy_price = {buy_price}, sell_price = {sell_price}')
        return False
    return True


def keep_getting_market_data_forever():
    status = True
    while True:
        time.sleep(time_sleep)
        if not status:
            print_log('keep_getting_market_data_forever had terminal error, stop app')
            break
        res = requests.get("https://api.coindcx.com/exchange/ticker")
        print_log("****************************************************")
        for market_data in res.json():
            # Currently only scan for Cardano INR Market
            if market_data['market'] == "ADAINR":
                last_price = float(market_data['last_price'])
                # The below strategy took time for buy order to be executed -> rising market
                # buy_price = round(last_price - (last_price * 0.01),2)
                order_book_url = "https://public.coindcx.com/market_data/orderbook?pair=B-ADA_INR"
                response = requests.get(order_book_url)
                quantity = 30
                low = last_price - last_price * 0.02
                high = last_price + last_price * 0.02
                print_log(f'Last Price = {last_price} High Price = {high} and Low price = {low}')
                # buy_price = round(last_price,2)
                # sell_price = round(buy_price * 1.02,2)
                bids_dict = response.json()['bids']
                asks_dict = response.json()['asks']
                buy_price = round(get_buy_price(bids_dict, low, last_price, quantity), 2)
                sell_price = round(get_sell_price(asks_dict, high, last_price), 2)
                if buy_price == -1 or sell_price == -1:
                    break  # Rethink think this buggy code
                unit_commission = buy_price * 0.001 + sell_price * 0.001
                unit_profit = sell_price - buy_price - unit_commission
                profit = unit_profit * quantity
                if not profitable(profit, buy_price, sell_price):
                    status = False
                    break
                print_log(f'Creating order calculated profit {profit}, buy_price = {buy_price} and sell_price = {sell_price}')
                order_id = create_order("buy", buy_price, quantity)
                if is_order_filled("buy", order_id, True):
                    print_log(f"Buy Order {order_id} is filled for price {buy_price}")
                    order_id = create_order("sell", sell_price, quantity)
                    if is_order_filled("sell", order_id, True):
                        print_log(f"Sell Order {order_id} is filled for price {sell_price}")
                        print_log(f'Realised profit = {profit}')
                    else:
                        print_log("Sell order failed, Try selling at no profit no loss")
                        if not cancel_order(order_id):
                            print_log(f'Sell order failed for {order_id} and could not cancel order as well')
                            status = False
                            break
                        sell_price = round(buy_price * 1.003, 2)
                        unit_commission = buy_price * 0.001 + sell_price * 0.001
                        unit_profit = sell_price - buy_price - unit_commission
                        profit = unit_profit * quantity
                        print_log(f'Creating order RE-calculated profit {profit}, buy_price = {buy_price} and sell_price = {sell_price}')
                        if not profitable(profit, buy_price, sell_price):
                            status = False
                            break
                        order_id = create_order("sell", sell_price, quantity)
                        if is_order_filled("sell", order_id, False):
                            print_log(f"Sell Order {order_id} is filled for price {sell_price}")
                            print_log(f'Realised profit = {profit}')
                        else:
                            print_log('Re-sell also failed as no profit, no-loss. Please stop process')
                            status = False
                           break

def main():
    print_log("**********************Starting z-crypto-bot***********************")
    keep_getting_market_data_forever()


if __name__ == "__main__":
    main()
