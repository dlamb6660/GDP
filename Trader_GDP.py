# (c) Daniel Lamb 2013
class Trader_GDP(Trader):

        def __init__(self, ttype, tid, balance):
                self.ttype = ttype
                self.tid = tid
                self.balance = balance
                self.blotter = []
                self.orders = []
                self.alloffers = []
                self.TB = []
                self.A = []
                self.RB = []
                # same lists need to be sorted by price for optimisations
                self.TB_asc = [] 
                self.A_asc = []
                self.RB_asc = []

                self.nrecent = 60
                self.graceperiod = 15
                self.job = None
                self.limit = None
                self.active = False
                self.margin_buy = -1.0*(0.05 + 0.3*random.random())
                self.margin_sell = 0.05 + 0.3*random.random()
                self.momntm = 0.1*random.random()
                self.beta = 0.1 + 0.4*random.random()
                self.prev_change = 0
                self.min = 1
                self.max = 200

        def getorder(self, time, countdown, lob):
                if len(self.orders) < 1:
                        self.active = False
                        order = None
                else:
                        self.active = True
                        self.limit = self.orders[0].price
                        self.job = self.orders[0].otype
                        if self.job == 'Bid':
                                # currently a buyer (working a bid order)
                                self.margin = self.margin_buy
                        else:
                                # currently a seller (working a sell order)
                                self.margin = self.margin_sell
                        quoteprice = int(self.limit * (1 + self.margin))
                        self.price = quoteprice

                        order=Order(self.tid, self.job, quoteprice, self.orders[0].qty, time)

                return order

        def tupaccepted(self, tup):
                # return true if the argument tup is an offer that has been accepted
                accepted = False
                for tup2 in self.TB:
                        if tup[0] == tup2[0] and tup[1] == tup2[1]:
                                accepted = True
                return accepted

        def alreadystored(self, price):
                for tup in self.alloffers:
                        if tup[1] == price:
                                return True
                return False

        def updatealloffers(self, lob, time):
                prev_alloffers = self.alloffers
                self.alloffers = []
                # store all offers that are still within (n+grace) recent trades
                for tup in prev_alloffers:
                        if tup[0] >= (time-(self.nrecent + self.graceperiod)) and not self.tupaccepted(tup):
                                self.alloffers.append((tup[0], tup[1]))

                # and also store any new offers
                for tup in lob['bids']['lob']:
                        if not self.alreadystored(tup[0]):
                                self.alloffers.append((time, tup[0]))


        def calculateTBL(self, trade, time):
                prev_TB = self.TB
                self.TB = []
                # store old trades that are still within n recent trades
                for tup in prev_TB:
                        if tup[0] >= (time-self.nrecent):
                                self.TB.append((tup[0], tup[1]))

                # and also store any new completed trades
                if trade != None:
                        self.TB.append((trade['time'], trade['price']))

                self.TB_asc = sorted(self.TB, key=lambda x: x[1])

        def calculateRBL_AL(self, lob, time):
                # rejected bids are offers that have existed for a certain 'grace period'
                # so store offers that are older than time-grace but younger than time-(nrecent+grace)
                self.RB = []
                self.A = []

                # self.alloffers is already filtered to stuff 
                # that is within the last (nrecent+graceperiod) seconds
                for tup in self.alloffers:
                        if (time-self.graceperiod) > tup[0]:
                                # all offers that have existed for grace period 
                                # -> count as rejected
                                self.RB.append((tup[0], tup[1]))
                        else:
                                # else it is an open offer -> count as offer
                                self.A.append((tup[0], tup[1]))
                self.RB_asc = sorted(self.RB, key=lambda x: x[1])
                self.A_asc = sorted(self.A, key=lambda x: x[1])

        def lenTB(self, price, prev_lenTB):
                start = prev_lenTB
                tb = start

                for i in range(start, len(self.TB_asc)):
                        if self.TB_asc[i][1] <= price:
                                tb+=1
                        else:
                                break
                return tb


        def lenRB(self, price, prev_lenRB):
                start = prev_lenRB
                rb = start

                for i in range(start, len(self.RB_asc)):
                        if self.RB_asc[i][1] <= price:
                                rb+=1
                        else:
                                break
                return rb


        def lenA(self, price, prev_lenA):
                start = prev_lenA
                a = start

                for i in range(start, len(self.A_asc)):
                        if self.A_asc[i][1] <= price:
                                a+=1
                        else:
                                break
                return a


        def calculatebelieffunction(self):
                optimum_price = None
                optimum = 0
                prev_belief = 0
                prev_lenTB = 0
                prev_lenA = 0
                prev_lenRB = 0
                for p in range(self.min, self.max):
                        lenTB = self.lenTB(p,prev_lenTB)
                        lenRB = self.lenRB(p,prev_lenRB)
                        lenA = self.lenA(p,prev_lenA)
                        prev_lenTB = lenTB
                        prev_lenA = lenA
                        prev_lenRB = lenRB

                        denom = (lenTB+lenA+lenRB)
                        if denom == 0:
                                belief = 0
                        else:
                                belief = float(lenTB + lenA) / denom

                        if self.job == 'Ask':
                                belief = 1 - belief

                        profit = self.profit_function(p)
                        product = belief * profit
                        if (self.job == 'Bid' and product > optimum and not lenTB == 0):
                                optimum = product
                                optimum_price = p
                                prev_belief = belief
                        elif (self.job == 'Ask' and product > optimum and belief > prev_belief):
                                optimum = product
                                optimum_price = p
                                prev_belief = belief
                return optimum_price

        def profit_function(self, price):
                if self.job=='Bid':
                        return self.limit - price
                elif self.job == 'Ask':
                        return price - self.limit
                return None


        def respond(self, time, lob, trade, verbose):

                def profit_alter(price):
                        oldprice = self.price
                        diff = price - oldprice
                        change = ((1.0-self.momntm)*(self.beta*diff)) + (self.momntm*self.prev_change)
                        self.prev_change = change
                        newmargin = ((self.price + change)/self.limit) - 1.0

                        if self.job=='Bid':
                                if newmargin < 0.0 :
                                        self.margin_buy = newmargin
                                        self.margin = newmargin
                        else :
                                if newmargin > 0.0 :
                                        self.margin_sell = newmargin
                                        self.margin = newmargin

                        #set the price from limit and profit-margin
                        self.price = int(round(self.limit*(1.0+self.margin),0))


                if (self.job == 'Bid' or self.job == 'Ask'):
                        self.calculateTBL(trade, time)
                        if (time%0.5 == 0):
                                self.calculateTBL(trade, time)
                                self.updatealloffers(lob, time)
                                # self.calculateAL(lob, time)
                                self.calculateRBL_AL(lob, time)

                                final_price = self.calculatebelieffunction()
                                if not final_price == None:
                                        profit_alter(final_price)