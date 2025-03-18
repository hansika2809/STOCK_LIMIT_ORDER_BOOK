from django.shortcuts import render, redirect
from .models import User, Order, Trade, Stoplossorder
from django.db.models import Q
from django.db import transaction
from django.contrib.auth.decorators import login_required
import json
from django.contrib import messages

from .utils import match_order  # Assuming match_order is in utils.py
from django.http import JsonResponse

def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        user, created = User.objects.get_or_create(username=username)
        return redirect('home', user_id=user.id)
    return render(request, 'trading/login.html')
def fetch_best_ask():
    # Fetch the best ask price (lowest available price for a buy order)
    return Order.objects.filter(order_type="SELL", is_matched=False).order_by('price').values('price', 'quantity').first()
def fetch_best_bid():
    # Fetch the best bid price (highest available price for a sell order)
    return Order.objects.filter(order_type="BUY", is_matched=False).order_by('-price').values('price', 'quantity').first()

def get_best_ask(request):
    if request.method == 'GET':
    # Fetch the best ask price (lowest available price for a buy order)
        best_ask = Order.objects.filter(order_type="SELL", is_matched=False).order_by('price').values('price', 'disclosed').first()
        return JsonResponse({'best_ask': best_ask})
    return JsonResponse({'best_ask': None})

def get_best_bid(request):
    if request.method == 'GET':
    # Fetch the best bid price (highest available price for a sell order)
        best_bid = Order.objects.filter(order_type="BUY", is_matched=False).order_by('-price').values('price', 'disclosed').first()
        return JsonResponse({'best_bid': best_bid})
    return JsonResponse({'best_bid': None})

# @login_required  # Ensure the user is logged in before accessing this view
# def home(request):
#     user = request.user  # Get the logged-in user
#     user, created = User.objects.get_or_create(username=user)

#     if request.method == "POST":
#         order_type = request.POST.get('order_type')
#         order_mode = request.POST.get('order_mode')
#         quantity = int(request.POST.get('quantity'))
#         disclosed = int(request.POST.get('disclosed_quantity'))
#         stoploss_order =  request.POST.get('Stoploss_order')
#         target_price = request.POST.get('Target_price')
#         is_ioc=request.POST.get('is_ioc')=='True'

#         price = None
#         end_time=request.POST.get('end_time')

#         if disclosed==0:
#             disclosed=quantity

#         try:
#             if order_mode == "LIMIT":
#                 price = float(request.POST.get('price', 0))  # Default to 0 if no price is provided

#             elif order_mode == "MARKET":
#                 if order_type == "BUY":
#                     # Fetch the JSON response from the best ask view
#                     best_ask_response = fetch_best_ask()
#                     best_ask_data=best_ask_response
#                     price = best_ask_data['price']

#                 elif order_type == "SELL":
#                     # Fetch the JSON response from the best bid view
#                     best_bid_response = fetch_best_bid()
#                     best_bid_data=best_bid_response
#                     price = best_bid_data['price']

#                 if price is None:
#                     return render(request, 'trading/home.html', {'error': 'Unable to fetch market price for the order type.'})
#                     # Create and save the new order

#             if disclosed>quantity:
#                 disclosed=quantity

#             if(stoploss_order=='NO'):
#                     # Save or process the order here
#                 new_order = Order(
#                     order_type=order_type,
#                     order_mode=order_mode,
#                     quantity=quantity,
#                     disclosed=disclosed,
#                     price=price,
#                     is_matched=False,
#                     is_ioc=is_ioc,
#                     user=user  # Ensure the order is associated with the logged-in user
#                 )

#                 if disclosed < 0.1 * quantity:  # disclosed_quantity should not be > 10% of quantity
#                     messages.error(request, "Disclosed Quantity cannot be less than 10% greater than Quantity.")

#                 else:
#                     # Proceed with saving the order or further logic
#                     messages.success(request, "Order placed successfully!")
#                     new_order.save()
#                     print("call1")
#                     if(not is_ioc):
#                         match_order(new_order)
#                     messages.success(request, 'Your order has been placed successfully!')
#                     return redirect('/home')

#             else:
#                 new_order = Stoplossorder (
#                     order_type=order_type,
#                     order_mode=order_mode,
#                     quantity=quantity,
#                     disclosed=disclosed,
#                     target_price=target_price,
#                     price=price,
#                     is_matched=False,
#                     is_ioc=is_ioc,
#                     user=user
#                 )

#                 if disclosed < 0.1 * quantity:  # disclosed_quantity should not be > 10% of quantity
#                     messages.error(request, "Disclosed Quantity cannot be less than 10% greater than Quantity.")

#                 else:
#                     # Proceed with saving the order or further logic
#                     messages.success(request, "Stoploss Order placed successfully!")
#                     new_order.save()
#                     messages.success(request, 'Your Stoploss order has been placed successfully!')
#                     return redirect('/home')


#         except Exception as e:
#             render(request, 'trading/home.html', {'error': 'Unable to fetch market price for the order type.'})
        


#     # Fetch orders associated with the user
#     orders = Order.objects.filter(user=user)  # Filter orders by the logged-in user

#     return render(request, 'trading/home.html', {'user': user, 'orders': orders})

@login_required  # Ensure the user is logged in before accessing this view
def home(request):
    user = request.user  # Get the logged-in user
    user, created = User.objects.get_or_create(username=user)

    if request.method == "POST":
        order_type = request.POST.get('order_type')
        order_mode = request.POST.get('order_mode')
        quantity = int(request.POST.get('quantity'))
        disclosed = int(request.POST.get('disclosed_quantity'))
        stoploss_order = request.POST.get('Stoploss_order')
        target_price = request.POST.get('Target_price')
        is_ioc = request.POST.get('is_ioc') == 'True'

        price = None
        end_time = request.POST.get('end_time')

        if disclosed == 0:
            disclosed = quantity

        try:
            if order_mode == "LIMIT":
                price = float(request.POST.get('price', 0))  # Default to 0 if no price is provided

            elif order_mode == "MARKET":
                if order_type == "BUY":
                    # Fetch the JSON response from the best ask view
                    best_ask_response = fetch_best_ask()
                    best_ask_data = best_ask_response
                    price = float(best_ask_data['price'])

                elif order_type == "SELL":
                    # Fetch the JSON response from the best bid view
                    best_bid_response = fetch_best_bid()
                    best_bid_data = best_bid_response
                    price = float(best_bid_data['price'])

                if price is None:
                    return render(request, 'trading/home.html', {'error': 'Unable to fetch market price for the order type.'})

            if disclosed > quantity:
                disclosed = quantity

            if stoploss_order == 'NO':
                # Save or process the order here
                new_order = Order(
                    order_type=order_type,
                    order_mode=order_mode,
                    quantity=quantity,
                    disclosed=disclosed,
                    price=price,
                    is_matched=False,
                    is_ioc=is_ioc,
                    user=user  # Ensure the order is associated with the logged-in user
                )

                if disclosed < 0.1 * quantity:
                    messages.error(request, "Disclosed Quantity cannot be less than 10% greater than Quantity.")
                else:
                    messages.success(request, "Order placed successfully!")
                    new_order.save()
                    if not is_ioc:
                        match_order(new_order)
                    messages.success(request, 'Your order has been placed successfully!')
                    return redirect('/home')

            else:
                latest_trade = Trade.objects.latest('timestamp')
                current_price = latest_trade.price
                
                if(order_type == "BUY" and current_price>target_price):
                        # Save or process the order here
                        new_order = Order(
                            order_type=order_type,
                            order_mode=order_mode,
                            quantity=quantity,
                            disclosed=disclosed,
                            price=price,
                            is_matched=False,
                            is_ioc=is_ioc,
                            user=user  # Ensure the order is associated with the logged-in user
                        )

                        if disclosed < 0.1 * quantity:
                            messages.error(request, "Disclosed Quantity cannot be less than 10% greater than Quantity.")
                        else:
                            messages.success(request, "Stoploss Order placed successfully!")
                            new_order.save()
                            if not is_ioc:
                                match_order(new_order)
                            messages.success(request, 'Your Stoploss order has been placed successfully!')
                            return redirect('/home')
                        
                elif(order_type == "SELL" and current_price<target_price):
                        new_order = Order(
                            order_type=order_type,
                            order_mode=order_mode,
                            quantity=quantity,
                            disclosed=disclosed,
                            price=price,
                            is_matched=False,
                            is_ioc=is_ioc,
                            user=user  # Ensure the order is associated with the logged-in user
                        )

                        if disclosed < 0.1 * quantity:
                            messages.error(request, "Disclosed Quantity cannot be less than 10% greater than Quantity.")
                        else:
                            messages.success(request, "stoploss Order placed successfully!")
                            new_order.save()
                            if not is_ioc:
                                match_order(new_order)
                            messages.success(request, 'Your stoplossorder has been placed successfully!')
                            return redirect('/home')
                else:   
                    
                    new_stoploss_order = Stoplossorder(
                        order_type=order_type,
                        order_mode=order_mode,
                        quantity=quantity,
                        disclosed=disclosed,
                        target_price=target_price,
                        price=price,
                        is_matched=False,
                        is_ioc=is_ioc,
                        user=user
                    )

                    if disclosed < 0.1 * quantity:
                        messages.error(request, "Disclosed Quantity cannot be less than 10% greater than Quantity.")
                    else:
                        messages.success(request, "Stoploss Order placed successfully!")
                        new_stoploss_order.save()
                        messages.success(request, 'Your Stoploss order has been placed successfully!')
                        return redirect('/home')
        
        except Exception as e:
            return render(request, 'trading/home.html', {'error': 'An error occurred while processing your order.'})

    # Fetch orders associated with the user
    orders = Order.objects.filter(user=user)
    stoploss_orders = Stoplossorder.objects.filter(user=user)  # Fetch stop-loss orders separately

    return render(request, 'trading/home.html', {'user': user, 'orders': orders, 'stoploss': stoploss_orders})


from django.shortcuts import render
from .models import Order
from django.shortcuts import render
from .models import Order, Trade

def orderbook(request):
    # Retrieve unmatched buy orders (sorted by price in descending order)
    buy_orders = Order.objects.filter(is_matched=False, order_type='BUY').order_by('-price')
    # Retrieve unmatched sell orders (sorted by price in ascending order)
    sell_orders = Order.objects.filter(is_matched=False, order_type='SELL').order_by('price')
    
    # Retrieve all trades (you may filter or sort as needed)
    trades = Trade.objects.all().order_by('-timestamp')  # Sorting trades by timestamp
    
    # Display both buy and sell orders in the orderbook, along with trades
    return render(request, 'trading/orderbook.html', {
        'buy_orders': buy_orders,
        'sell_orders': sell_orders,
        'best_bid': buy_orders.first() if buy_orders else None,
        'best_ask': sell_orders.first() if sell_orders else None,
        'trades': trades  # Pass trades to the template
    })

@login_required
def modify(request):
    # Retrieve unmatched buy orders (sorted by price in descending order)
    buy_orders = Order.objects.filter(is_matched=False, order_type='BUY').order_by('-price')
    # Retrieve unmatched sell orders (sorted by price in ascending order)
    sell_orders = Order.objects.filter(is_matched=False, order_type='SELL').order_by('price')
    
    # Retrieve all trades (you may filter or sort as needed)
    trades = Trade.objects.all().order_by('-timestamp')  # Sorting trades by timestamp
    
    # Display both buy and sell orders in the orderbook, along with trades
    return render(request, 'trading/modify.html', {
        'buy_orders': buy_orders,
        'sell_orders': sell_orders,
        'best_bid': buy_orders.first() if buy_orders else None,
        'best_ask': sell_orders.first() if sell_orders else None,
        'trades': trades  # Pass trades to the template
    })

@login_required  
def modify_order_page(request):
    # Retrieve unmatched buy orders (sorted by price in descending order)
    buy_orders = Order.objects.filter(is_matched=False, order_type='BUY').order_by('-price')
    # Retrieve unmatched sell orders (sorted by price in ascending order)
    sell_orders = Order.objects.filter(is_matched=False, order_type='SELL').order_by('price')
    
    # Retrieve all trades (you may filter or sort as needed)
    trades = Trade.objects.all().order_by('-timestamp')  # Sorting trades by timestamp

    # Display both buy and sell orders in the orderbook, along with trades
    return render(request, 'trading/modify_order.html', {
        'buy_orders': buy_orders,
        'sell_orders': sell_orders,
        'trades': trades  # Pass trades to the template
    })
     
@login_required  
def update_prev_order(request):
    if request.method == 'POST':
        try:
            # Extract the order_id and quantity from the JSON body
            data = json.loads(request.body)
            order_id = data.get('order_id')
            new_quantity = data.get('quantity')
            new_disclosed = data.get('disclosed_quantity')

            # Validate the order_id and new_quantity as integers
            order_id = int(order_id)
            new_quantity = int(new_quantity)
            new_disclosed = int(new_disclosed)
            
            print(f"Received order update: Order ID = {order_id}, Quantity = {new_quantity}, Disclosed Quantity = {new_disclosed}")
              
            # Check if the order exists
            order = Order.objects.get(id=order_id)
            if order.is_matched == True:
                return JsonResponse({'success': False, 'message': 'Order has already been placed. No modifications allowed.'})
            if new_disclosed < new_quantity * 0.1:
                return JsonResponse({'success': False, 'message': 'Disclosed value must be greater then 10% of quantity.'})
            if new_disclosed > new_quantity:
                return JsonResponse({'success': False, 'message': 'Cannot disclose more than the quantity.'})
            order.quantity = new_quantity
            order.disclosed = new_disclosed
            order.save()

            return JsonResponse({'success': True})

        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Order not found.'})
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid data provided.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})




def clear_database(request):
    Order.objects.all().delete()
    Trade.objects.all().delete()
    return redirect('login')

def get_buy_orders(request):
    if request.method == 'GET':
        buy_orders = Order.objects.filter(order_type='BUY', is_matched = False).values('price','disclosed', 'is_matched', 'id','is_ioc')
        return JsonResponse({'buy_orders': list(buy_orders)})

def get_sell_orders(request):
    if request.method == 'GET':
        sell_orders = Order.objects.filter(order_type='SELL', is_matched = False).values('price','disclosed', 'is_matched','is_ioc')
        return JsonResponse({'sell_orders': list(sell_orders)})

def get_recent_trades(request):
    if request.method == 'GET':
        recent_trades = Trade.objects.all().order_by('-timestamp')[:10].values(
            'buyer','seller', 'price', 'quantity', 'timestamp'
        )  # Adjust fields and ordering as needed
        return JsonResponse({'trades': list(recent_trades)})



