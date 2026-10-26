"""The answer evaluation set (V0.9): questions from the retrieval set, each
with the facts a correct answer must state, and questions the documents
don't answer. Written before any answer was recorded, so the facts weren't
fitted to what Gemini says.

A fact is a tuple of ways to write it; the answer must contain one of them
(case doesn't matter): ("2 months", "two months").
"""

from retrieval_set import COMPARE, QUESTIONS

FACTS = {
    # words
    "What is the late payment fee for rent?": [("500",)],
    "How many days of paid annual leave do employees get?": [("24",)],
    "What is the admin address of the AX-300 router?": [("192.168.8.1",)],
    "How long is the free-look period?": [("15 days",)],
    "Which hosting provider was chosen?": [("Kestrel Cloud",)],
    "When is the security deposit returned?": [("21 days",)],
    "What does a blinking orange light mean on the AX-300?": [("no internet",)],
    # reworded
    "As an employee, how do I get my money back for a work trip?": [("30 days",)],
    "I can't log in to my AX-300 internet box any more. How do I start over?": [("10 seconds",)],
    "Why was the go-live date pushed back?": [("payment gateway",)],
    "Who pays if I accidentally damage something in the apartment?": [("tenant",)],
    "How much does the health cover cost per year?": [("18,400", "18400")],
    "What happens if I move out after three months?": [("lock-in",)],
    # names
    "What is Ravi supposed to do?": [("20 March",)],
    "What is Lena's task?": [("test plan",)],
    "What power adapter does the AX-300 use?": [("12 V", "12V"), ("1.5 A", "1.5A")],
    "Who is the tenant at 14 Elm Court?": [("Maya Fernandes",)],
    "What happens to claims over 20,000 rupees?": [("director",)],
    "Why Kestrel Cloud?": [("18%", "18 percent")],
    "What is the admin address of the AX-500?": [("192.168.10.1",)],
    "How long is the AX-500 warranty?": [("3-year", "3 years", "three years", "3 year")],
    # parts
    "How long is the notice period in the lease, and in the employee handbook?": [
        ("two months", "2 months"),
        ("60 days",),
    ],
    "What is the admin address of the AX-300, and of the AX-500?": [("192.168.8.1",), ("192.168.10.1",)],
    "How long is the notice period for employees, and for contractors?": [("60 days",), ("7 days",)],
    "How much is the flat's deposit, and what is the sum insured?": [
        ("56,000", "56000"),
        ("5 lakh", "500,000", "5,00,000"),
    ],
    # compare
    "Who must give longer notice to leave: an employee or a contractor?": [("60 days",), ("7 days",)],
    "Which router supports more connected devices, the AX-300 or the AX-500?": [("64",), ("128",)],
    "Is the AX-500 warranty longer than the AX-300 warranty?": [
        ("2-year", "2 years", "two years", "2 year"),
        ("3-year", "3 years", "three years", "3 year"),
    ],
    "Do employees or contractors have to change their passwords more often?": [("90 days",), ("60 days",)],
    "Which costs more per month: the flat's rent or the health insurance premium?": [
        ("28,000", "28000"),
        ("18,400", "18400"),
    ],
}

# (question, kind, answer pages, facts), in the order above.
_LABELLED = {question: (kind, pages) for question, kind, pages in QUESTIONS + COMPARE}
ANSWERABLE = [(question, *_LABELLED[question], facts) for question, facts in FACTS.items()]

# Nothing in the documents answers these; the right reply is NOT_FOUND with
# no citations. Each is close to a topic the documents do cover.
UNANSWERABLE = [
    "What is the landlord's phone number?",
    "How many floors does the building at 14 Elm Court have?",
    "What colour is the AX-300 router?",
    "What is the salary of a permanent employee?",
    "Does the AX-500 support Bluetooth?",
    "When was Brightline Software founded?",
]
