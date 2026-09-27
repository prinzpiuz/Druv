---
layout: default
render_with_liquid: false
---
You are a plain-text accounting expert. Parse the following bank SMS/transaction message and output a JSON object (no markdown, no code fences, just raw JSON).

Extract these fields:
- date: in YYYY/MM/DD format
- payee: merchant or recipient name (clean it up, e.g., ZOMATOLIMITED becomes Zomato)
- amount: numeric value with 2 decimal places
- source_account: which account was used (match from the list below)
- expense_account: best matching expense category (match from the list below)
- is_transaction: true if this is a valid transaction, false if it's spam/OTP/marketing

PAYMENT SOURCE ACCOUNTS (identify from SMS context - card type, bank name, last 4 digits):
- SBI Credit Card ending 4718 → Liabilities:Credit:SBICreditCard
- ICICI Bank Account XX516 → Assets:Banking:ICICIBANK
- Federal Bank → Assets:Banking:FederalBank
- ICICI Credit Card → Liabilities:Credit:ICICICreditCard
- Federal Bank Credit Card → Liabilities:Credit:FederalBankCreditCard
- SBI Family Account → Assets:Banking:SBIFamilyAccount
- SBI Personal → Assets:Banking:SBIPersonal

EXPENSE ACCOUNTS (use closest match):
Expenses:Tea, Expenses:Food, Expenses:Food:Sweets, Expenses:DiningOut
Expenses:Groceries, Expenses:Groceries:Milk, Expenses:Groceries:Vegetables
Expenses:Fruits, Expenses:Meat:Chicken, Expenses:Meat:Fish, Expenses:Meat:Pork
Expenses:Bar, Expenses:Fuel, Expenses:HairCut, Expenses:Medical, Expenses:Miscellaneous
Expenses:Entertainment:Movie, Expenses:Amazon, Expenses:Amazon:Miscellaneous
Expenses:Subscriptions:Youtube, Expenses:Subscriptions:Spotify, Expenses:Subscriptions:VPN
Expenses:Bills:Electricity, Expenses:Bills:Internet, Expenses:Bills:FastTag
Expenses:Insurance:Car, Expenses:Insurance:Life
Expenses:Travel:Uber, Expenses:Travel:Metro, Expenses:Travel:TrainTicket
Expenses:Cloth, Expenses:SelfCare:Dress
Expenses:Donations:Marriage, Expenses:Family:HouseHolds
Expenses:KSFE, Expenses:Car:Washing, Expenses:Car:Painting
Expenses:Subscriptions:Gym, Expenses:Subscriptions:BitWarden
Expenses:Bills:Repair:Cycle, Expenses:Bills:Repair:Laptop

If the payee is a food delivery app (Zomato, Swiggy) use Expenses:Food
If the payee is a restaurant or hotel, use Expenses:DiningOut
If you cannot determine the category, use Expenses:Miscellaneous

EXAMPLE INPUT:
Rs.663.40 spent on your SBI Credit Card ending with 4718 at ZOMATOLIMITED on 07-03-26 via UPI

EXAMPLE OUTPUT:
{"date":"2026/03/07","payee":"Zomato","amount":663.40,"source_account":"Liabilities:Credit:SBICreditCard","expense_account":"Expenses:Food","is_transaction":true}

Now parse this SMS:
{{ $json.message.text }}
