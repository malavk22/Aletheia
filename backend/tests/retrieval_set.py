"""The fixed retrieval check set (V0.8): made-up documents, and questions
labelled with the page(s) that answer them. Retrieval upgrades are measured
against it, so it must not change once a baseline is recorded: a new question
would change every score, old and new.

Question kinds:
- words: the question uses the document's own words.
- reworded: the same meaning in other words ("cat" for "pets").
- names: a name, number or code is what identifies the answer.
- parts: two questions in one, answered on two pages, often in two documents.
"""

DOCUMENTS = {
    "lease.pdf": [
        # 1
        "Tenancy agreement. This agreement is made between Northgate Homes Ltd, "
        "the landlord, and Maya Fernandes, the tenant, for the flat at 14 Elm Court, "
        "Baner Road, Pune. The flat is let furnished, with the furniture listed in the "
        "inventory signed by both parties on the day the keys are handed over. The "
        "tenancy starts on 1 February 2026 and runs for 11 months. Only the tenant and "
        "the people named in this agreement may live in the flat. The landlord's "
        "representative for all questions about this agreement is the property office "
        "of Northgate Homes, open on weekdays.",
        # 2
        "Rent and deposit. The rent is 28,000 rupees per month, payable in advance by "
        "bank transfer on or before the 5th of each month. If the rent has not arrived "
        "by the 10th, a late payment fee of 500 rupees per day is charged until it is "
        "paid. Electricity, water and internet bills are paid by the tenant directly to "
        "the providers. The tenant pays a security deposit of 56,000 rupees, equal to "
        "two months of rent, before moving in. The deposit is returned within 21 days "
        "after the keys are given back, less the cost of any damage beyond normal wear "
        "and tear and any unpaid rent or bills.",
        # 3
        "Use of the flat. No pets may be kept in the flat, except fish in an aquarium. "
        "Smoking is not allowed indoors or on the balcony. Guests may stay for at most "
        "14 nights in a row. The tenant may not sublet the flat, or any room in it, "
        "without the landlord's written consent. The flat must be used as a home only, "
        "not as an office open to customers or as a shop. Loud music is not allowed "
        "after 10 pm, in line with the rules of the housing society.",
        # 4
        "Repairs and maintenance. The tenant must report any damage or fault to the "
        "landlord within 48 hours of noticing it. The landlord fixes urgent problems, "
        "such as a water leak or a failure of the electricity supply, within 24 hours "
        "of being told. The tenant pays for repairing damage that the tenant, members "
        "of the household or guests cause, whether by accident or not. Painting the "
        "walls, drilling holes or changing the locks needs the landlord's consent in "
        "writing. The landlord may visit to inspect the flat with 24 hours of notice.",
        # 5
        "Ending the tenancy. Either party may end this agreement by giving the other "
        "two months of notice in writing. The first six months are a lock-in period: "
        "if the tenant leaves during the lock-in period, the tenant pays the rent for "
        "the rest of the lock-in period. At the end of the tenancy the flat is "
        "inspected against the inventory in the presence of both parties. All keys and "
        "access cards must be returned on the last day.",
        # 6: shares words with many questions, answers none.
        "Definitions and general terms. In this agreement, notice means a letter or an "
        "email sent to the address of the other party given above. The deposit means "
        "the amount described in the clause on rent and deposit. The inventory means "
        "the signed list of furniture and fittings. Damage means harm beyond normal "
        "wear and tear. This agreement is governed by the laws of India, and the courts "
        "of Pune decide any dispute that the parties cannot settle between themselves.",
    ],
    "hr-policy.pdf": [
        # 1
        "Employee handbook: working hours. Office hours are 9:30 am to 6 pm, Monday to "
        "Friday, with a one-hour lunch break. Core hours, when everyone should be "
        "available for meetings, are 11 am to 4 pm. With their manager's approval, "
        "employees may work remotely for up to two days a week. Remote days are agreed "
        "a week in advance and recorded in the team calendar. Overtime must be approved "
        "by the manager before it is worked.",
        # 2
        "Leave. Employees get 24 days of paid annual leave per calendar year. Up to 5 "
        "unused days can be carried over to the next year; the rest lapse. Sick leave is "
        "10 days a year; a doctor's certificate is needed for more than 3 sick days in a "
        "row. Parental leave is 26 weeks for the birth parent and 4 weeks for the other "
        "parent. Leave requests are made in the HR portal at least two weeks in "
        "advance, except for sick leave.",
        # 3
        "Expenses. Work-related expenses are paid back when a claim is submitted in "
        "the HR portal within 30 days, with the original receipts. Air travel is booked "
        "in economy class through the travel desk. When travelling for work, a meal "
        "allowance of 1,200 rupees per day is paid. Claims over 20,000 rupees need the "
        "approval of a director before they are paid. Claims are paid with the next "
        "monthly salary.",
        # 4
        "Resignation. Permanent employees who resign must give a notice period of "
        "60 days. During probation, which is the first six months of employment, the "
        "notice period is 15 days. The final settlement of salary and leave is paid "
        "within 45 days of the last working day. Company laptops, phones and access "
        "cards must be handed back on the last working day.",
        # 5
        "Conduct and IT security. Passwords for company systems must be changed every "
        "90 days and never shared. Security incidents, such as a lost laptop or a "
        "suspicious email, must be reported to the IT security team within one hour. "
        "Company cloud storage may not be used for personal files. Complaints of "
        "harassment are handled confidentially by the Internal Committee.",
        # 6: shares words with many questions, answers none.
        "About this handbook. This handbook applies to all employees of Brightline "
        "Software in India, permanent or on probation. It is updated once a year by the "
        "HR team; the latest version is always in the HR portal. Managers explain the "
        "handbook to new employees in their first week. Questions about leave, "
        "expenses, notice or security can be sent to the HR helpdesk, which answers "
        "within two working days.",
    ],
    "meeting-notes.pdf": [
        # 1
        "Project Falcon steering meeting, 3 March 2026. Present: Ravi Menon, Lena "
        "Vogel, Arjun Rao and Priya Shah. Status: the launch is moved from 15 March to "
        "12 April 2026, because the certification of the payment gateway has been "
        "delayed by the provider. The project budget is 4.2 million rupees, of which "
        "2.9 million has been spent so far. The team agreed that quality comes before "
        "speed and that a second delay must be avoided.",
        # 2
        "Decisions. For hosting, the meeting chose Kestrel Cloud over Arcadia Systems, "
        "because Kestrel Cloud is 18% cheaper for the same service levels. Two QA "
        "contractors will be hired for six weeks to finish testing. The offline mode is "
        "dropped from release 1 and moved to release 2, to keep the scope small. The "
        "mobile app design stays as approved in January.",
        # 3
        "Risks and next steps. The main risk is that the payment gateway certification "
        "slips again. Ravi will contact the gateway provider by 20 March to confirm the "
        "new certification date. Lena will update the test plan to include the two "
        "contractors. Arjun will prepare the hosting contract with Kestrel Cloud. The "
        "next steering meeting is on 2 April 2026.",
        # 4: shares words with many questions, answers none.
        "Appendix: earlier actions. From the February meeting: Ravi compared the "
        "hosting offers, and this is done. Lena wrote the first test plan, and this is "
        "done. Priya presented the launch communication plan, which was approved. "
        "Arjun collected the release notes for the design review.",
    ],
    "router-manual.pdf": [
        # 1
        "AX-300 router user manual. In the box: the AX-300 Wi-Fi 6 router, a 12 V "
        "1.5 A power adapter, one network cable and this manual. The router has four "
        "LAN ports for wired devices and one WAN port for the modem. It supports up to "
        "64 connected devices at the same time.",
        # 2
        "Setting up the AX-300. Connect the WAN port to your modem with the network cable and "
        "plug in the power adapter. Join the Wi-Fi network called AX300 followed by "
        "four characters printed on the label. Open a browser and go to the admin "
        "address 192.168.8.1. Sign in with the default admin password printed on the "
        "sticker under the router, and choose a new password when asked.",
        # 3
        "AX-300 status lights. Solid blue: the router is connected to the internet. Blinking "
        "orange: the router is on, but there is no internet connection; check the "
        "modem and the cable. Solid red: hardware fault; switch the router off and "
        "contact support. No light: the router has no power.",
        # 4
        "AX-300 troubleshooting. If Wi-Fi is slow, place the router in an open spot, away "
        "from walls and metal, or choose another channel in the admin page. If you have "
        "forgotten the admin password, press and hold the reset button on the back for "
        "10 seconds: the router restarts with its factory settings, and you set it up "
        "again. Firmware updates are installed automatically at 3 am.",
        # 5
        "Warranty and support. The AX-300 has a 2-year warranty from the date of "
        "purchase. The warranty covers manufacturing defects. It does not cover damage "
        "from water, from dropping the router, or from opening its case. Register the "
        "router online within 30 days of purchase to extend the warranty by 6 months. "
        "Phone support is open from 8 am to 8 pm, every day.",
        # 6: shares words with many questions, answers none.
        "Safety information. Use the router indoors only, in a dry place with free "
        "air around it. Use only the power adapter supplied in the box. Do not open "
        "the case: there are no parts inside that you can repair yourself. Keep the "
        "router away from children. Dispose of the router as electronic waste, not with "
        "household rubbish.",
    ],
    "insurance-policy.pdf": [
        # 1
        "Health insurance policy summary. Policyholder: Maya Fernandes. Sum insured: "
        "5 lakh rupees per policy year. Policy period: 1 April 2026 to 31 March 2027. "
        "Annual premium: 18,400 rupees, including taxes. The policy covers the "
        "policyholder only; family members can be added at the next renewal.",
        # 2
        "What is covered. Hospital stays of more than 24 hours, and day-care "
        "procedures that need less than 24 hours. Road ambulance costs up to 2,000 "
        "rupees per hospital stay. Medical costs in the 30 days before admission and "
        "the 60 days after discharge, when they are for the same illness. Room rent is "
        "covered up to 1% of the sum insured per day.",
        # 3
        "What is not covered, and waiting periods. Illnesses that started before the "
        "policy, so-called pre-existing conditions, are covered only after 3 years. No "
        "illness is covered in the first 30 days of the policy, except injuries from "
        "an accident, which are covered from the first day. Cosmetic treatment is never "
        "covered; dental treatment only after an accident.",
        # 4
        "Claims and cancellation. For cashless treatment at a network hospital, tell "
        "the insurer within 24 hours of an emergency admission, or 48 hours before a "
        "planned one. For reimbursement, send the bills and the discharge summary "
        "within 15 days of discharge. You can cancel the policy within 15 days of "
        "receiving it, the free-look period, and get the full premium back.",
        # 5: shares words with many questions, answers none.
        "Definitions. Hospital means a registered hospital with at least 10 beds and "
        "doctors on duty day and night. A network hospital is a hospital that has an "
        "agreement with the insurer. Accident means a sudden, unforeseen event from an "
        "outside cause. Policy year means each year of the policy period. Premium means "
        "the amount paid for this insurance.",
    ],
    # Look-alikes: a second router and a policy for contractors. The right page
    # often depends on a name or number, not on the topic.
    "router-ax500-manual.pdf": [
        # 1
        "AX-500 router user manual. In the box: the AX-500 Wi-Fi 6E tri-band router, "
        "a 12 V 2 A power adapter, two network cables and this manual. The AX-500 has "
        "four LAN ports, one 2.5 gigabit WAN port and a USB port for sharing a drive. "
        "It supports up to 128 connected devices at the same time.",
        # 2
        "Setting up the AX-500. Connect the 2.5 gigabit WAN port to your modem and "
        "plug in the power adapter. Join the Wi-Fi network called AX500 followed by six "
        "characters printed on the label. Open the Aletheon app, or a browser at the "
        "admin address 192.168.10.1, and sign in with the setup code on the label.",
        # 3
        "AX-500 status lights. Solid white: connected to the internet. Solid orange: "
        "no internet connection; check the modem. Blinking orange: a firmware update is "
        "being installed; do not switch the router off. Blinking red: the router is too "
        "hot; move it to a place with more air.",
        # 4
        "AX-500 troubleshooting. If devices drop off the network, turn on band steering "
        "in the app. To return the AX-500 to its factory settings, hold the reset "
        "button for 5 seconds until the light blinks white. Firmware updates can be "
        "scheduled in the app, or installed by hand.",
        # 5
        "AX-500 warranty. The AX-500 has a 3-year warranty from the date of purchase, "
        "covering manufacturing defects. Accidental damage, such as a drop or a spill, "
        "is covered only with the CarePlus plan, bought within 60 days of purchase. "
        "Support is open by chat around the clock.",
    ],
    "contractor-policy.pdf": [
        # 1
        "Policy for contractors. This policy applies to independent contractors who "
        "work for Brightline Software under a service contract. Contractors are not "
        "employees: they do not get paid leave, sick leave or parental leave, and they "
        "plan their own time off, telling the project lead two weeks in advance.",
        # 2
        "Invoices and costs. Contractors send one invoice per month, by the 3rd of the "
        "next month, and are paid within 30 days of the invoice. Travel costs agreed in "
        "advance with the project lead are added to the monthly invoice, with copies of "
        "the tickets; costs older than 60 days are not paid.",
        # 3
        "Ending a contract. Either side may end a service contract with 7 days of "
        "written notice. Brightline Software may end it at once for a serious breach, "
        "such as sharing confidential information. All devices and access badges must "
        "be returned within 3 days after the contract ends.",
        # 4
        "Access and passwords for contractors. Contractors get an account that expires "
        "when the contract ends. Their passwords must be changed every 60 days and "
        "must not be reused. Contractors may only use the systems named in their "
        "contract.",
    ],
}

# Another person's workspace, with sentences very close to some questions. Its
# text must never be retrieved for the workspace above.
OTHER_WORKSPACE = {
    "other-lease.pdf": [
        "The late payment fee for rent is 900 rupees per day. Pets are allowed. The "
        "notice period is one month. The router admin address is 10.0.0.1.",
    ]
}

# (question, kind, the (file, page) pairs that answer it)
QUESTIONS = [
    ("What is the late payment fee for rent?", "words", [("lease.pdf", 2)]),
    ("How many days of paid annual leave do employees get?", "words", [("hr-policy.pdf", 2)]),
    ("What is the admin address of the AX-300 router?", "words", [("router-manual.pdf", 2)]),
    ("How long is the free-look period?", "words", [("insurance-policy.pdf", 4)]),
    ("Which hosting provider was chosen?", "words", [("meeting-notes.pdf", 2)]),
    ("How long is the notice period during probation?", "words", [("hr-policy.pdf", 4)]),
    ("When is the security deposit returned?", "words", [("lease.pdf", 2)]),
    ("What does a blinking orange light mean on the AX-300?", "words", [("router-manual.pdf", 3)]),
    ("Can I keep a cat in the flat?", "reworded", [("lease.pdf", 3)]),
    ("As an employee, how do I get my money back for a work trip?", "reworded", [("hr-policy.pdf", 3)]),
    (
        "I can't log in to my AX-300 internet box any more. How do I start over?",
        "reworded",
        [("router-manual.pdf", 4)],
    ),
    ("If I break my leg tomorrow, am I covered straight away?", "reworded", [("insurance-policy.pdf", 3)]),
    ("Why was the go-live date pushed back?", "reworded", [("meeting-notes.pdf", 1)]),
    ("Who pays if I accidentally damage something in the apartment?", "reworded", [("lease.pdf", 4)]),
    ("Can I work from my house some days?", "reworded", [("hr-policy.pdf", 1)]),
    ("How much does the health cover cost per year?", "reworded", [("insurance-policy.pdf", 1)]),
    ("What happens if I move out after three months?", "reworded", [("lease.pdf", 5)]),
    ("Is a cracked AX-300 from a fall fixed for free?", "reworded", [("router-manual.pdf", 5)]),
    ("What is Ravi supposed to do?", "names", [("meeting-notes.pdf", 3)]),
    ("What is Lena's task?", "names", [("meeting-notes.pdf", 3)]),
    ("What power adapter does the AX-300 use?", "names", [("router-manual.pdf", 1)]),
    ("Who is the tenant at 14 Elm Court?", "names", [("lease.pdf", 1)]),
    ("What is 192.168.8.1?", "names", [("router-manual.pdf", 2)]),
    ("What happens to claims over 20,000 rupees?", "names", [("hr-policy.pdf", 3)]),
    ("Why Kestrel Cloud?", "names", [("meeting-notes.pdf", 2)]),
    (
        "How long is the notice period in the lease, and in the employee handbook?",
        "parts",
        [("lease.pdf", 5), ("hr-policy.pdf", 4)],
    ),
    (
        "How quickly must I report damage in the flat, and a security incident at work?",
        "parts",
        [("lease.pdf", 4), ("hr-policy.pdf", 5)],
    ),
    (
        "What does the AX-300 warranty cover, and how much ambulance cost does the insurance pay?",
        "parts",
        [("router-manual.pdf", 5), ("insurance-policy.pdf", 2)],
    ),
    (
        "What is the Falcon budget, and which feature was dropped from release 1?",
        "parts",
        [("meeting-notes.pdf", 1), ("meeting-notes.pdf", 2)],
    ),
    (
        "As an employee, how many days do I have to claim expenses, and to send hospital bills to the insurer?",
        "parts",
        [("hr-policy.pdf", 3), ("insurance-policy.pdf", 4)],
    ),
    (
        "How much is the flat's deposit, and what is the sum insured?",
        "parts",
        [("lease.pdf", 2), ("insurance-policy.pdf", 1)],
    ),
    (
        "How do I reset the AX-300, and how often must employees change their passwords?",
        "parts",
        [("router-manual.pdf", 4), ("hr-policy.pdf", 5)],
    ),
    # About the look-alikes.
    ("What is the admin address of the AX-500?", "names", [("router-ax500-manual.pdf", 2)]),
    ("What power adapter does the AX-500 need?", "names", [("router-ax500-manual.pdf", 1)]),
    ("How long is the AX-500 warranty?", "names", [("router-ax500-manual.pdf", 5)]),
    ("What is the notice period for contractors?", "words", [("contractor-policy.pdf", 3)]),
    ("How often must contractors change their passwords?", "words", [("contractor-policy.pdf", 4)]),
    ("My AX-500's orange light keeps flashing. Is something wrong?", "reworded", [("router-ax500-manual.pdf", 3)]),
    ("Do contractors get paid holidays?", "reworded", [("contractor-policy.pdf", 1)]),
    ("How does a contractor get reimbursed for a train ticket?", "reworded", [("contractor-policy.pdf", 2)]),
    (
        "What is the admin address of the AX-300, and of the AX-500?",
        "parts",
        [("router-manual.pdf", 2), ("router-ax500-manual.pdf", 2)],
    ),
    (
        "How long is the notice period for employees, and for contractors?",
        "parts",
        [("hr-policy.pdf", 4), ("contractor-policy.pdf", 3)],
    ),
]
