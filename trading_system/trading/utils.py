from django.db import transaction
from django.utils import timezone
from .models import Order, Trade,Stoplossorder


def match_order(new_order):
    print("match")
    closing_price= None
    # Begin a transaction to ensure atomicity
    with transaction.atomic():
        # For a BUY limit order, we are looking for SELL orders at the same price or lower
        if new_order.order_type == 'BUY' and new_order.order_mode == 'LIMIT':
            opposite_orders = Order.objects.filter(
                order_type='SELL', 
                order_mode='LIMIT', 
                price__lte=new_order.price, 
                is_matched=False
            ).order_by('price', 'timestamp')
        
        # For a SELL limit order, we are looking for BUY orders at the same price or higher
        elif new_order.order_type == 'SELL' and new_order.order_mode == 'LIMIT':
            opposite_orders = Order.objects.filter(
                order_type='BUY', 
                order_mode='LIMIT', 
                price__gte=new_order.price, 
                is_matched=False
            ).order_by('-price', 'timestamp')

        # For a BUY market order, we are looking for SELL orders with the lowest price
        elif new_order.order_type == 'BUY' and new_order.order_mode == 'MARKET':
            opposite_orders = Order.objects.filter(
                order_type='SELL', 
                is_matched=False
            ).order_by('price', 'timestamp')

        # For a SELL market order, we are looking for BUY orders with the highest price
        elif new_order.order_type == 'SELL' and new_order.order_mode == 'MARKET':
            opposite_orders = Order.objects.filter(
                order_type='BUY', 
                is_matched=False
            ).order_by('-price', 'timestamp')

        # Immediate or Cancellation (IOC) orders
        if new_order.is_ioc:
            # Track executed quantity for IOC orders
            executed_quantity=0
            
            for opposite_order in opposite_orders:
                if new_order.quantity<=0:
                    break
                
                match_quantity=min(new_order.quantity,opposite_order.quantity)
                
                # Create a trade entry for the matched orders
                Trade.objects.create(
                    buyer=new_order.user if new_order.order_type == 'BUY' else opposite_order.user,
                    seller=opposite_order.user if new_order.order_type == 'BUY' else new_order.user,
                    quantity=match_quantity,
                    price=opposite_order.price,
                    timestamp=timezone.now()
                )
                
                #changes:
                closing_price = opposite_order.price
                # Update quantities
                executed_quantity += match_quantity
                new_order.quantity -= match_quantity
                opposite_order.quantity -= match_quantity
                
                # Update disclosed quantity if needed
                if(opposite_order.disclosed>opposite_order.quantity):# < to > Akshat
                    opposite_order.disclosed=opposite_order.quantity
                if(new_order.disclosed>new_order.quantity):# < to > Akshat
                    new_order.disclosed=new_order.quantity
                
                # Update opposite order status
                if opposite_order.quantity == 0:
                    opposite_order.is_matched = True
                opposite_order.save()
            
            # Handle IOC order after matching
            if executed_quantity>0:
                # Partially executed:save with executed quantity and mark as matched
                new_order.quantity=0  # Discard remaining quantity
                new_order.is_matched=True
                new_order.disclosed=0 
                print("saved1")
                new_order.save()
                return  # To prevent further processing
            else:
                # Completely unexecuted:delete the order
                print("delete1")
                new_order.delete()
                return

        # Try to match with the opposite orders
        if(new_order.order_mode=="LIMIT"):
            remaining_quantity = new_order.quantity
            for opposite_order in opposite_orders:
                if remaining_quantity <= 0:
                    break
                
                match_quantity = min(remaining_quantity, opposite_order.quantity)

                # For limit orders, the price is already set in the opposite order
                if new_order.order_mode == 'LIMIT':
                    match_price = opposite_order.price
                # For market orders, the price is taken from the best available order
                else:
                    match_price = opposite_order.price

                # Create a trade entry for the matched orders
                Trade.objects.create(
                    buyer=new_order.user if new_order.order_type == 'BUY' else opposite_order.user,
                    seller=opposite_order.user if new_order.order_type == 'BUY' else new_order.user,
                    quantity=match_quantity,
                    price=match_price,
                    timestamp=timezone.now()
                )
                #changes
                closing_price = match_price
                # Update the quantities of the matched orders
                remaining_quantity -= match_quantity
                opposite_order.quantity -= match_quantity
                new_order.quantity -= match_quantity
                if(opposite_order.disclosed>opposite_order.quantity):# < to > Akshat
                    opposite_order.disclosed=opposite_order.quantity
                if(new_order.disclosed>new_order.quantity):# < to > Akshat
                    new_order.disclosed=new_order.quantity
                opposite_order.save()
                new_order.save()

                # If the opposite order is fully matched, mark it as matched
                if opposite_order.quantity == 0:
                    opposite_order.is_matched = True
                    opposite_order.save()

                # If the new order is fully matched, mark it as matched
                if new_order.quantity == 0:
                    new_order.is_matched = True
                    new_order.save()
                    
            stop_loss_buy_orders = Stoplossorder.objects.filter(order_type='BUY').order_by('target_price')
            stop_loss_sell_orders= Stoplossorder.objects.filter(order_type='SELL').order_by('-target_price')
            
            if closing_price is not None:
                # Process BY stop-loss orders
                for buy_order in stop_loss_buy_orders:
                    if buy_order.target_price <= closing_price:
                        if buy_order.order_mode=="MARKET":
                            best_ask_response = Order.objects.filter(order_type="SELL", is_matched=False).order_by('price').values('price', 'quantity').first()
                            best_ask_data = best_ask_response
                            price = best_ask_data['price']
                        else:
                            price=buy_order.price
                            
                        new_order = Order(
                            user=buy_order.user,
                            order_type=buy_order.order_type,
                            order_mode=buy_order.order_mode,  # Assuming stop-loss orders are treated as limit orders
                            quantity=buy_order.quantity,
                            price=price,  # Use target_price as the price for the order
                            disclosed=buy_order.disclosed,  # Copy disclosed quantity if it exists
                            timestamp=timezone.now(),
                            is_matched=False  # Mark as unmatched initially
                        )
                        new_order.save()
                        match_order(new_order)
                        buy_order.delete()
                        
                for sell_order in stop_loss_sell_orders:
                    if sell_order.target_price >= closing_price:
                             # Move the order to the main Order table
                            if buy_order.order_mode=="MARKET":
                                best_ask_response = Order.objects.filter(order_type="BUY", is_matched=False).order_by('-price').values('price', 'quantity').first()
                                best_ask_data = best_ask_response
                                price = best_ask_data['price']
                            else:
                                price=sell_order
                                 # Move the order to the main Order table
                            new_order = Order(
                                user=sell_order.user,
                                order_type=sell_order.order_type,
                                order_mode=sell_order.order_mode,  # Assuming stop-loss orders are treated as limit orders
                                quantity=sell_order.quantity,
                                price=price,  # Use target_price as the price for the order
                                disclosed=sell_order.disclosed if hasattr(sell_order, 'disclosed') else 0,  # Copy disclosed quantity if it exists
                                timestamp=timezone.now(),
                                is_matched=False  # Mark as unmatched initially
                            ) 
                            new_order.save()
                            match_order(new_order)
                            sell_order.delete()   
            

            # If the new order is partially matched, update its quantity and status
            if new_order.quantity > 0:
                new_order.save()
            else:
                new_order.is_matched = True
                new_order.save()

            # Ensure that any remaining unmatched orders are still available for future matches
            new_order.timestamp = timezone.now()
            new_order.save()
            
            
        else:
            remaining_quantity=new_order.quantity
            complete_order=False
            # while(remaining_quantity>0):
            try:
                closing_price=None
                for opposite_order in opposite_orders:
                    if(remaining_quantity<=0):
                        complete_order=True
                        break
                    match_quantity=min(opposite_order.quantity,remaining_quantity)
                    if(match_quantity==opposite_order.quantity):
                        Trade.objects.create(
                            buyer=new_order.user if new_order.order_type == 'BUY' else opposite_order.user,
                            seller=opposite_order.user if new_order.order_type == 'BUY' else new_order.user,
                            quantity=match_quantity,
                            price=opposite_order.price,
                            timestamp=timezone.now()
                        )
                        #changes:
                        closing_price = opposite_order.price
                        
                        remaining_quantity-=match_quantity
                        opposite_order.quantity -= match_quantity
                        new_order.quantity -= match_quantity
                        if(opposite_order.disclosed>opposite_order.quantity):# < to > Akshat
                            opposite_order.disclosed=opposite_order.quantity
                        if(new_order.disclosed>new_order.quantity):# < to > Akshat
                            new_order.disclosed=new_order.quantity
                        opposite_order.is_matched = True
                        opposite_order.save()
                        new_order.save()
                    else:
                        Trade.objects.create(
                            buyer=new_order.user if new_order.order_type == 'BUY' else opposite_order.user,
                            seller=opposite_order.user if new_order.order_type == 'BUY' else new_order.user,
                            quantity=match_quantity,
                            price=opposite_order.price,
                            timestamp=timezone.now()
                        )
                        #changes:
                        closing_price = opposite_order.price
                        
                        remaining_quantity-=match_quantity
                        opposite_order.quantity -= match_quantity
                        new_order.quantity -= match_quantity
                        if(opposite_order.disclosed>opposite_order.quantity):# < to > Akshat
                            opposite_order.disclosed=opposite_order.quantity
                        if(new_order.disclosed>new_order.quantity):# < to > Akshat
                            new_order.disclosed=new_order.quantity
                        new_order.is_matched=True
                        opposite_order.save()
                        new_order.save()
                print(closing_price)
                
                stop_loss_buy_orders =  Stoplossorder.objects.filter(order_type='BUY').order_by('target_price')
                stop_loss_sell_orders = Stoplossorder.objects.filter(order_type='SELL').order_by('-target_price')
                
                if closing_price is not None:
                    for buy_order in stop_loss_buy_orders:
                        if buy_order.target_price <= closing_price:
                            if buy_order.order_mode=="MARKET":
                                best_ask_response = Order.objects.filter(order_type="SELL", is_matched=False).order_by('price').values('price', 'quantity').first()
                                best_ask_data = best_ask_response
                                price = best_ask_data['price']
                            else:
                                price=buy_order
                    # Move the order to the main Order table
                            new_order = Order(
                                user=buy_order.user,
                                order_type=buy_order.order_type,
                                order_mode=buy_order.order_mode,  # Assuming stop-loss orders are treated as limit orders
                                quantity=buy_order.quantity,
                                price=price,  # Use target_price as the price for the order
                                disclosed=buy_order.disclosed,  # Copy disclosed quantity if it exists
                                timestamp=timezone.now(),
                                is_matched=False  # Mark as unmatched initially
                            )
                            new_order.save()
                            match_order(new_order)
                            buy_order.delete()
                            
                    for sell_order in stop_loss_sell_orders:
                        if sell_order.target_price >= closing_price:
                            if buy_order.order_mode=="MARKET":
                                best_ask_response = Order.objects.filter(order_type="BUY", is_matched=False).order_by('-price').values('price', 'quantity').first()
                                best_ask_data = best_ask_response
                                price = best_ask_data['price']
                            else:
                                price=sell_order
                                 # Move the order to the main Order table
                            new_order = Order(
                                user=sell_order.user,
                                order_type=sell_order.order_type,
                                order_mode=sell_order.order_mode,  # Assuming stop-loss orders are treated as limit orders
                                quantity=sell_order.quantity,
                                price=price,  # Use target_price as the price for the order
                                disclosed=sell_order.disclosed if hasattr(sell_order, 'disclosed') else 0,  # Copy disclosed quantity if it exists
                                timestamp=timezone.now(),
                                is_matched=False  # Mark as unmatched initially
                            )
                            # Delete    
                            # the order from the stop-loss table
                            new_order.save()
                            match_order(new_order)
                            sell_order.delete()
                
                
                        
                        
                        
            except Exception as e:
                print('Some Error Occured')


            
            
            if(complete_order==False):
                #the leftover quantity is converted to 0
                remaining_quantity=0
                new_order.quantity=0
                new_order.is_matched=True
                new_order.save()
                print("Incomplete order Placed")
                
    
    

               
                
            




