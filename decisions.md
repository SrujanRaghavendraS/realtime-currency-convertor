# Which APIs did u use and why?
A free key gives 5,000 calls a month at 10 a minute window.With no key it gives 100 calls an hour per IP. Our 10/15-minute collector stays under 81% of the monthly quota.
MEanwhile If i could play with the rates at which the Different tier calls the API I could show and differentiate b/w the service quality

# Whats the fallback stratergy when the service fails?
Looking into the subscription tier and efficiency(to gain quality trust) in the free tier the fallback is the EWMA(Exponentially weighted moving averages) This doesn't require additional or different(Paid API) calls making it free calculated with sliding window approach.
Suppose if here also there is a service failure we can go with the latest value in the premmium service which we cache is redis.

For the Premium service.There will be a different data provider and even if that faills,last known good rate is there as a second fallback.

# How do u handle Conflicting data from different sources?
The primary data source is the provider who refreshes their data high frequently with less waiting time for next refresh and such data should be treated as primary source.
Based on similar tech specifications we can choose the next provider also.

However suppose if there are too large deviations then we need to come up with different stratergy to choose the best.We need to find some suitable algorithm in such a case especialy these are anomalies so anomalis based on different trends should be compared

# How does the user see when the data is stale or things fail?
When thigs fail there are clear indications how the data is generated so we are transparent how the data is calculated based on the previous datapoints cached in the REDIS .
So clear indications are there when data is predicted when not.So higher the collected data from the APIs higher the accuracy for EWMA algo

# Did u do anything to improve the Staleness of the data? if so,what?
Since I am using a Public Free API for both the Free/Paid Tiers and im playing with the frequency of calls to differentiate, On the trading days when there are high fluctuations I will be calling 10 min once on non-trading days i will be calling 15 min once.However to be more precise we need to do some analysis on the Currencies values considering the factors like trading/non trading days, playing with frequencies.Currently the free tier calls the API for every 5 calls of the Premium service so that we can differentiate the valu trends and understand the working of the dashboard

# What did u cut to ship today?
Using the Paid APIs for real time data,streaming the realtime data rather than calling APIs all time using Kafka or rabbitMQ(MQTT), could have researched on even high accurate algorithms.

# What would u add with more time?
Analyse the timeseries data understand the real loopholes in the trends identifying how our system can fail due to the Unpredictable trends,Build a scalable system design including queuing systems and for all possible currencies .Currently only for 5 different currencies i have built.

# Any other thoughts u had while building this out?
1.Yes Like when the values of currencies are so much fluctuating How to international payment gateways process transactions,
2.What if the main SoT(Source of Truth)fails Are all systems dependent on that? How should we approach in that direction.
3.What additional problem we should research about that when solved, user acqustion rate increases