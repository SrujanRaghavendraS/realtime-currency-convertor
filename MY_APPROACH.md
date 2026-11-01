# These are the steps which I followed

-> Understand the Problem statement carefully
-> Understand where the Free Tier fails and as mentioned in FAllback we should not loose potential users who could buy the subscription and for such profitable conversions I choose an algo instead of another API
->Similarly for the Fallback for Premium users we cannot afford to loose them so we need to provide with another API as a backup
->The UI Part I wanted the show the difference of service that Paid users get and Free users wont
so that its easy to differentiate b/w the features.
-> I wanted the readers to understand how the oveerall system works so Including the rate limiting stratergies and other constraints I wanted to build an efficient system making use of all free reource and cost optimising the requirement .
->I especially wanted to show how Fallbacks works in either cases so have given a simulator where in the EWMA Algorithm works and provides the values accrurately so have added a CTA for user understanding
->Have given the API rates understanding so the end evaluator can understand how rate limits are mitigated
->Also added a flow chat for the understanding of the opverall application
->MAin areas of concerns were The Fall back stratergy,How to show the live data to the users(We could have streamded though),the system understanding, and making use of available free resources to show how the system works so that end users could differentiate b/w the FREE and the paid Tier